from __future__ import annotations

from pathlib import Path
import ctypes
import threading
import time

try:
    import requests
except ImportError:
    requests = None

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QObject, Signal, QPoint, QPointF
from PySide6.QtGui import QPainter, QPixmap, QImage, QCursor, QBitmap, QColor
from PySide6.QtWidgets import QWidget, QApplication

from .settings_window import CassetteSettingsDialog

from .cassette_renderer import CassetteRenderer


class _AssetLoader(QObject):
    """Loads Spotify artwork and lyrics off the GUI thread."""
    ready = Signal(str, object, object, str)  # track id, image bytes, lyrics, plain fallback

    def load(self, track_id, artwork_url, lyrics_client, artist, title, album, duration, artwork_provider=None):
        def worker():
            # Copy the argument into a worker-local variable before assigning to it.
            # Without this, Python treats artwork_url as a local variable because the
            # fallback provider may assign to it, causing UnboundLocalError.
            resolved_artwork_url = artwork_url or ""
            image_bytes = b""
            synced = []
            plain = ""
            if not resolved_artwork_url and artwork_provider is not None:
                try:
                    resolved_artwork_url = artwork_provider() or ""
                except Exception:
                    resolved_artwork_url = ""
            if resolved_artwork_url:
                try:
                    local = Path(resolved_artwork_url)
                    if local.exists() and local.is_file():
                        image_bytes = local.read_bytes()
                    elif requests is not None:
                        response = requests.get(
                            resolved_artwork_url,
                            headers={"User-Agent": "Cassette/1.0"},
                            timeout=10,
                        )
                        response.raise_for_status()
                        image_bytes = response.content
                except Exception:
                    pass
            if lyrics_client is not None:
                try:
                    result = lyrics_client.get(artist, title, album, duration)
                    synced = result.get("synced", [])
                    plain = result.get("plain", "") or ""
                except Exception:
                    pass
            self.ready.emit(track_id, image_bytes, synced, plain)

        threading.Thread(target=worker, name="CassetteTrackAssets", daemon=True).start()


