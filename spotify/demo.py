from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer


class DemoSpotifyClient(QObject):
    """Local Spotify-like playback simulator used when DEMO_MODE=1."""

    error = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.root = Path(__file__).resolve().parent.parent
        self.tracks = [
            {
                "id": "demo-midnight-drive",
                "title": "Midnight Drive",
                "artist": "Cassette Demo",
                "album": "After Hours",
                "duration": 214000,
                "artwork": str(self.root / "assets" / "demo_art_1.svg"),
                "lyrics": [(0, "City lights are moving slow"), (7, "Windows glow like falling stars"), (14, "We keep driving through the night"), (22, "No destination, just the sound")],
            },
            {
                "id": "demo-summer-static",
                "title": "Summer Static",
                "artist": "Cassette Demo",
                "album": "Polaroid Weather",
                "duration": 198000,
                "artwork": str(self.root / "assets" / "demo_art_2.svg"),
                "lyrics": [(0, "Warm air caught inside the speakers"), (8, "Old songs hiding in the static"), (16, "Every second feels electric"), (25, "Turn it up and let it fade")],
            },
            {
                "id": "demo-neon-rain",
                "title": "Neon Rain",
                "artist": "Cassette Demo",
                "album": "Night Signals",
                "duration": 231000,
                "artwork": str(self.root / "assets" / "demo_art_3.svg"),
                "lyrics": [(0, "Neon rain across the glass"), (9, "Reflections blur and disappear"), (18, "A quiet rhythm in the distance"), (27, "Stay awhile, the morning's near")],
            },
        ]
        self.index = 0
        self.position = 0
        self.playing = True
        self._clock = QTimer(self)
        self._clock.setInterval(100)
        self._clock.timeout.connect(self._advance)
        self._clock.start()

    def _advance(self):
        if not self.playing:
            return
        self.position += 100
        if self.position >= self.tracks[self.index]["duration"]:
            self.next_track()

    def current(self):
        track = self.tracks[self.index]
        return {
            "item": {
                "id": track["id"],
                "name": track["title"],
                "artists": [{"name": track["artist"]}],
                "album": {"name": track["album"], "images": []},
                "duration_ms": track["duration"],
            },
            "progress_ms": self.position,
            "is_playing": self.playing,
        }

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def next_track(self):
        self.index = (self.index + 1) % len(self.tracks)
        self.position = 0

    def previous(self):
        self.index = (self.index - 1) % len(self.tracks)
        self.position = 0

    def seek(self, ms):
        self.position = max(0, min(int(ms), self.tracks[self.index]["duration"]))

    def volume(self, percent):
        # Kept for API compatibility with the real Spotify client.
        return None
