from __future__ import annotations

import os
import time
import threading
import sys

from PySide6.QtCore import QObject, Signal
from pynput import mouse, keyboard

from .s_gesture import s_score


class GlobalGestureTracker(QObject):
    """Global Cassette activation gesture.

    Windows keeps the existing Ctrl+Alt + hand-drawn S gesture.
    macOS uses a double-tap of the Right Command (⌘) key instead.

    The macOS shortcut is intentionally handled from the global keyboard
    listener and does not require a mouse gesture.
    """

    gesture_detected = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.chord = False
        self.points = []
        self.started = 0.0
        self.moved = False
        self.cooldown_until = 0.0
        self._running = False
        self._thread = None
        self._mouse_listener = None
        self._key_listener = None
        try:
            self.mouse_controller = mouse.Controller()
        except Exception:
            self.mouse_controller = None

    def start(self):
        if self._running:
            return
        self._running = True
        if os.name == "nt":
            self._thread = threading.Thread(target=self._windows_poll, name="CassetteGesture", daemon=True)
            self._thread.start()
        else:
            # macOS uses a global keyboard listener for the Right Command
            # double-tap. Linux keeps the existing Ctrl+Alt + S fallback.
            # On macOS, grant Cassette Accessibility/Input Monitoring
            # permission when prompted by System Settings > Privacy & Security.
            self._key_listener = keyboard.Listener(on_press=self._key_down, on_release=self._key_up)
            if sys.platform == "darwin":
                self._mouse_listener = None
            else:
                self._mouse_listener = mouse.Listener(on_move=self._move)
            try:
                self._key_listener.start()
                self._mouse_listener.start()
            except Exception:
                self._key_listener = None
                self._mouse_listener = None
                self._running = False

    def stop(self):
        self._running = False
        for listener in (self._key_listener, self._mouse_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._key_listener = None
        self._mouse_listener = None
        self._thread = None
        self._reset()

    def _begin(self, x, y):
        if self.chord:
            return
        self.chord = True
        self.started = time.monotonic()
        self.points = [(float(x), float(y))]
        self.moved = False

    def _reset(self):
        self.points = []
        self.chord = False

    def _key_down(self, key):
        # macOS: double-tap the physical Right Command key to toggle Cassette.
        if sys.platform == "darwin":
            if key == keyboard.Key.cmd_r:
                now = time.monotonic()
                if now - self._last_right_command_tap <= self._right_command_tap_interval:
                    self._last_right_command_tap = 0.0
                    if now >= self.cooldown_until:
                        self.cooldown_until = now + 0.45
                        self.gesture_detected.emit()
                else:
                    self._last_right_command_tap = now
            return

        # Non-Windows fallback (Linux).
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = True
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = True
        if getattr(self, "ctrl", False) and getattr(self, "alt", False):
            if self.mouse_controller is not None:
                x, y = self.mouse_controller.position
                self._begin(x, y)

    def _key_up(self, key):
        if sys.platform == "darwin":
            return

        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = False
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = False
        if self.chord and not (getattr(self, "ctrl", False) and getattr(self, "alt", False)):
            self._finish()

    def _move(self, x, y):
        if self.chord:
            self._sample(float(x), float(y))

    def _sample(self, x, y):
        now = time.monotonic()
        if now < self.cooldown_until:
            return
        point = (x, y)
        if not self.points:
            self.points.append(point)
            return
        if math_dist(self.points[-1], point) >= 0.8:
            self.moved = True
            if now - self.started > self.settings.gesture_timeout_ms / 1000.0:
                # Keep a held Ctrl+Alt chord usable: restart the stroke at the
                # current cursor position instead of permanently timing it out.
                self._begin(x, y)
                return
            self.points.append(point)

    def _windows_poll(self):
        import ctypes

        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_MENU = 0x12

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        while self._running:
            try:
                ctrl = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                alt = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                pt = POINT()
                if not user32.GetCursorPos(ctypes.byref(pt)):
                    time.sleep(0.005)
                    continue

                if ctrl and alt:
                    if not self.chord:
                        self._begin(pt.x, pt.y)
                    self._sample(float(pt.x), float(pt.y))
                elif self.chord:
                    self._sample(float(pt.x), float(pt.y))
                    self._finish()

            except Exception:
                # Keep the global tracker alive if a transient Win32 call fails.
                pass
            time.sleep(0.005)  # ~200 Hz

    def _finish(self):
        points = self.points
        self._reset()
        if time.monotonic() < self.cooldown_until or len(points) < 6:
            return

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        size = max(width, height)
        if size < self.settings.gesture_min_size:
            return

        path = sum(math_dist(a, b) for a, b in zip(points, points[1:]))
        if path < max(12.0, size * 0.55):
            return

        if s_score(points) >= self.settings.gesture_threshold:
            self.cooldown_until = time.monotonic() + 0.45
            self.gesture_detected.emit()


def math_dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
