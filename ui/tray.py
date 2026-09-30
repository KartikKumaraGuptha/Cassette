from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


class TrayController:
    def __init__(self, app, cassette, spotify, tracker, settings):
        self.app = app
        self.cassette = cassette
        self.spotify = spotify
        self.tracker = tracker
        self.settings = settings
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRoundedRect(3, 7, 26, 18, 4, 4)
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawEllipse(8, 11, 8, 8)
        painter.drawEllipse(16, 11, 8, 8)
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(pixmap), app)

        menu = QMenu()
        show = QAction("Show Cassette", menu); show.triggered.connect(cassette.show_at_cursor)
        hide = QAction("Hide Cassette", menu); hide.triggered.connect(cassette.hide_smooth)
        menu.addAction(show); menu.addAction(hide)
        menu.addSeparator()

        self.connection_action = QAction("Spotify Connection…", menu)
        self.connection_action.triggered.connect(self._connect_spotify)
        menu.addAction(self.connection_action)
        self.disconnect_action = QAction("Disconnect Spotify", menu)
        self.disconnect_action.triggered.connect(self._disconnect_spotify)
        menu.addAction(self.disconnect_action)
        self.disconnect_action.setEnabled(False)

        menu.addSeparator()
        quit_ = QAction("Exit", menu); quit_.triggered.connect(app.quit)
        menu.addAction(quit_)
        self.menu = menu
        menu.aboutToShow.connect(self._apply_menu_theme)
        self._apply_menu_theme()
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Cassette — Spotify")
        spotify.connection_changed.connect(self._on_connection_changed)
        spotify.error.connect(self._show_error)
        self._on_connection_changed(spotify.is_connected, spotify.status_text())

    def _apply_menu_theme(self):
        dark = self._as_bool(self.settings.get("appearance/dark_mode", False), False)
        if dark:
            self.menu.setStyleSheet("""QMenu { background: rgba(30,34,42,250); color: #f5f7fa; border: 1px solid rgba(255,255,255,55); padding: 6px; } QMenu::item { padding: 7px 28px 7px 10px; border-radius: 7px; } QMenu::item:selected { background: rgba(255,255,255,28); } QMenu::separator { height: 1px; background: rgba(255,255,255,35); margin: 5px 8px; }""")
        else:
            self.menu.setStyleSheet("""QMenu { background: rgba(248,249,251,250); color: #151a22; border: 1px solid rgba(20,26,34,30); padding: 6px; } QMenu::item { padding: 7px 28px 7px 10px; border-radius: 7px; } QMenu::item:selected { background: rgba(20,26,34,18); } QMenu::separator { height: 1px; background: rgba(20,26,34,22); margin: 5px 8px; }""")

    @staticmethod
    def _as_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _connect_spotify(self):
        self.spotify.connect()

    def _disconnect_spotify(self):
        self.spotify.disconnect()

    def _on_connection_changed(self, connected, message):
        self.disconnect_action.setEnabled(bool(connected))
        self.connection_action.setText("Spotify Connected ✓" if connected else "Spotify Connection…")
        self.tray.setToolTip(f"Cassette — {message}")
        try:
            self.tray.showMessage("Cassette", message, QSystemTrayIcon.MessageIcon.Information, 2500)
        except Exception:
            pass

    def _show_error(self, message):
        try:
            self.tray.showMessage("Cassette — Spotify", message, QSystemTrayIcon.MessageIcon.Warning, 5000)
        except Exception:
            pass

    def show(self):
        self.tray.show()
