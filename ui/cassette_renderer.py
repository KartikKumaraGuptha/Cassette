from __future__ import annotations

import math
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QPixmap, QImage, QFont,
    QLinearGradient, QRadialGradient,
)


class CassetteRenderer:
    """Direct QPainter rendering for Cassette's live Liquid Glass surface."""

    def __init__(self):
        self.art = QPixmap()
        self._art_scaled = QPixmap()
        self._art_scaled_size = (0, 0)
        self.reel_angle = 0.0
        self.progress = 0.0
        self.playing = False
        self.title = "Nothing playing"
        self.artist = "Connect Spotify"
        self.status = "Connect Spotify"
        self.connected = False
        self.lyrics = []
        self.lyric_index = 0
        self.lyric_line = ""
        self.plain_lyric = ""
        self.volume = 70
        self.duration = 0
        self.art_luma = 0.5
        self.art_text_light = True
        self.art_tint = QColor(145, 170, 195)
        # Estimated backdrop color is sampled from a handful of pixels just
        # outside the widget. It is used only for lyric contrast; the glass
        # itself is still rendered by the live Windows compositor.
        self.backdrop_color = QColor(32, 38, 48)
        self.backdrop_text_light = True
        self.backdrop_tint = QColor(70, 95, 125)
        self.element_color = QColor(248, 250, 253)
        self.element_dim = QColor(225, 231, 238)
        self.element_shadow = QColor(0, 0, 0, 90)
        self.pressed_control = None
        self.ui_scale = 1.0
        self.glass_opacity = 0.82

    def layout(self, rect: QRectF) -> dict[str, object]:
        """Return one shared geometry model for painting and mouse hit testing."""
        r = rect.adjusted(1.0, 1.0, -1.0, -1.0)
        pad = 16.0
        header = QRectF(r.left() + pad, r.top() + 17, r.width() - 2 * pad, 64)
        art = QRectF(r.left() + pad, header.bottom() + 10, r.width() - 2 * pad, 176)
        lyric_pill = QRectF(r.left() + pad, art.bottom() + 8, r.width() - 2 * pad, 44)
        progress_y = lyric_pill.bottom() + 16
        bar_left = r.left() + pad + 39
        bar_right = r.right() - pad - 39
        bar = QRectF(bar_left, progress_y, bar_right - bar_left, 3)
        controls = QRectF(r.left() + pad, r.bottom() - 82, r.width() - 2 * pad, 60)

        left_edge = controls.left() + 39
        right_edge = controls.right() - 39
        step = (right_edge - left_edge) / 6.0
        centers = [left_edge + step * i for i in range(7)]
        volume_center = centers[6] - 4.0
        volume_bar = QRectF(volume_center - 2.0, controls.center().y() - 2.0, 32.0, 4.0)

        slots = []
        for i, cx in enumerate(centers):
            half = step * 0.46
            slots.append(QRectF(cx - half, controls.top() + 4, half * 2, controls.height() - 8))
        # The volume slot owns only the final slot. This avoids the old overlap
        # where the volume hitbox stole the +10 second button.
        return {
            "outer": r,
            "header": header,
            "art": art,
            "lyric_pill": lyric_pill,
            "progress_y": progress_y,
            "bar": bar,
            "controls": controls,
            "centers": centers,
            "slots": slots,
            "volume_bar": volume_bar,
        }

    def paint(self, p: QPainter, rect: QRectF):
        # Render at a fixed reference geometry and scale the complete cassette
        # uniformly. This keeps every control spacing relationship intact while
        # allowing the settings slider to resize the widget in real time.
        scale = max(0.72, min(1.35, float(self.ui_scale)))
        p.save()
        p.scale(scale, scale)
        rect = QRectF(0, 0, 510, 436)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        g = self.layout(rect)
        r: QRectF = g["outer"]
        top: QRectF = g["header"]
        art: QRectF = g["art"]
        controls: QRectF = g["controls"]
        lyric_pill: QRectF = g["lyric_pill"]
        bar: QRectF = g["bar"]
        centers = g["centers"]

        radius = 31.0
        body = QPainterPath()
        body.addRoundedRect(r, radius, radius)

        # Extremely light surface. The live Windows blur is underneath this
        # painter surface; these alpha values deliberately do not make a solid
        # white/grey card.
        p.save()
        p.setClipPath(body)
        # Stronger optical glass: the live DWM blur supplies the actual backdrop
        # diffusion; this translucent layer supplies the visible liquid-glass
        # density and inherits a restrained tint from the current backdrop.
        base = QLinearGradient(r.topLeft(), r.bottomLeft())
        bt = self.backdrop_tint
        oa = max(0.15, min(1.25, float(self.glass_opacity) / 0.82))
        base.setColorAt(0.0, QColor(bt.red(), bt.green(), bt.blue(), int(22 * oa)))
        base.setColorAt(0.30, QColor(255, 255, 255, int(13 * oa)))
        base.setColorAt(0.72, QColor(bt.red(), bt.green(), bt.blue(), int(16 * oa)))
        base.setColorAt(1.0, QColor(255, 255, 255, int(20 * oa)))
        p.fillPath(body, base)
        p.restore()

        # Thin optical rim only. No rectangular background is painted here.
        rim = QLinearGradient(r.topLeft(), r.bottomRight())
        fc = self.element_color
        rim.setColorAt(0.0, QColor(fc.red(), fc.green(), fc.blue(), 175))
        rim.setColorAt(0.24, QColor(fc.red(), fc.green(), fc.blue(), 78))
        rim.setColorAt(0.55, QColor(fc.red(), fc.green(), fc.blue(), 38))
        rim.setColorAt(1.0, QColor(fc.red(), fc.green(), fc.blue(), 128))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(rim, 0.9))
        p.drawPath(body)

        self._glass_panel(p, top, 33, 0.98, self.backdrop_tint)
        self._glass_panel(p, controls, 31, 1.0, self.backdrop_tint)

        # Header.
        spotify_center = QPointF(top.left() + 35, top.center().y())
        self._spotify_mark(p, spotify_center, 20, self.element_color, self.backdrop_tint)
        p.setPen(Qt.PenStyle.NoPen)
        status_color = QColor(43, 211, 107, 245) if self.connected else self._fg(225)
        p.setBrush(status_color)
        p.drawEllipse(QPointF(spotify_center.x() + 23, top.top() + 13), 1.45, 1.45)

        title_rect = QRectF(top.left() + 84, top.top() + 15, top.width() - 168, 18)
        f = p.font(); f.setPixelSize(14); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.setPen(self._fg(242))
        p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._elide(self.title, 42))

        artist_rect = QRectF(top.left() + 88, top.top() + 38, top.width() - 176, 13)
        f.setPixelSize(10); f.setWeight(QFont.Weight.Normal); p.setFont(f)
        p.setPen(self._fg(155))
        p.drawText(artist_rect, Qt.AlignmentFlag.AlignCenter, self._elide(self.artist, 48))
        self._settings_icon(p, QPointF(top.right() - 29, top.center().y()), 9, self._fg(210))

        # Artwork.
        art_path = QPainterPath()
        art_path.addRoundedRect(art, 12, 12)
        p.save(); p.setClipPath(art_path)
        if not self.art.isNull():
            aw, ah = int(art.width()), int(art.height())
            if self._art_scaled.isNull() or self._art_scaled_size != (aw, ah):
                self._art_scaled = self.art.scaled(
                    aw, ah,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._art_scaled_size = (aw, ah)
            sx = max(0, (self._art_scaled.width() - aw) // 2)
            sy = max(0, (self._art_scaled.height() - ah) // 2)
            p.drawPixmap(art, self._art_scaled, QRectF(sx, sy, aw, ah))
        else:
            g0 = QLinearGradient(art.topLeft(), art.bottomRight())
            g0.setColorAt(0, QColor(70, 86, 105, 150))
            g0.setColorAt(1, QColor(25, 32, 42, 155))
            p.fillPath(art_path, g0)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self._fg(105), .75))
        p.drawPath(art_path)

        # Very soft lower readability fade. It is a gradient, not a lyric box.
        fade = QLinearGradient(art.left(), art.bottom() - 66, art.left(), art.bottom())
        fade.setColorAt(0.0, QColor(0, 0, 0, 0))
        fade.setColorAt(0.72, QColor(0, 0, 0, 30))
        fade.setColorAt(1.0, QColor(0, 0, 0, 92))
        p.save(); p.setClipPath(art_path); p.fillRect(art, fade); p.restore()

        # Reels stay vertically centered in the artwork. Lyrics have their own
        # dedicated glass pill below the artwork, so they can never collide with
        # the reels or sit on top of the album image.
        reel_y = art.center().y()
        reel_r = 39.0
        self._reel(p, QPointF(art.left() + 136, reel_y), reel_r, self.reel_angle, self.element_color)
        self._reel(p, QPointF(art.right() - 136, reel_y), reel_r, -self.reel_angle, self.element_color)

        self._draw_lyrics(p, lyric_pill)

        # Progress rail.
        f.setPixelSize(10); f.setWeight(QFont.Weight.Normal); p.setFont(f)
        p.setPen(self._fg(220))
        # Time labels use the same 16 px outer content margin as the artwork and
        # header, instead of hugging the window edge. This keeps the timestamps
        # visually aligned with the rest of the widget.
        time_margin = 16.0
        p.drawText(QRectF(r.left() + time_margin + 2, bar.top() - 7, 34, 13), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._time_text(self.progress, self.duration))
        p.drawText(QRectF(r.right() - time_margin - 36, bar.top() - 7, 34, 13), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._duration_text(self.duration))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._fg(88)); p.drawRoundedRect(bar, 1.5, 1.5)
        a = max(0.0, min(1.0, self.progress))
        filled = QRectF(bar.left(), bar.top(), bar.width() * a, bar.height())
        p.setBrush(self._fg(232)); p.drawRoundedRect(filled, 1.5, 1.5)
        p.drawEllipse(QPointF(bar.left() + bar.width() * a, bar.center().y()), 4.1, 4.1)

        # Reference-style controls: seven equal slots, large glass play button,
        # clean monochrome symbols. No fixed blue tint; the live backdrop shows
        # through the capsule and therefore follows whatever is behind Cassette.
        cy = controls.center().y()
        slot_names = ["shuffle", "back10", "prev", "play", "next", "forward10", "volume"]
        for name, cx in zip(slot_names, centers):
            if self.pressed_control == name:
                slot = g["slots"][slot_names.index(name)]
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._fg(28))
                p.drawRoundedRect(slot.adjusted(3, 5, -3, -5), 20, 20)

        self._draw_shuffle(p, QPointF(centers[0], cy), 9, self.element_color)
        self._draw_seek10(p, QPointF(centers[1], cy), 10, backwards=True, color=self.element_color)
        self._draw_prev(p, QPointF(centers[2], cy), 10, self.element_color)
        self._draw_play_pause(p, QPointF(centers[3], cy), 27, self.playing, self.element_color)
        self._draw_next(p, QPointF(centers[4], cy), 10, self.element_color)
        self._draw_seek10(p, QPointF(centers[5], cy), 10, backwards=False, color=self.element_color)
        self._draw_volume(p, QPointF(centers[6] - 18, cy), 7, self.element_color)

        vb: QRectF = g["volume_bar"]
        self._draw_volume_slider(p, vb, self.volume, self.element_color)
        p.restore()

    def set_artwork(self, pixmap):
        self.art = pixmap
        self._art_scaled = QPixmap()
        self._art_scaled_size = (0, 0)
        self.art_luma = 0.5
        self.art_text_light = True
        self.art_tint = QColor(145, 170, 195)
        if pixmap and not pixmap.isNull():
            img = pixmap.toImage().scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation).convertToFormat(QImage.Format.Format_RGB32)
            total = 0.0; count = 0
            # Pick a stable album-derived tint. Saturated pixels get more weight
            # than neutral blacks/whites so the glass follows the artwork's actual
            # character instead of simply becoming grey.
            weighted_r = weighted_g = weighted_b = weight_sum = 0.0
            for yy in range(img.height()):
                for xx in range(img.width()):
                    c = img.pixelColor(xx, yy)
                    r, g, b = c.red(), c.green(), c.blue()
                    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    total += lum
                    count += 1
                    mx, mn = max(r, g, b), min(r, g, b)
                    sat = (mx - mn) / max(1, mx)
                    # Avoid letting tiny extreme pixels dominate while still
                    # strongly preferring visible album colors.
                    weight = 0.35 + 1.65 * sat
                    if lum < 18 or lum > 245:
                        weight *= 0.45
                    weighted_r += r * weight
                    weighted_g += g * weight
                    weighted_b += b * weight
                    weight_sum += weight
            self.art_luma = (total / max(1, count)) / 255.0
            self.art_text_light = self.art_luma < 0.56
            if weight_sum:
                tr = int(weighted_r / weight_sum)
                tg = int(weighted_g / weight_sum)
                tb = int(weighted_b / weight_sum)
                # Keep the tint slightly lifted so the glass remains translucent
                # and premium rather than becoming a solid saturated panel.
                self.art_tint = QColor(tr, tg, tb)

    @staticmethod
    def _elide(text, limit):
        text = text or ""
        return text if len(text) <= limit else text[:limit - 1] + "…"

    def _fg(self, alpha=255):
        c = self.element_color
        return QColor(c.red(), c.green(), c.blue(), int(alpha))

    def set_backdrop_palette(self, color, text_light):
        """Update the complete UI palette from the live background behind Cassette."""
        c = QColor(color)
        self.backdrop_color = c
        self.backdrop_text_light = bool(text_light)

        # Keep the tint visibly colorful instead of using the raw average, which
        # often becomes muddy grey when several background regions are sampled.
        h, s, v, _ = c.getHsv()
        if h < 0:
            h = 210
        s = max(105, min(220, int(s * 1.45)))
        v = max(38, min(235, int(v * 0.92 + 18)))
        self.backdrop_tint = QColor.fromHsv(h, s, v, 255)

        if self.backdrop_text_light:
            self.element_color = QColor(248, 250, 253)
            self.element_dim = QColor(220, 228, 237)
            self.element_shadow = QColor(0, 0, 0, 105)
        else:
            self.element_color = QColor(18, 24, 32)
            self.element_dim = QColor(38, 46, 56)
            self.element_shadow = QColor(255, 255, 255, 72)

    def _glass_panel(self, p, rect, radius, strength=0.7, tint=None):
        strength *= max(0.15, min(1.25, float(self.glass_opacity) / 0.82))
        path = QPainterPath(); path.addRoundedRect(rect, radius, radius)

        # The lyric pill can inherit a very subtle tint from the album artwork.
        # The alpha stays deliberately low so it remains Liquid Glass rather than
        # turning into a colored opaque card.
        base = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        base.setColorAt(0.0, QColor(255, 255, 255, int(24 * strength)))
        base.setColorAt(.28, QColor(255, 255, 255, int(15 * strength)))
        base.setColorAt(.68, QColor(235, 242, 250, int(12 * strength)))
        base.setColorAt(1.0, QColor(255, 255, 255, int(19 * strength)))
        p.fillPath(path, base)

        bloom = QRadialGradient(QPointF(rect.left() + rect.width() * .18, rect.top() + 1), rect.width() * .72)
        bloom.setColorAt(0.0, QColor(255, 255, 255, int(48 * strength)))
        bloom.setColorAt(.30, QColor(255, 255, 255, int(16 * strength)))
        bloom.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, bloom)

        if tint is not None:
            # Slightly stronger album-derived tint while remaining translucent.
            tg = QLinearGradient(rect.topLeft(), rect.bottomRight())
            tg.setColorAt(0.0, QColor(tint.red(), tint.green(), tint.blue(), int(66 * strength)))
            tg.setColorAt(.45, QColor(tint.red(), tint.green(), tint.blue(), int(42 * strength)))
            tg.setColorAt(1.0, QColor(tint.red(), tint.green(), tint.blue(), int(54 * strength)))
            p.fillPath(path, tg)

        rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, int(165 * strength)))
        rim.setColorAt(.25, QColor(255, 255, 255, int(65 * strength)))
        rim.setColorAt(.65, QColor(255, 255, 255, int(34 * strength)))
        rim.setColorAt(1.0, QColor(255, 255, 255, int(95 * strength)))
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(rim, .85)); p.drawPath(path)
        inner = rect.adjusted(1.0, 1.0, -1.0, -1.0)
        p.setPen(QPen(QColor(255, 255, 255, int(28 * strength)), .45))
        p.drawRoundedRect(inner, max(0, radius - 1), max(0, radius - 1))

    @staticmethod
    def _spotify_mark(p, c, rad, fg, tint):
        dark = sum((tint.red(), tint.green(), tint.blue())) / 3.0 > 132
        disc = QColor(12, 18, 26, 232) if dark else QColor(242, 246, 250, 224)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(disc); p.drawEllipse(c, rad, rad)
        pen = QPen(fg, 1.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        for y, spread, lift in [(-5.0, 10.2, -1.6), (0.0, 8.6, -1.0), (4.4, 6.8, -.6)]:
            path = QPainterPath(); path.moveTo(c.x() - spread, c.y() + y)
            path.cubicTo(c.x() - spread*.35, c.y() + y + lift, c.x() + spread*.30, c.y() + y + lift, c.x() + spread, c.y() + y + 1.0)
            p.drawPath(path)

    @staticmethod
    def _settings_icon(p, c, r, color):
        """Small Apple-style gear used in the header settings slot."""
        p.save()
        p.setPen(QPen(color, 1.45, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, r * 0.56, r * 0.56)
        for i in range(8):
            a = math.radians(i * 45)
            inner = r * 0.73
            outer = r * 1.03
            p.drawLine(
                QPointF(c.x() + math.cos(a) * inner, c.y() + math.sin(a) * inner),
                QPointF(c.x() + math.cos(a) * outer, c.y() + math.sin(a) * outer),
            )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(c, r * 0.18, r * 0.18)
        p.restore()

    @staticmethod
    def _reel(p, c, rad, angle, fg):
        """Glass cassette reel: transparent body, optical rim, rotating spokes."""
        p.save(); p.translate(c); p.rotate(angle)

        # Shadow/refraction halo lets the album artwork remain visible through it.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 35)); p.drawEllipse(QPointF(1.2, 2.0), rad + 1.7, rad + 1.7)

        outer = QRadialGradient(QPointF(-rad * .28, -rad * .32), rad * 1.18)
        outer.setColorAt(0.0, QColor(fg.red(), fg.green(), fg.blue(), 62))
        outer.setColorAt(.38, QColor(fg.red(), fg.green(), fg.blue(), 28))
        outer.setColorAt(.72, QColor(fg.red(), fg.green(), fg.blue(), 18))
        outer.setColorAt(1.0, QColor(fg.red(), fg.green(), fg.blue(), 5))
        p.setBrush(outer); p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 165), 1.0)); p.drawEllipse(QPointF(0, 0), rad, rad)

        # Recessed glass/tape center. Low alpha is intentional: artwork shows
        # through the reel instead of being replaced by a dark solid disc.
        inner = QRadialGradient(QPointF(-rad * .2, -rad * .24), rad * .83)
        inner.setColorAt(0.0, QColor(20, 30, 44, 48))
        inner.setColorAt(.55, QColor(8, 18, 31, 30))
        inner.setColorAt(1.0, QColor(fg.red(), fg.green(), fg.blue(), 8))
        p.setBrush(inner); p.setPen(QPen(QColor(255, 255, 255, 76), .7)); p.drawEllipse(QPointF(0, 0), rad * .79, rad * .79)

        # Rotating optical spokes.
        p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 80), .65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(math.cos(a) * rad * .18, math.sin(a) * rad * .18), QPointF(math.cos(a) * rad * .67, math.sin(a) * rad * .67))

        hub = QRadialGradient(QPointF(-rad * .08, -rad * .10), rad * .24)
        hub.setColorAt(0.0, QColor(fg.red(), fg.green(), fg.blue(), 100)); hub.setColorAt(.42, QColor(fg.red(), fg.green(), fg.blue(), 55)); hub.setColorAt(1.0, QColor(15, 25, 38, 75))
        p.setBrush(hub); p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 110), .55)); p.drawEllipse(QPointF(0, 0), rad * .20, rad * .20)
        p.setBrush(QColor(20, 30, 42, 95)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(0, 0), rad * .075, rad * .075)

        # Moving specular streak + stationary rim glint.
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 155), 1.25))
        p.drawArc(QRectF(-rad * .91, -rad * .91, rad * 1.82, rad * 1.82), 28 * 16, 108 * 16)
        p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 70), .7))
        p.drawArc(QRectF(-rad * .78, -rad * .78, rad * 1.56, rad * 1.56), 205 * 16, 70 * 16)
        p.restore()

    @staticmethod
    def _draw_play_pause(p, c, r, playing, color):
        """Reference glass play/pause orb, recolored by the live backdrop palette."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Same achromatic glass construction as the supplied control, but using
        # the dynamic foreground color so it flips with the background.
        hi = QColor(color.red(), color.green(), color.blue(), 140)
        mid = QColor(color.red(), color.green(), color.blue(), 80)
        low = QColor(color.red(), color.green(), color.blue(), 90)
        edge = QColor(color.red(), color.green(), color.blue(), 180)
        icon = QColor(color.red(), color.green(), color.blue(), 240)

        grad = QRadialGradient(c.x() - r * 0.2, c.y() - r * 0.2, r * 1.2)
        grad.setColorAt(0.0, hi)
        grad.setColorAt(0.3, mid)
        grad.setColorAt(0.7, low)
        grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 120))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(edge, 1.2))
        p.drawEllipse(QRectF(c.x() - r, c.y() - r, r * 2, r * 2).adjusted(1, 1, -1, -1))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(icon)
        if playing:
            bar_w, bar_h = 4.0, 16.0
            gap = 5.0
            x1 = c.x() - bar_w - gap / 2.0
            x2 = c.x() + gap / 2.0
            y = c.y() - bar_h / 2.0
            p.drawRoundedRect(QRectF(x1, y, bar_w, bar_h), 2, 2)
            p.drawRoundedRect(QRectF(x2, y, bar_w, bar_h), 2, 2)
        else:
            path = QPainterPath()
            path.moveTo(c.x() - 5, c.y() - 9)
            path.lineTo(c.x() + 9, c.y())
            path.lineTo(c.x() - 5, c.y() + 9)
            path.closeSubpath()
            p.drawPath(path)
        p.restore()

    @staticmethod
    def _draw_shuffle(p, c, s, color):
        """Reference shuffle icon with both crossing paths and arrowheads."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(color.red(), color.green(), color.blue(), 240)
        pen = QPen(col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        p1 = QPainterPath()
        p1.moveTo(c.x() - s, c.y() + s * .60)
        p1.cubicTo(c.x() - s * .30, c.y() + s * .60, c.x() + s * .30, c.y() - s * .60, c.x() + s, c.y() - s * .60)
        p.drawPath(p1)
        p.drawLine(QPointF(c.x() + s * .60, c.y() - s * .90), QPointF(c.x() + s, c.y() - s * .60))
        p.drawLine(QPointF(c.x() + s * .60, c.y() - s * .30), QPointF(c.x() + s, c.y() - s * .60))

        p2 = QPainterPath()
        p2.moveTo(c.x() - s, c.y() - s * .60)
        p2.cubicTo(c.x() - s * .30, c.y() - s * .60, c.x() + s * .30, c.y() + s * .60, c.x() + s, c.y() + s * .60)
        p.drawPath(p2)
        p.drawLine(QPointF(c.x() + s * .60, c.y() + s * .30), QPointF(c.x() + s, c.y() + s * .60))
        p.drawLine(QPointF(c.x() + s * .60, c.y() + s * .90), QPointF(c.x() + s, c.y() + s * .60))
        p.restore()

    @staticmethod
    def _draw_seek10(p, c, s, backwards, color):
        """Reference circular 10-second seek control."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(color.red(), color.green(), color.blue(), 240)
        pen = QPen(col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc_rect = QRectF(c.x() - s * 1.1, c.y() - s * 1.1, s * 2.2, s * 2.2)

        if backwards:
            start_angle = 230 * 16
            span_angle = -300 * 16
            p.drawArc(arc_rect, start_angle, span_angle)
            arrow = QPainterPath()
            arrow.moveTo(c.x() - s * .55, c.y() - s * 1.30)
            arrow.lineTo(c.x() - s * 1.05, c.y() - s * .75)
            arrow.lineTo(c.x() - s * .45, c.y() - s * .60)
            p.drawPath(arrow)
        else:
            start_angle = -50 * 16
            span_angle = 300 * 16
            p.drawArc(arc_rect, start_angle, span_angle)
            arrow = QPainterPath()
            arrow.moveTo(c.x() + s * .55, c.y() - s * 1.30)
            arrow.lineTo(c.x() + s * 1.05, c.y() - s * .75)
            arrow.lineTo(c.x() + s * .45, c.y() - s * .60)
            p.drawPath(arrow)

        font = QFont("Arial", 7, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(col)
        p.drawText(QRectF(c.x() - s, c.y() - s * .55, s * 2, s * 1.1), Qt.AlignmentFlag.AlignCenter, "10")
        p.restore()

    @staticmethod
    def _draw_prev(p, c, s, color):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(color.red(), color.green(), color.blue(), 240)
        p.setPen(QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() - s * .70, c.y() - s * .70), QPointF(c.x() - s * .70, c.y() + s * .70))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        path = QPainterPath()
        path.moveTo(c.x() - s * .50, c.y())
        path.lineTo(c.x() + s * .70, c.y() - s * .70)
        path.lineTo(c.x() + s * .70, c.y() + s * .70)
        path.closeSubpath()
        p.drawPath(path)
        p.restore()

    @staticmethod
    def _draw_next(p, c, s, color):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(color.red(), color.green(), color.blue(), 240)
        p.setPen(QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() + s * .70, c.y() - s * .70), QPointF(c.x() + s * .70, c.y() + s * .70))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        path = QPainterPath()
        path.moveTo(c.x() + s * .50, c.y())
        path.lineTo(c.x() - s * .70, c.y() - s * .70)
        path.lineTo(c.x() - s * .70, c.y() + s * .70)
        path.closeSubpath()
        p.drawPath(path)
        p.restore()

    @staticmethod
    def _draw_volume(p, c, s, color):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(color.red(), color.green(), color.blue(), 240)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        spk_path = QPainterPath()
        spk_path.moveTo(c.x() - s, c.y() - s * .38)
        spk_path.lineTo(c.x() - s * .38, c.y() - s * .38)
        spk_path.lineTo(c.x() + s * .45, c.y() - s)
        spk_path.lineTo(c.x() + s * .45, c.y() + s)
        spk_path.lineTo(c.x() - s * .38, c.y() + s * .38)
        spk_path.lineTo(c.x() - s, c.y() + s * .38)
        spk_path.closeSubpath()
        p.drawPath(spk_path)

        pen = QPen(col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc1 = QRectF(c.x() - s * .50, c.y() - s * .50, s, s)
        p.drawArc(arc1, -50 * 16, 100 * 16)
        arc2 = QRectF(c.x() - s * .75, c.y() - s * .875, s * 1.75, s * 1.75)
        p.drawArc(arc2, -50 * 16, 100 * 16)
        p.restore()

    @staticmethod
    def _draw_volume_slider(p, bar, volume, color):
        """Reference CustomSlider styling, fitted into the existing volume slot."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        handle_radius = 4.5
        track_height = 3.0
        track_x = bar.left()
        track_w = bar.width()
        track_y = bar.center().y() - track_height / 2.0
        fraction = max(0.0, min(1.0, volume / 100.0))
        handle_cx = track_x + fraction * track_w

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 60))
        p.drawRoundedRect(QRectF(track_x, track_y, track_w, track_height), 1.5, 1.5)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 220))
        active_w = handle_cx - track_x
        if active_w > 0:
            p.drawRoundedRect(QRectF(track_x, track_y, active_w, track_height), 1.5, 1.5)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 255))
        p.drawEllipse(QRectF(handle_cx - handle_radius, bar.center().y() - handle_radius, handle_radius * 2, handle_radius * 2))
        p.restore()

    def _draw_lyrics(self, p, pill):
        """Render previous/current/next lyrics inside a softly album-tinted glass pill."""
        active = (self.lyric_line or self.plain_lyric or "").strip()
        if not active:
            return

        previous = ""
        following = ""
        if self.lyrics:
            i = max(0, min(self.lyric_index, len(self.lyrics) - 1))
            if i > 0:
                previous = self.lyrics[i - 1][1].strip()
            if i + 1 < len(self.lyrics):
                following = self.lyrics[i + 1][1].strip()

        # The pill borrows a restrained amount of the album's dominant color,
        # but lyric contrast follows the live backdrop behind the widget rather
        # than the album art.
        self._glass_panel(p, pill, 18, 0.88, self.art_tint)

        if self.backdrop_text_light:
            prev_c = self._fg(130)
            active_c = self._fg(245)
            next_c = self._fg(112)
            shadow = QColor(0, 0, 0, 95)
        else:
            prev_c = self._fg(145)
            active_c = self._fg(235)
            next_c = self._fg(125)
            shadow = QColor(255, 255, 255, 70)

        x = pill.left() + 22
        w = pill.width() - 44
        p.save()

        # Three states have explicit vertical margins so they remain separated.
        if previous:
            f = p.font(); f.setPixelSize(8); f.setWeight(QFont.Weight.Normal); p.setFont(f)
            p.setPen(QPen(shadow, 1.8))
            p.drawText(QRectF(x, pill.top() + 4, w, 8), Qt.AlignmentFlag.AlignCenter, self._elide(previous, 76))

        f = p.font(); f.setPixelSize(12); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.setPen(QPen(shadow, 2.0))
        p.drawText(QRectF(x, pill.top() + 15, w, 14), Qt.AlignmentFlag.AlignCenter, self._elide(active, 62))

        if following:
            f = p.font(); f.setPixelSize(8); f.setWeight(QFont.Weight.Normal); p.setFont(f)
            p.setPen(QPen(shadow, 1.6))
            p.drawText(QRectF(x, pill.top() + 32, w, 8), Qt.AlignmentFlag.AlignCenter, self._elide(following, 76))

        if previous:
            f = p.font(); f.setPixelSize(8); f.setWeight(QFont.Weight.Normal); p.setFont(f)
            p.setPen(prev_c)
            p.drawText(QRectF(x, pill.top() + 4, w, 8), Qt.AlignmentFlag.AlignCenter, self._elide(previous, 76))

        f = p.font(); f.setPixelSize(12); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.setPen(active_c)
        p.drawText(QRectF(x, pill.top() + 15, w, 14), Qt.AlignmentFlag.AlignCenter, self._elide(active, 62))

        if following:
            f = p.font(); f.setPixelSize(8); f.setWeight(QFont.Weight.Normal); p.setFont(f)
            p.setPen(next_c)
            p.drawText(QRectF(x, pill.top() + 32, w, 8), Qt.AlignmentFlag.AlignCenter, self._elide(following, 76))
        p.restore()

    @staticmethod
    def _time_text(progress,duration): return CassetteRenderer._fmt(max(0,int(progress*duration)))
    @staticmethod
    def _duration_text(duration): return CassetteRenderer._fmt(max(0,int(duration)))
    @staticmethod
    def _fmt(ms):
        s=int(ms/1000); return f"{s//60}:{s%60:02d}"
