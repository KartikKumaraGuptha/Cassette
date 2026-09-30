from __future__ import annotations

import threading
from PySide6.QtCore import QObject, Signal, QTimer


class PlaybackMonitor(QObject):
    """Non-blocking Spotify playback monitor.

    Network polling runs off the GUI thread so a slow Spotify request can never
    freeze painting, dragging, or control interaction.
    """

    track_changed = Signal(dict)
    state_changed = Signal(bool)
    position_changed = Signal(int)
    status_changed = Signal(str)

    def __init__(self, spotify):
        super().__init__()
        self.spotify = spotify
        self.timer = QTimer(self)
        self.timer.setInterval(900)
        self.timer.timeout.connect(self.poll)
        self.last_id = None
        self.playing = False
        self.position = 0
        self.duration = 0
        self.status = "Connect Spotify"
        self._poll_lock = threading.Lock()
        self._poll_inflight = False

    def start(self):
        self.poll()
        self.timer.start()

    def poll(self):
        # Never overlap HTTP polls. The GUI thread returns immediately.
        with self._poll_lock:
            if self._poll_inflight:
                return
            self._poll_inflight = True
        threading.Thread(target=self._poll_worker, name="CassettePlaybackPoll", daemon=True).start()

    def _poll_worker(self):
        try:
            data = self.spotify.current()
            self._apply_result(data)
        finally:
            with self._poll_lock:
                self._poll_inflight = False

    def _apply_result(self, data):
        if not data:
            status = "Connect Spotify" if not getattr(self.spotify, "is_connected", False) else "Nothing playing"
            self._set_status(status)
            if self.last_id is not None:
                self.last_id = None
                self.playing = False
                self.position = 0
                self.duration = 0
                self.state_changed.emit(False)
            return

        item = data.get("item")
        if not item:
            device = (data.get("device") or {}).get("name")
            self._set_status(f"Ready · {device}" if device else "Nothing playing")
            if self.last_id is not None:
                self.last_id = None
                self.playing = False
                self.position = 0
                self.duration = 0
                self.state_changed.emit(False)
            return

        if item.get("type", "track") != "track":
            self._set_status("Podcast / episode")
            return

        track_id = item.get("id")
        self.position = int(data.get("progress_ms") or 0)
        self.duration = int(item.get("duration_ms") or 0)
        playing = bool(data.get("is_playing"))
        self._set_status("Playing" if playing else "Paused")

        if track_id != self.last_id:
            self.last_id = track_id
            self.track_changed.emit({
                "id": track_id,
                "title": item.get("name", ""),
                "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "album": item.get("album", {}).get("name", ""),
                "album_id": item.get("album", {}).get("id", ""),
                "artwork": (item.get("album", {}).get("images") or [{}])[0].get("url", ""),
                "duration": self.duration,
            })

        if playing != self.playing:
            self.playing = playing
            self.state_changed.emit(playing)
        self.position_changed.emit(self.position)

    def _set_status(self, value):
        if value != self.status:
            self.status = value
            self.status_changed.emit(value)

    def current_position(self):
        return self.position
