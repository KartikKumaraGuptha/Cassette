from __future__ import annotations

import os
import re
import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)


DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def app_base_dir() -> Path:
    """Return the directory containing main.py (or the packaged executable)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def env_file_path() -> Path:
    """Return the writable .env location for source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            path = Path.home() / "Library" / "Application Support" / "Cassette"
        else:
            app_data = os.environ.get("LOCALAPPDATA")
            if app_data:
                path = Path(app_data) / "Cassette"
            else:
                path = Path.home() / "AppData" / "Local" / "Cassette"
        path.mkdir(parents=True, exist_ok=True)
        return path / ".env"
    return Path(__file__).resolve().parent.parent / ".env"


def _available_screen_geometry(widget):
    """Return the usable screen area, excluding the Windows taskbar/docks."""
    screen = widget.screen()
    if screen is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return None
    return screen.availableGeometry()


def _fit_window_to_work_area(widget, base_width, base_height, margin=0.92):
    """Return a scale and size that fit inside the current screen work area."""
    area = _available_screen_geometry(widget)
    if area is None:
        return 1.0, base_width, base_height

    max_width = max(320, int(area.width() * margin))
    max_height = max(360, int(area.height() * margin))
    scale = min(1.0, max_width / base_width, max_height / base_height)
    width = max(320, int(base_width * scale))
    height = max(360, int(base_height * scale))
    return scale, width, height


def has_spotify_credentials() -> bool:
    path = env_file_path()
    if not path.exists():
        return False
    values = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return False
    return bool(values.get("SPOTIFY_CLIENT_ID"))