class CassetteWindow(QWidget):
    """Reference-sized Spotify cassette with liquid-glass material."""

    def __init__(self, settings, spotify, lyrics, monitor, animations):
        super().__init__()
        self.settings, self.spotify, self.lyrics = settings, spotify, lyrics
        self.monitor, self.animations = monitor, animations
        self.renderer = CassetteRenderer()
        self.renderer.ui_scale = float(getattr(settings, "cassette_scale", 1.0))
        self.renderer.glass_opacity = float(settings.get("appearance/glass_opacity", 0.82))
        self._settings_dialog = None
        self.resize(round(510 * self.renderer.ui_scale), round(436 * self.renderer.ui_scale))
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        # The top-level surface must be genuinely translucent. Windows'
        # compositor supplies the *live* acrylic backdrop; QPainter only adds
        # the optical glass layers. Keeping the Qt surface transparent avoids
        # the opaque client rectangle that appeared with DWM system-backdrop
        # on this frameless window. No desktop screenshot is used.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowOpacity(0.0)
        self._visible_state = "HIDDEN"
        self._anim = None
        self._track_id = None
        self._native_glass_ready = False
        self._native_region_size = None
        self._asset_loader = _AssetLoader()
        self._volume_dragging = False
        self._pending_volume = None
        self._volume_timer = QTimer(self)
        self._volume_timer.setSingleShot(True)
        self._volume_timer.setInterval(140)
        self._volume_timer.timeout.connect(self._flush_volume)
        self._asset_loader.ready.connect(self._assets_ready)

        # Smooth local playback clock. Spotify is polled in the background,
        # while this clock keeps the progress rail/lyrics visually real-time.
        self._display_position_ms = 0
        self._position_received_at = time.monotonic()

        # Header/empty-glass dragging moves the complete widget. Interactive
        # controls keep their normal hit targets.
        self._dragging = False
        self._drag_offset = None

        self._tick = QTimer(self)
        self._tick.setInterval(24)
        self._tick.timeout.connect(self._frame)
        self._tick.start()

        # A tiny, low-frequency backdrop probe is used only to choose lyric
        # text contrast. It samples a few screen pixels immediately OUTSIDE the
        # Cassette window; it never captures the desktop or feeds pixels into
        # the glass renderer. This lets lyrics switch between light/dark text
        # when the app behind Cassette changes from dark to bright.
        self._backdrop_timer = QTimer(self)
        self._backdrop_timer.setInterval(80)
        self._backdrop_timer.timeout.connect(self._sample_backdrop_color)
        self._backdrop_timer.start()
        self._sample_backdrop_color()

        self.renderer.connected = bool(getattr(spotify, "is_connected", False))
        self.renderer.artist = "Ready to play" if self.renderer.connected else "Connect Spotify"
        self.renderer.status = "Ready to play" if self.renderer.connected else "Connect Spotify"

        if hasattr(spotify, "connection_changed"):
            spotify.connection_changed.connect(self._on_connection_changed)
        if hasattr(spotify, "error"):
            spotify.error.connect(self._on_spotify_error)

    def _sample_backdrop_color(self):
        """Detect the actual background behind the Cassette using Qt's screen.

        This deliberately does NOT try to infer the background from the Cassette
        size or from a few Win32 GetPixel coordinates.  Instead we grab only a
        very thin ring *outside* the current window and sample that ring.
        QScreen handles Windows DPI/scaling and multi-monitor coordinates for us.
        The Cassette itself is never included in the sampled pixels.
        """
        if not self.isVisible():
            return
        try:
            screen = self.screen()
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is None:
                return

            # Global logical geometry of the current widget.  QScreen maps this
            # correctly regardless of 100/125/150/200% Windows scaling.
            top_left = self.mapToGlobal(QPoint(0, 0))
            w = max(1, self.width())
            h = max(1, self.height())
            x = top_left.x()
            y = top_left.y()

            # Sample a thin outside ring.  The distance scales with the actual
            # widget size, but is clamped so tiny and huge UI sizes both work.
            pad = max(6, min(28, int(min(w, h) * 0.035)))
            strip = max(4, min(14, pad // 2))

            # Four strips outside the current window. They contain only the
            # background, never the Cassette itself.
            rects = [
                QRect(x, y - pad - strip, w, strip),          # top
                QRect(x, y + h + pad, w, strip),              # bottom
                QRect(x - pad - strip, y, strip, h),          # left
                QRect(x + w + pad, y, strip, h),              # right
            ]

            vals = []
            screen_geo = screen.geometry()
            for rect in rects:
                # Clip each strip to the current monitor. This also prevents
                # invalid grabs when the widget is close to an edge.
                r = rect.intersected(screen_geo)
                if r.isEmpty():
                    continue
                pix = screen.grabWindow(0, r.x(), r.y(), r.width(), r.height())
                if pix.isNull():
                    continue

                # Downsample the strip aggressively; we only need its color,
                # not an image. This keeps the 80ms detector inexpensive.
                step_x = max(1, pix.width() // 12)
                step_y = max(1, pix.height() // 8)
                for py in range(0, pix.height(), step_y):
                    for px in range(0, pix.width(), step_x):
                        c = pix.pixelColor(px, py)
                        if c.alpha() == 0:
                            continue
                        vals.append((c.red(), c.green(), c.blue()))

            if not vals:
                return

            # Robust median RGB and median luminance. A bright icon or dark text
            # in the background cannot dominate the decision.
            channels = [sorted(v[i] for v in vals) for i in range(3)]
            mid = len(vals) // 2
            if len(vals) & 1:
                rgb = tuple(ch[mid] for ch in channels)
            else:
                rgb = tuple((ch[mid - 1] + ch[mid]) // 2 for ch in channels)
            palette = QColor(*rgb)

            lums = sorted(
                (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
                for r, g, b in vals
            )
            m = len(lums) // 2
            lum = lums[m] if len(lums) & 1 else (lums[m - 1] + lums[m]) * 0.5

            # Use wide hysteresis so the UI changes decisively but doesn't
            # flicker around grey backgrounds.
            previous = bool(self.renderer.backdrop_text_light)
            if previous:
                text_light = lum < 0.58
            else:
                text_light = lum < 0.46
            if previous and lum >= 0.64:
                text_light = False
            elif (not previous) and lum <= 0.38:
                text_light = True

            self.renderer.set_backdrop_palette(palette, text_light)
            self.update()
        except Exception:
            # Contrast detection must never be allowed to break paint/update.
            pass

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            self.renderer.paint(p, QRectF(0, 0, self.width(), self.height()))
        finally:
            if p.isActive():
                p.end()

    def _frame(self):
        # 30 FPS is reserved for active playback: reel motion plus a local
        # interpolation of Spotify's last network position. No HTTP work occurs
        # on this timer.
        if not self.renderer.playing:
            return
        if self.settings.reel_enabled:
            self.renderer.reel_angle = (self.renderer.reel_angle + 3.8) % 360
        elapsed = max(0.0, time.monotonic() - self._position_received_at)
        position = self._display_position_ms + int(elapsed * 1000.0)
        duration = int(self.monitor.duration or self.renderer.duration or 0)
        if duration > 0:
            position = min(position, duration)
            self.renderer.progress = position / duration
        self._update_lyric_line(position)
        self.update()

    def _on_connection_changed(self, connected, message):
        self.renderer.connected = bool(connected)
        if not connected:
            self._track_id = None
            self.renderer.title = "Nothing playing"
            self.renderer.artist = "Connect Spotify"
            self.renderer.status = message or "Connect Spotify"
            self.renderer.set_artwork(QPixmap())
            self.renderer.lyrics = []
            self.renderer.lyric_line = ""
            self.renderer.plain_lyric = ""
        elif self.renderer.title == "Nothing playing":
            self.renderer.artist = "Ready to play"
            self.renderer.status = message or "Ready to play"
        self.update()

    def _on_spotify_error(self, message):
        if not self.renderer.connected:
            self.renderer.artist = "Connect Spotify"
        self.renderer.status = message or self.renderer.status
        self.update()

    def on_track_changed(self, track):
        track_id = track.get("id") or ""
        self._track_id = track_id
        self.renderer.title = track.get("title", "Nothing playing") or "Nothing playing"
        self.renderer.artist = track.get("artist", "") or "Unknown artist"
        self.renderer.lyrics = list(track.get("lyrics") or [])
        self.renderer.lyric_index = 0
        self.renderer.lyric_line = ""
        self.renderer.plain_lyric = ""
        if self.renderer.lyrics:
            self._update_lyric_line(0)
        self.renderer.progress = 0
        self.renderer.duration = int(track.get("duration", 0) or 0)
        self.renderer.set_artwork(QPixmap())
        self.renderer.status = "Playing" if self.renderer.playing else "Paused"
        self.update()

        self._asset_loader.load(
            track_id,
            track.get("artwork", ""),
            self.lyrics,
            track.get("artist", ""),
            track.get("title", ""),
            track.get("album", ""),
            track.get("duration", 0),
            (lambda: self.spotify.album_artwork(track.get("album_id", ""))) if hasattr(self.spotify, "album_artwork") else None,
        )

    def _assets_ready(self, track_id, image_bytes, synced, plain):
        if track_id != self._track_id:
            return
        if image_bytes:
            image = QImage.fromData(image_bytes)
            if not image.isNull():
                self.renderer.set_artwork(QPixmap.fromImage(image))
        if synced:
            self.renderer.lyrics = synced
        elif not self.renderer.lyrics:
            self.renderer.lyrics = []
        self.renderer.lyric_index = 0
        self.renderer.lyric_line = ""
        if plain:
            self.renderer.plain_lyric = next((line.strip() for line in plain.splitlines() if line.strip()), "")
        self._update_lyric_line(self.monitor.current_position())
        self.update()

    def _update_lyric_line(self, ms):
        if self.renderer.lyrics:
            t = ms / 1000.0
            idx = 0
            for i, (ts, text) in enumerate(self.renderer.lyrics):
                if ts <= t:
                    idx = i
                else:
                    break
            self.renderer.lyric_index = idx
            self.renderer.lyric_line = self.renderer.lyrics[idx][1] if self.renderer.lyrics else ""
        else:
            self.renderer.lyric_line = ""

    def on_playback_state(self, playing):
        self.renderer.playing = bool(playing)
        self.renderer.status = "Playing" if playing else "Paused"
        if not playing:
            self._display_position_ms = int(self.monitor.current_position() or self._display_position_ms)
            self._position_received_at = time.monotonic()
        self.update()

    def on_position(self, ms):
        self._display_position_ms = int(ms or 0)
        self._position_received_at = time.monotonic()
        self.renderer.progress = (self._display_position_ms / self.monitor.duration) if self.monitor.duration else 0
        self._update_lyric_line(self._display_position_ms)
        self.update()

    def on_player_status(self, status):
        self.renderer.status = status or ""
        if self.renderer.title == "Nothing playing":
            if status == "Connect Spotify":
                self.renderer.artist = "Connect Spotify"
            elif status:
                self.renderer.artist = status
        self.update()

    def toggle_at_cursor(self):
        if self._visible_state in ("VISIBLE", "APPEARING"):
            self.hide_smooth()
        else:
            self.show_at_cursor()

    def _stop_animation(self):
        if self._anim is not None:
            try:
                self._anim.stop()
                self._anim.deleteLater()
            except RuntimeError:
                pass
            self._anim = None

    def _apply_windows_glass(self):
        """Apply Windows DWM glass when available; use Qt-native translucency on macOS."""
        if __import__("os").name != "nt":
            # macOS does not expose the Windows DWM API. The window remains a
            # genuinely translucent, rounded Qt surface and the renderer draws
            # the optical glass layers. Keeping this path separate prevents any
            # Win32 dependency from affecting the macOS build.
            self._native_glass_ready = False
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.winId())
            user32 = ctypes.windll.user32

            class ACCENT_POLICY(ctypes.Structure):
                _fields_ = [
                    ("AccentState", ctypes.c_int),
                    ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_uint32),
                    ("AnimationId", ctypes.c_int),
                ]

            class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
                _fields_ = [
                    ("Attribute", ctypes.c_int),
                    ("Data", ctypes.POINTER(ACCENT_POLICY)),
                    ("SizeOfData", ctypes.c_size_t),
                ]

            # First clip the actual HWND. Do this BEFORE enabling DWM blur so
            # the compositor never gets an opportunity to expose a rectangular
            # blur surface outside Cassette's rounded silhouette.
            get_client_rect = user32.GetClientRect
            get_client_rect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            get_client_rect.restype = wintypes.BOOL
            client = wintypes.RECT()
            region_ok = False
            if get_client_rect(wintypes.HWND(hwnd), ctypes.byref(client)):
                width = max(1, client.right - client.left)
                height = max(1, client.bottom - client.top)
                # GetClientRect is already in the HWND's native coordinate
                # space. Do NOT multiply it by Qt's devicePixelRatio here.
                radius = max(1, int(round(31.0 * float(self.renderer.ui_scale))))
                create_round = user32.CreateRoundRectRgn
                create_round.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
                create_round.restype = wintypes.HRGN
                region = create_round(0, 0, width + 1, height + 1, radius * 2, radius * 2)
                if region:
                    set_region = user32.SetWindowRgn
                    set_region.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
                    set_region.restype = ctypes.c_int
                    region_ok = bool(set_region(wintypes.HWND(hwnd), region, True))
                    if not region_ok:
                        user32.DeleteObject(region)

            # Windows compositor: live backdrop blur only. No white/black tint.
            # ACCENT_ENABLE_BLURBEHIND = 3.
            policy = ACCENT_POLICY(3, 0, 0x00000000, 0)
            data = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.pointer(policy), ctypes.sizeof(policy))
            set_wca = getattr(user32, "SetWindowCompositionAttribute", None)
            blur_ok = False
            if set_wca is not None:
                set_wca.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
                set_wca.restype = wintypes.BOOL
                blur_ok = bool(set_wca(wintypes.HWND(hwnd), ctypes.byref(data)))

            # Ask DWM for native rounded corners as an additional hint on
            # Windows 11. The Win32 region remains the hard clipping boundary.
            try:
                dwmapi = ctypes.windll.dwmapi
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                value = ctypes.c_int(DWMWCP_ROUND)
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except Exception:
                pass

            self._native_glass_ready = bool(region_ok and blur_ok)
        except Exception:
            self._native_glass_ready = False

    def _apply_round_mask(self):
        """Fallback Qt clip for non-Windows or before the native HWND exists."""
        try:
            from PySide6.QtCore import QRect
            bitmap = QBitmap(self.size())
            bitmap.fill(Qt.GlobalColor.color0)
            painter = QPainter(bitmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(Qt.GlobalColor.color1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(0, 0, self.width(), self.height()), 31, 31)
            painter.end()
            self.setMask(bitmap)
        except Exception:
            pass

    def _run_spotify_action(self, method, *args):
        """Run a playback command off the GUI thread."""
        fn = getattr(self.spotify, method, None)
        if fn is None:
            return
        def worker():
            try:
                fn(*args)
            except Exception:
                # Client implementations emit their own error signal. Never
                # mutate Qt-rendered state from the worker thread.
                pass
        threading.Thread(target=worker, name=f"CassetteAction-{method}", daemon=True).start()

    def show_at_cursor(self):
        self._stop_animation()
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(pos.x() - self.width() // 2, geo.left() + 8), geo.right() - self.width() - 8)
        y = min(max(pos.y() - self.height() // 2, geo.top() + 8), geo.bottom() - self.height() - 8)
        self.move(x, y)
        self._visible_state = "APPEARING"
        self.setWindowOpacity(0.0)
        # Create/show the native HWND first, then apply the compositor and
        # physical-pixel rounded region. This is important on per-monitor DPI
        # systems where the HWND dimensions are not the same as Qt logical
        # dimensions.
        self.show()
        self._apply_round_mask()
        self._apply_windows_glass()
        self.raise_()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(330)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._animation_shown)
        self._anim.start()

    def _animation_shown(self):
        self._visible_state = "VISIBLE"
        self._anim = None

    def hide_smooth(self):
        # The settings panel belongs to Cassette's visible state. Hiding the
        # app with Ctrl+Alt+S (or the tray) hides the panel at the same time.
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.hide()
        if self._visible_state == "HIDDEN":
            return
        self._stop_animation()
        self._visible_state = "DISAPPEARING"
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self._finish_hide)
        self._anim.start()

    def _finish_hide(self):
        self._anim = None
        self.setWindowOpacity(0.0)
        self.hide()
        self._visible_state = "HIDDEN"

    def _set_volume_from_x(self, x):
        scale = max(0.72, min(1.35, float(self.renderer.ui_scale)))
        x = x / scale
        layout = self.renderer.layout(QRectF(0, 0, 510, 436))
        vb = layout["volume_bar"]
        value = int(max(0.0, min(1.0, (x - vb.left()) / max(1.0, vb.width()))) * 100)
        self.renderer.volume = value
        self._pending_volume = value
        self._volume_timer.start()
        self.update()

    def _flush_volume(self):
        value = self._pending_volume
        if value is None or not hasattr(self.spotify, "volume"):
            return
        self._pending_volume = None
        self._run_spotify_action("volume", int(value))

    def _control_at(self, pos):
        layout = self.renderer.layout(QRectF(0, 0, 510, 436))
        controls = layout["controls"]
        if not controls.contains(pos):
            return None
        slots = layout["slots"]
        names = ["shuffle", "back10", "prev", "play", "next", "forward10", "volume"]
        for name, slot in zip(names, slots):
            if slot.contains(pos):
                return name
        return None

    def _seek_from_x(self, x):
        scale = max(0.72, min(1.35, float(self.renderer.ui_scale)))
        x = x / scale
        bar = self.renderer.layout(QRectF(0, 0, 510, 436))["bar"]
        if not self.monitor.duration:
            return
        progress = max(0.0, min(1.0, (x - bar.left()) / max(1.0, bar.width())))
        target = int(progress * self.monitor.duration)
        self._display_position_ms = target
        self._position_received_at = time.monotonic()
        self.renderer.progress = progress
        self._update_lyric_line(target)
        self.update()
        self._run_spotify_action("seek", target)

    def _seek_relative(self, delta_ms):
        duration = int(self.monitor.duration or self.renderer.duration or 0)
        if duration <= 0:
            return
        current = int(self._display_position_ms + max(0.0, time.monotonic() - self._position_received_at) * 1000.0)
        target = max(0, min(duration, current + int(delta_ms)))
        self._display_position_ms = target
        self._position_received_at = time.monotonic()
        self.renderer.progress = target / duration
        self._update_lyric_line(target)
        self.update()
        self._run_spotify_action("seek", target)

    def _set_pressed(self, name):
        self.renderer.pressed_control = name
        self.update()

    def _open_settings(self):
        if self._settings_dialog is None:
            self._settings_dialog = CassetteSettingsDialog(self, self.settings, self.renderer)
            self._settings_dialog.finished.connect(lambda _code: setattr(self, "_settings_dialog", None))
            self._settings_dialog.scale_changed.connect(self._apply_ui_scale)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _apply_ui_scale(self, scale):
        scale = max(0.72, min(1.35, float(scale)))
        old_center = self.frameGeometry().center()
        self.resize(round(510 * scale), round(436 * scale))
        self.move(old_center.x() - self.width() // 2, old_center.y() - self.height() // 2)
        self._apply_round_mask()
        if self.isVisible() or self._native_glass_ready:
            self._apply_windows_glass()
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        raw_pos = event.position()
        scale = max(0.72, min(1.35, float(self.renderer.ui_scale)))
        pos = raw_pos / scale
        layout = self.renderer.layout(QRectF(0, 0, 510, 436))

        header = layout["header"]
        settings_center = QPointF(header.right() - 29, header.center().y())
        if (pos - settings_center).manhattanLength() <= 18:
            self._set_pressed(None)
            self._open_settings()
            event.accept()
            return

        # Progress hitbox exactly follows the painted rail, with a comfortable
        # vertical tolerance that does not overlap the controls.
        bar = layout["bar"]
        progress_hit = QRectF(bar.left() - 8, bar.top() - 12, bar.width() + 16, 27)
        if progress_hit.contains(pos) and self.monitor.duration:
            self._set_pressed(None)
            self._seek_from_x(raw_pos.x())
            event.accept()
            return

        control = self._control_at(pos)
        if control:
            if control == "volume":
                self._volume_dragging = True
                self._set_pressed("volume")
                self._set_volume_from_x(raw_pos.x())
            elif control == "shuffle":
                self._set_pressed(control); self._run_spotify_action("shuffle", True)
            elif control == "back10":
                self._set_pressed(control); self._seek_relative(-10000)
            elif control == "prev":
                self._set_pressed(control); self._run_spotify_action("previous")
            elif control == "play":
                self._set_pressed(control)
                self.renderer.playing = not self.renderer.playing
                self.renderer.status = "Playing" if self.renderer.playing else "Paused"
                if not self.renderer.playing:
                    self._display_position_ms = int(self._display_position_ms + max(0.0, time.monotonic() - self._position_received_at) * 1000.0)
                self._position_received_at = time.monotonic()
                self._run_spotify_action("play" if self.renderer.playing else "pause")
                self.update()
            elif control == "next":
                self._set_pressed(control); self._run_spotify_action("next")
            elif control == "forward10":
                self._set_pressed(control); self._seek_relative(10000)
            event.accept()
            return

        # Drag anywhere on the glass outside interactive controls. This makes
        # the whole widget easy to reposition after activation.
        header = layout["header"]
        if header.contains(pos) or layout["outer"].contains(pos):
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return

        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._volume_dragging:
            self._set_volume_from_x(event.position().x())
            event.accept()
            return
        if self._dragging and self._drag_offset is not None:
            target = event.globalPosition().toPoint() - self._drag_offset
            screen = QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            x = min(max(target.x(), geo.left() + 4), geo.right() - self.width() - 4)
            y = min(max(target.y(), geo.top() + 4), geo.bottom() - self.height() - 4)
            self.move(x, y)
            event.accept()
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._volume_dragging:
                self._set_volume_from_x(event.position().x())
                self._volume_dragging = False
                self._volume_timer.start(20)
                self.renderer.pressed_control = None
                self.update()
                event.accept()
                return
            if self.renderer.pressed_control is not None:
                self.renderer.pressed_control = None
                self.update()
            if self._dragging:
                self._dragging = False
                self._drag_offset = None
                event.accept()
                return
        return super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_round_mask()
        if self.isVisible() or self._native_glass_ready:
            self._apply_windows_glass()

