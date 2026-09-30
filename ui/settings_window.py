from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QFont
from PySide6.QtWidgets import QDialog, QSlider, QPushButton, QLabel, QCheckBox


class CassetteSettingsDialog(QDialog):
    """Compact Apple-style settings panel with live cassette preview controls."""

    opacity_changed = Signal(float)
    scale_changed = Signal(float)

    def __init__(self, parent, settings, renderer):
        super().__init__(parent)
        self.settings = settings
        self.renderer = renderer
        self.setWindowTitle("Cassette Settings")
        self.setFixedSize(390, 380)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._opacity = float(settings.get("appearance/glass_opacity", 0.82))
        self._scale = float(settings.get("cassette/scale", 1.0))
        self._dark_mode = self._as_bool(settings.get("appearance/dark_mode", False), False)

        self.opacity_slider = self._slider(20, 100, int(round(self._opacity * 100)))
        self.scale_slider = self._slider(72, 135, int(round(self._scale * 100)))
        self.opacity_slider.valueChanged.connect(self._opacity_changed)
        self.scale_slider.valueChanged.connect(self._scale_changed)

        self.opacity_value = self._label(f"{self.opacity_slider.value()}%")
        self.scale_value = self._label(f"{self.scale_slider.value()}%")

        self.dark_mode = QCheckBox("Dark mode", self)
        self.dark_mode.setChecked(self._dark_mode)
        self.dark_mode.setGeometry(24, 246, 342, 32)
        self.dark_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dark_mode.setContentsMargins(4, 2, 4, 2)
        self.dark_mode.stateChanged.connect(self._dark_mode_changed)
        self.close_button = QPushButton("Close", self)
        self.close_button.setGeometry(24, 320, 342, 38)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setContentsMargins(6, 2, 6, 2)
        self.close_button.clicked.connect(self.close)
        self._apply_widget_theme()

    def _slider(self, lo, hi, value):
        s = QSlider(Qt.Orientation.Horizontal, self)
        s.setRange(lo, hi)
        s.setValue(value)
        s.setGeometry(24, 0, 286, 30)
        s.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: rgba(20,26,34,45);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(20,26,34,155);
                border-radius: 2px;
            }
            QSlider::add-page:horizontal {
                background: rgba(255,255,255,125);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 18px;
                margin: -7px 0;
                background: rgba(255,255,255,245);
                border: 1px solid rgba(0,0,0,40);
                border-radius: 9px;
            }
        """)
        return s

    def _label(self, text):
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setContentsMargins(4, 2, 6, 2)
        label.setStyleSheet("color: rgba(20,26,34,190); font-size: 12px; font-weight: 600;")
        label.setGeometry(320, 0, 46, 30)
        return label

    def _opacity_changed(self, value):
        self._opacity = value / 100.0
        self.opacity_value.setText(f"{value}%")
        self.settings.set("appearance/glass_opacity", self._opacity)
        self.renderer.glass_opacity = self._opacity
        self.opacity_changed.emit(self._opacity)
        self.parent().update()

    def _scale_changed(self, value):
        self._scale = value / 100.0
        self.scale_value.setText(f"{value}%")
        self.settings.set("cassette/scale", self._scale)
        self.renderer.ui_scale = self._scale
        self.scale_changed.emit(self._scale)

    @staticmethod
    def _as_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _dark_mode_changed(self, state):
        self._dark_mode = bool(state)
        self.settings.set("appearance/dark_mode", self._dark_mode)
        self._apply_widget_theme()
        self.update()

    def _apply_widget_theme(self):
        if self._dark_mode:
            self.opacity_slider.setStyleSheet(self._slider_style(True))
            self.scale_slider.setStyleSheet(self._slider_style(True))
            self.opacity_value.setStyleSheet("color: rgba(245,248,252,215); font-size: 12px; font-weight: 600;")
            self.scale_value.setStyleSheet("color: rgba(245,248,252,215); font-size: 12px; font-weight: 600;")
            self.dark_mode.setStyleSheet("QCheckBox { color: rgba(245,248,252,225); font-size: 13px; font-weight: 600; } QCheckBox::indicator { width: 18px; height: 18px; } QCheckBox::indicator:unchecked { background: rgba(255,255,255,35); border: 1px solid rgba(255,255,255,90); border-radius: 9px; } QCheckBox::indicator:checked { background: rgba(255,255,255,230); border: 1px solid rgba(255,255,255,245); border-radius: 9px; }")
            self.close_button.setStyleSheet("QPushButton { background: rgba(255,255,255,32); color: #f5f8fc; border: 1px solid rgba(255,255,255,70); border-radius: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background: rgba(255,255,255,55); } QPushButton:pressed { background: rgba(255,255,255,20); }")
        else:
            self.opacity_slider.setStyleSheet(self._slider_style(False))
            self.scale_slider.setStyleSheet(self._slider_style(False))
            self.opacity_value.setStyleSheet("color: rgba(20,26,34,190); font-size: 12px; font-weight: 600;")
            self.scale_value.setStyleSheet("color: rgba(20,26,34,190); font-size: 12px; font-weight: 600;")
            self.dark_mode.setStyleSheet("QCheckBox { color: rgba(20,26,34,220); font-size: 13px; font-weight: 600; } QCheckBox::indicator { width: 18px; height: 18px; } QCheckBox::indicator:unchecked { background: rgba(20,26,34,18); border: 1px solid rgba(20,26,34,65); border-radius: 9px; } QCheckBox::indicator:checked { background: rgba(20,26,34,225); border: 1px solid rgba(20,26,34,245); border-radius: 9px; }")
            self.close_button.setStyleSheet("QPushButton { background: rgba(255,255,255,170); color: #151a22; border: 1px solid rgba(255,255,255,210); border-radius: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background: rgba(255,255,255,205); } QPushButton:pressed { background: rgba(225,230,236,210); }")

    @staticmethod
    def _slider_style(dark):
        if dark:
            return """QSlider::groove:horizontal { height: 5px; background: rgba(255,255,255,38); border-radius: 2px; } QSlider::sub-page:horizontal { background: rgba(255,255,255,190); border-radius: 2px; } QSlider::add-page:horizontal { background: rgba(255,255,255,55); border-radius: 2px; } QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: rgba(255,255,255,245); border: 1px solid rgba(0,0,0,60); border-radius: 9px; }"""
        return """QSlider::groove:horizontal { height: 5px; background: rgba(20,26,34,45); border-radius: 2px; } QSlider::sub-page:horizontal { background: rgba(20,26,34,155); border-radius: 2px; } QSlider::add-page:horizontal { background: rgba(255,255,255,125); border-radius: 2px; } QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: rgba(255,255,255,245); border: 1px solid rgba(0,0,0,40); border-radius: 9px; }"""

    def showEvent(self, event):
        # Position beside the cassette without taking it off screen.
        if self.parent() is not None:
            p = self.parent().frameGeometry()
            target = QPointF(p.right() + 14, p.top()).toPoint()
            screen = self.screen() or self.parent().screen()
            if screen:
                geo = screen.availableGeometry()
                x = min(max(target.x(), geo.left() + 8), geo.right() - self.width() - 8)
                y = min(max(target.y(), geo.top() + 8), geo.bottom() - self.height() - 8)
                self.move(x, y)
        super().showEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)

        # More opaque than Cassette itself: readable settings surface while
        # retaining the same soft, layered Apple-like visual language.
        p.fillPath(path, QColor(25, 29, 36, 242) if self._dark_mode else QColor(245, 248, 252, 224))
        p.setPen(QPen(QColor(255, 255, 255, 85 if self._dark_mode else 235), 1.0))
        p.drawPath(path)
        inner = r.adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 55 if self._dark_mode else 120), 0.6))
        p.drawRoundedRect(inner, 23, 23)

        f = p.font()
        f.setPixelSize(18)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(245, 248, 252, 240) if self._dark_mode else QColor(17, 23, 31, 235))
        p.drawText(QRectF(28, 24, 292, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Cassette Settings")

        f.setPixelSize(11)
        f.setWeight(QFont.Weight.Normal)
        p.setFont(f)
        p.setPen(QColor(215, 220, 228, 165) if self._dark_mode else QColor(45, 53, 64, 165))
        p.drawText(QRectF(28, 54, 332, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Changes apply instantly")

        self._draw_setting_label(p, 91, "Glass opacity")
        self._draw_setting_label(p, 151, "Widget size")

        # Sliders are children, so their positions are assigned here every paint
        # only to keep the layout simple and deterministic.
        self.opacity_slider.move(24, 108)
        self.opacity_value.move(320, 108)
        self.scale_slider.move(24, 168)
        self.scale_value.move(320, 168)
        p.end()

    def _draw_setting_label(self, p, y, text):
        f = p.font()
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(235, 240, 246, 220) if self._dark_mode else QColor(25, 31, 40, 220))
        p.drawText(QRectF(28, y - 20, 282, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
