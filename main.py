import os
import sys
from PySide6.QtWidgets import QApplication

from config.settings import Settings
from spotify.demo import DemoSpotifyClient
from services.playback_monitor import PlaybackMonitor
from services.animation_manager import AnimationManager
from gestures.mouse_tracker import GlobalGestureTracker
from ui.cassette_window import CassetteWindow
from ui.tray import TrayController
from ui.setup_window import FirstLaunchSetup, has_spotify_credentials


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cassette")
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()
    demo_mode = os.getenv("DEMO_MODE", "0").strip() == "1"

    # Real Spotify mode starts with a one-time Apple-style setup window.
    # Demo mode intentionally bypasses credentials.
    first_launch_setup_completed = False
    if not demo_mode and not has_spotify_credentials():
        setup = FirstLaunchSetup(settings=settings)
        if setup.exec() != setup.DialogCode.Accepted or not has_spotify_credentials():
            return 0
        first_launch_setup_completed = True

    if demo_mode:
        spotify = DemoSpotifyClient(settings)
        # Demo tracks already contain local synchronized lyrics.
        lyrics = None
    else:
        from spotify.client import SpotifyClient
        from spotify.lyrics import LyricsClient
        spotify = SpotifyClient(settings)
        lyrics = LyricsClient()

    monitor = PlaybackMonitor(spotify)
    animations = AnimationManager()
    cassette = CassetteWindow(settings, spotify, lyrics, monitor, animations)
    tracker = GlobalGestureTracker(settings)

    tracker.gesture_detected.connect(cassette.toggle_at_cursor)
    tracker.start()
    app.aboutToQuit.connect(tracker.stop)

    tray = TrayController(app, cassette, spotify, tracker, settings)
    tray.show()

    # After the first-launch setup, immediately start Spotify's existing
    # Authorization Code + PKCE flow. Later launches keep the existing
    # token/keyring behavior and do not open the browser automatically.
    if first_launch_setup_completed and not spotify.is_connected:
        spotify.connect()

    monitor.track_changed.connect(cassette.on_track_changed)
    monitor.state_changed.connect(cassette.on_playback_state)
    monitor.position_changed.connect(cassette.on_position)
    monitor.status_changed.connect(cassette.on_player_status)
    monitor.start()

    # Demo mode starts hidden. Use Ctrl+Alt + draw S, or the tray menu.
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