class _GuideContent(QWidget):
    """Scrollable setup-guide content with optional s1.png, s2.png, ... images."""

    def __init__(self, dark_mode=False, parent=None):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.images = []
        self.setMinimumWidth(680)
        self._load_images()

    def _load_images(self):
        files = []
        for path in app_base_dir().glob("s*.png"):
            stem = path.stem[1:]
            if stem.isdigit():
                files.append((int(stem), path))
        self.images = [p for _, p in sorted(files)]

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(25, 29, 36) if self.dark_mode else QColor(245, 248, 252))
        color = QColor(245, 248, 252, 240) if self.dark_mode else QColor(17, 23, 31, 240)
        sub = QColor(215, 220, 228, 175) if self.dark_mode else QColor(45, 53, 64, 175)
        f = p.font(); f.setPixelSize(22); f.setWeight(QFont.Weight.DemiBold); p.setFont(f); p.setPen(color)
        p.drawText(QRectF(34, 24, 612, 32), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "How do I get these?")
        f.setPixelSize(11); f.setWeight(QFont.Weight.Normal); p.setFont(f); p.setPen(sub)
        p.drawText(QRectF(34, 61, 612, 36), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Follow these steps to create your Spotify app and copy the Client ID.\nScreenshots are loaded automatically from s1.png, s2.png, s3.png... next to main.py.")

        text_color = QColor(235, 240, 246, 225) if self.dark_mode else QColor(25, 31, 40, 225)
        muted = QColor(205, 212, 222, 175) if self.dark_mode else QColor(65, 74, 86, 175)
        steps = [
            ("1. Open the Spotify Developer Dashboard", "Open the Spotify for Developers Dashboard. Use the dashboard to create and configure the app that Cassette will connect to."),
            ("2. Log in with Spotify", "Click Log In and sign in with the Spotify account you want to use with Cassette. If Spotify asks you to authorize access, complete the sign-in flow."),
            ("3. Create an app and select the required APIs", "Choose Create app, enter a name and short description, then select both Web API and Web Playback SDK (Web Playback API) when asked which APIs/SDKs you plan to use. Accept the developer terms and create the app."),
            ("4. Add the Redirect URI", "Open your app settings and add exactly: http://127.0.0.1:8888/callback. Save the settings. The redirect URI must match exactly, including the address and port."),
            ("5. Copy the Client ID", "After the app is created, copy the Client ID shown in the app settings. Cassette uses the Authorization Code with PKCE flow, so you do not need to enter a Client Secret."),
            ("6. Return to Cassette", "Paste the Client ID into the Welcome to Cassette window. Keep the Redirect URI as http://127.0.0.1:8888/callback unless you intentionally changed the app configuration to match a different URI."),
        ]
        y = 112
        for i, (heading, body) in enumerate(steps):
            f = p.font(); f.setPixelSize(13); f.setWeight(QFont.Weight.DemiBold); p.setFont(f); p.setPen(text_color)
            p.drawText(QRectF(34, y + 1, 612, 23), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, heading)
            f.setPixelSize(11); f.setWeight(QFont.Weight.Normal); p.setFont(f); p.setPen(muted)
            p.drawText(QRectF(34, y + 29, 612, 38), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, body)
            y += 76
            if i < len(steps) - 1:
                box = QRectF(30, y, 620, 190)
                p.setPen(QPen(QColor(190, 200, 212, 85) if self.dark_mode else QColor(90, 100, 112, 70), 1))
                p.setBrush(QColor(255, 255, 255, 18) if self.dark_mode else QColor(225, 230, 236, 145))
                p.drawRoundedRect(box, 14, 14)
                if i < len(self.images):
                    pix = QPixmap(str(self.images[i]))
                    if not pix.isNull():
                        scaled = pix.scaled(int(box.width()-12), int(box.height()-12), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        p.drawPixmap(int(box.x() + (box.width()-scaled.width())/2), int(box.y() + (box.height()-scaled.height())/2), scaled)
                else:
                    self._placeholder(p, 30, y, 620, 190, f"SCREENSHOT PLACEHOLDER {i+1}\nAdd s{i+1}.png next to main.py")
                y += 205
        if len(self.images) > len(steps):
            for i in range(len(steps), len(self.images)):
                box = QRectF(30, y, 620, 190)
                p.setPen(QPen(QColor(190, 200, 212, 85) if self.dark_mode else QColor(90, 100, 112, 70), 1))
                p.setBrush(QColor(255, 255, 255, 18) if self.dark_mode else QColor(225, 230, 236, 145))
                p.drawRoundedRect(box, 14, 14)
                pix = QPixmap(str(self.images[i]))
                if not pix.isNull():
                    scaled = pix.scaled(int(box.width()-12), int(box.height()-12), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    p.drawPixmap(int(box.x() + (box.width()-scaled.width())/2), int(box.y() + (box.height()-scaled.height())/2), scaled)
                y += 205
        p.end()
        self.setMinimumHeight(y + 20)

    def _placeholder(self, p, x, y, w, h, text):
        p.setPen(QPen(QColor(190, 200, 212, 85) if self.dark_mode else QColor(90, 100, 112, 70), 1, Qt.PenStyle.DashLine))
        p.setBrush(QColor(255, 255, 255, 18) if self.dark_mode else QColor(225, 230, 236, 145))
        p.drawRoundedRect(QRectF(x, y, w, h), 14, 14)
        f = p.font(); f.setPixelSize(12); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.setPen(QColor(205, 212, 222, 165) if self.dark_mode else QColor(70, 80, 92, 150))
        p.drawText(QRectF(x + 28, y + 8, w - 56, h - 16), Qt.AlignmentFlag.AlignCenter, text)


class SetupGuideWindow(QDialog):
    """Separate setup guide; automatically loads s1.png, s2.png, ... from main.py directory."""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("How to set up Spotify")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._ui_scale = 1.0
        self._resize_for_screen()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._settings = settings or getattr(parent, "settings", None)
        self._dark_mode = self._read_dark_mode()

        self.content = _GuideContent(self._dark_mode)
        self.scroll = QScrollArea(self)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidget(self.content)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollBar:vertical { width: 8px; background: transparent; } QScrollBar::handle:vertical { border-radius: 4px; background: rgba(120,130,145,100); }")

        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(self._button_style())

        self.dashboard_button = QPushButton("Open Spotify Developer Dashboard", self)
        self.dashboard_button.clicked.connect(lambda: webbrowser.open("https://developer.spotify.com/dashboard"))
        self.dashboard_button.setStyleSheet(self._button_style())

        self._layout_for_screen()

    def _resize_for_screen(self):
        """Fit the guide inside the monitor work area so it never hides behind the taskbar."""
        self._ui_scale, width, height = _fit_window_to_work_area(self, 720, 760, margin=0.94)
        self.setMinimumSize(360, 400)
        self.resize(width, height)

    def _layout_for_screen(self):
        s = self._ui_scale
        w, h = self.width(), self.height()

        # Keep a compact header/footer while giving the scroll area all remaining space.
        margin = max(12, int(18 * s))
        footer_h = max(34, int(36 * s))
        footer_gap = max(10, int(12 * s))
        scroll_h = max(120, h - (margin * 2 + footer_h + footer_gap))

        self.scroll.setGeometry(margin, margin, max(100, w - 2 * margin), scroll_h)
        self.dashboard_button.setGeometry(
            max(12, int(30 * s)),
            h - max(36, int(36 * s)) - max(12, int(24 * s)),
            max(180, int(360 * s)),
            footer_h,
        )
        self.close_button.setGeometry(
            w - max(12, int(30 * s)) - max(80, int(100 * s)),
            h - max(36, int(36 * s)) - max(12, int(24 * s)),
            max(80, int(100 * s)),
            footer_h,
        )

        # The guide content is intentionally wider than a narrow screen at its
        # natural size, so the scroll area can scroll vertically and horizontally
        # if Windows gives the application an unusually small work area.
        self.content.setMinimumWidth(max(360, int(680 * s)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "scroll"):
            self._layout_for_screen()

    def _read_dark_mode(self):
        try:
            value = self._settings.get("appearance/dark_mode", False) if self._settings is not None else False
            if isinstance(value, str): return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        except Exception:
            return False

    def _button_style(self):
        if self._dark_mode:
            return """QPushButton { background: rgba(255,255,255,35); color:#f5f8fc; border:1px solid rgba(255,255,255,75); border-radius:12px; font-size:12px; font-weight:600; padding: 2px 14px; } QPushButton:hover { background:rgba(255,255,255,55); }"""
        return """QPushButton { background:rgba(255,255,255,220); color:#151a22; border:1px solid rgba(255,255,255,235); border-radius:12px; font-size:12px; font-weight:600; padding: 2px 14px; } QPushButton:hover { background:rgba(255,255,255,245); }"""

    def paintEvent(self, _event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath(); path.addRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),26,26)
        p.fillPath(path, QColor(25,29,36,242) if self._dark_mode else QColor(245,248,252,242))
        p.setPen(QPen(QColor(255,255,255,85 if self._dark_mode else 240),1)); p.drawPath(path); p.end()


class FirstLaunchSetup(QDialog):
    """First-run Spotify credential setup window."""

    setup_completed = Signal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self._dark_mode = self._read_dark_mode()
        self.setWindowTitle("Cassette Setup")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._ui_scale = 1.0
        self._resize_for_screen()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.client_id = QLineEdit(self)
        self.client_id.setPlaceholderText("Paste your Spotify Client ID")
        self.client_id.setGeometry(*self._sg(36, 214, 488, 48))
        self.client_id.setStyleSheet(self._field_style())

        self.redirect = QLineEdit(self)
        self.redirect.setText(DEFAULT_REDIRECT_URI)
        self.redirect.setGeometry(*self._sg(36, 306, 488, 48))
        self.redirect.setStyleSheet(self._field_style())

        guide = QPushButton("How do I get these?", self)
        guide.setGeometry(*self._sg(36, 398, 180, 38))
        guide.clicked.connect(self._open_guide)
        guide.setStyleSheet(self._secondary_style(self._dark_mode))

        done = QPushButton("Continue", self)
        done.setGeometry(*self._sg(342, 398, 182, 38))
        done.clicked.connect(self._save)
        done.setStyleSheet(self._primary_style(self._dark_mode))

        close = QPushButton("Close", self)
        close.setGeometry(*self._sg(342, 486, 182, 36))
        close.clicked.connect(self.reject)
        close.setStyleSheet(self._secondary_style(self._dark_mode))

        self.gesture_hint = QLabel("Hold Ctrl + Alt, then draw an S with your cursor to open or close Cassette.", self)
        self.gesture_hint.setGeometry(*self._sg(36, 486, 292, 50))
        self.gesture_hint.setWordWrap(True)
        self.gesture_hint.setContentsMargins(4, 3, 4, 3)

        self.status = QLabel("", self)
        self.status.setGeometry(*self._sg(36, 518, 488, 28))
        self.status.setWordWrap(True)
        self.status.setContentsMargins(4, 2, 4, 2)
        self.status.setStyleSheet("color: rgba(190,45,45,220); font-size: 11px;")

        self.dark_mode = QCheckBox("Dark mode", self)
        self.dark_mode.setChecked(self._dark_mode)
        self.dark_mode.setGeometry(*self._sg(36, 356, 180, 30))
        self.dark_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dark_mode.stateChanged.connect(self._dark_mode_changed)
        self._apply_theme()

    def _resize_for_screen(self):
        """Scale the setup window to the usable monitor area, including taskbar-safe bounds."""
        self._ui_scale, width, height = _fit_window_to_work_area(self, 560, 585, margin=0.94)
        self.setMinimumSize(360, 390)
        self.resize(width, height)

    def _sg(self, x, y, w, h):
        s = self._ui_scale
        return (
            int(x * s),
            int(y * s),
            max(1, int(w * s)),
            max(1, int(h * s)),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # If the window is resized by Windows or a DPI change, keep the child
        # controls proportional to the same logical 560x585 design.
        if hasattr(self, "client_id"):
            for widget, geometry in (
                (self.client_id, (36, 214, 488, 48)),
                (self.redirect, (36, 306, 488, 48)),
                (self.dark_mode, (36, 356, 180, 30)),
                (self.gesture_hint, (36, 486, 292, 50)),
                (self.status, (36, 518, 488, 28)),
            ):
                widget.setGeometry(*self._sg(*geometry))

            buttons = self.findChildren(QPushButton)
            if len(buttons) >= 3:
                buttons[0].setGeometry(*self._sg(36, 398, 180, 38))
                buttons[1].setGeometry(*self._sg(342, 398, 182, 38))
                buttons[2].setGeometry(*self._sg(342, 486, 182, 36))

    def _read_dark_mode(self):
        try:
            value = self.settings.get("appearance/dark_mode", False) if self.settings is not None else False
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        except Exception:
            return False

    def _dark_mode_changed(self, state):
        self._dark_mode = bool(state)
        if self.settings is not None:
            self.settings.set("appearance/dark_mode", self._dark_mode)
        self._apply_theme()
        self.update()

    def _apply_theme(self):
        self.client_id.setStyleSheet(self._field_style(self._dark_mode))
        self.redirect.setStyleSheet(self._field_style(self._dark_mode))
        if self._dark_mode:
            self.dark_mode.setStyleSheet("QCheckBox { color: rgba(245,248,252,225); font-size: 13px; font-weight: 600; } QCheckBox::indicator { width: 18px; height: 18px; } QCheckBox::indicator:unchecked { background: rgba(255,255,255,35); border: 1px solid rgba(255,255,255,90); border-radius: 9px; } QCheckBox::indicator:checked { background: rgba(255,255,255,230); border: 1px solid rgba(255,255,255,245); border-radius: 9px; }")
        else:
            self.dark_mode.setStyleSheet("QCheckBox { color: rgba(20,26,34,220); font-size: 13px; font-weight: 600; } QCheckBox::indicator { width: 18px; height: 18px; } QCheckBox::indicator:unchecked { background: rgba(20,26,34,18); border: 1px solid rgba(20,26,34,65); border-radius: 9px; } QCheckBox::indicator:checked { background: rgba(20,26,34,225); border: 1px solid rgba(20,26,34,245); border-radius: 9px; }")
        self.gesture_hint.setStyleSheet(
            "color: rgba(215,220,228,175); font-size: 10px;" if self._dark_mode
            else "color: rgba(60,68,80,165); font-size: 10px;"
        )
        buttons = self.findChildren(QPushButton)
        if len(buttons) >= 2:
            buttons[0].setStyleSheet(self._secondary_style(self._dark_mode))
            buttons[1].setStyleSheet(self._primary_style(self._dark_mode))

    @staticmethod
    def _field_style(dark=False):
        if dark:
            return """QLineEdit { background: rgba(255,255,255,24); color: #f5f8fc; border: 1px solid rgba(255,255,255,65); border-radius: 14px; padding: 0 15px; font-size: 13px; } QLineEdit:focus { border: 1px solid rgba(255,255,255,130); }"""
        return """QLineEdit { background: rgba(255,255,255,210); color: #171c24; border: 1px solid rgba(30,38,48,35); border-radius: 14px; padding: 0 15px; font-size: 13px; } QLineEdit:focus { border: 1px solid rgba(20,26,34,105); }"""

    @staticmethod
    def _primary_style(dark=False):
        if dark:
            return """
        QPushButton { background: rgba(255,255,255,225); color: #151a22; border: 1px solid rgba(255,255,255,245); border-radius: 12px; font-size: 12px; font-weight: 600; padding: 2px 14px; } QPushButton:hover { background: rgba(255,255,255,245); } QPushButton:pressed { background: rgba(225,230,236,230); }
        """
        return """
        QPushButton { background: rgba(20,26,34,225); color: white; border: 1px solid rgba(255,255,255,80); border-radius: 12px; font-size: 12px; font-weight: 600; padding: 2px 14px; }
        QPushButton:hover { background: rgba(35,42,52,245); }
        QPushButton:pressed { background: rgba(10,14,19,245); }
        """

    @staticmethod
    def _secondary_style(dark=False):
        if dark:
            return """QPushButton { background: rgba(255,255,255,32); color: #f5f8fc; border: 1px solid rgba(255,255,255,70); border-radius: 12px; font-size: 12px; font-weight: 600; padding: 2px 14px; } QPushButton:hover { background: rgba(255,255,255,55); }"""
        return """
        QPushButton { background: rgba(255,255,255,180); color: #171c24; border: 1px solid rgba(30,38,48,45); border-radius: 12px; font-size: 12px; font-weight: 600; padding: 2px 14px; }
        QPushButton:hover { background: rgba(255,255,255,225); }
        """

    def _open_guide(self):
        guide = SetupGuideWindow(self, self.settings)
        guide.exec()

    def _save(self):
        client_id = self.client_id.text().strip()
        redirect = self.redirect.text().strip()
        if not client_id:
            self.status.setText("Enter your Spotify Client ID to continue.")
            return
        if not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?/callback/?$", redirect):
            self.status.setText("Redirect URI must be a loopback callback ending in /callback.")
            return

        path = env_file_path()
        try:
            path.write_text(
                "# Cassette Spotify configuration\n"
                f"SPOTIFY_CLIENT_ID={client_id}\n"
                f"REDIRECT_URI={redirect}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self.status.setText(f"Could not save configuration: {exc}")
            return

        self.setup_completed.emit()
        self.accept()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.scale(self._ui_scale, self._ui_scale)
        r = QRectF(1, 1, 560 - 2, 585 - 2)
        path = QPainterPath(); path.addRoundedRect(r, 28, 28)
        p.fillPath(path, QColor(25, 29, 36, 245) if self._dark_mode else QColor(245, 248, 252, 245))
        p.setPen(QPen(QColor(255, 255, 255, 85 if self._dark_mode else 245), 1))
        p.drawPath(path)

        # Large borderless logo area in the top-right. There is deliberately NO
        # backing rectangle/panel here: the transparent pixels of logo.png reveal
        # the exact same themed surface as the rest of the welcome window.
        logo_area = QRectF(332, 28, 196, 150)
        logo = QPixmap(str(app_base_dir() / "logo.png"))
        if not logo.isNull():
            # Preserve native quality whenever possible. Only downscale when the
            # source is larger than the available logo area; never upscale it.
            max_w, max_h = 184, 138
            if logo.width() > max_w or logo.height() > max_h:
                logo = logo.scaled(
                    max_w, max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            x = int(logo_area.center().x() - logo.width() / 2)
            y = int(logo_area.center().y() - logo.height() / 2)
            p.drawPixmap(x, y, logo)

        self._text(p, 36, 35, 280, 38, "Welcome to Cassette", 25, True, QColor(245, 248, 252, 240) if self._dark_mode else QColor(17, 23, 31, 245))
        self._text(p, 36, 75, 480, 50,
                   "Let's connect your Spotify account.\nYou only need to do this once.",
                   12, False, QColor(215, 220, 228, 165) if self._dark_mode else QColor(45, 53, 64, 170))

        self._text(p, 36, 182, 480, 22, "Spotify Client ID", 12, True, QColor(235, 240, 246, 220) if self._dark_mode else QColor(25, 31, 40, 220))
        self._text(p, 36, 274, 480, 22, "Redirect URI", 12, True, QColor(235, 240, 246, 220) if self._dark_mode else QColor(25, 31, 40, 220))
        self._text(p, 36, 548, 488, 27,
                   "Cassette uses Spotify Authorization Code + PKCE.\nNo Client Secret is required.",
                   10, False, QColor(190, 198, 210, 145) if self._dark_mode else QColor(60, 68, 80, 145))
        p.end()

    @staticmethod
    def _text(p, x, y, w, h, text, size, bold, color):
        f = p.font(); f.setPixelSize(size); f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal); p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(x + 4, y + 2, max(0, w - 8), max(0, h - 4)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
