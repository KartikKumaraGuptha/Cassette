import json
from pathlib import Path
from PySide6.QtCore import QSettings

class Settings:
    def __init__(self):
        self.qs = QSettings("Cassette", "SpotifyCassette")
        # Migrate older gesture tuning so an existing install does not keep
        # the previous large-stroke values.
        if int(self.qs.value("gesture/profile_version", 0) or 0) < 6:
            self.qs.setValue("gesture/threshold", 0.12)
            self.qs.setValue("gesture/min_size", 5.0)
            self.qs.setValue("gesture/timeout_ms", 2800)
            self.qs.setValue("gesture/profile_version", 6)

    def get(self, key, default=None):
        value = self.qs.value(key, default)
        return value

    def set(self, key, value):
        self.qs.setValue(key, value)

    @property
    def gesture_threshold(self):
        return float(self.get("gesture/threshold", 0.12))

    @property
    def gesture_min_size(self):
        return float(self.get("gesture/min_size", 5.0))

    @property
    def gesture_timeout_ms(self):
        return int(self.get("gesture/timeout_ms", 2800))

    @property
    def cassette_scale(self):
        return float(self.get("cassette/scale", 1.0))

    @staticmethod
    def _as_bool(value, default=True):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @property
    def always_on_top(self):
        return self._as_bool(self.get("window/always_on_top", True), True)

    @property
    def lyrics_enabled(self):
        return self._as_bool(self.get("lyrics/enabled", True), True)

    @property
    def reel_enabled(self):
        return self._as_bool(self.get("reels/enabled", True), True)
