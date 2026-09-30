from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import keyring
import requests
from PySide6.QtCore import QObject, Signal


class _CallbackHandler(BaseHTTPRequestHandler):
    server_version = "CassetteOAuth/1.0"

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        self.server.callback_params = {k: v[0] for k, v in params.items() if v}
        body = (
            "<html><head><meta charset='utf-8'><title>Cassette</title></head>"
            "<body style='font-family:Segoe UI;background:#101114;color:white;text-align:center;padding:60px'>"
            "<h2>Cassette Spotify connection received.</h2>"
            "<p>You can close this browser tab and return to Cassette.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class SpotifyClient(QObject):
    """Spotify Web API client using Authorization Code + PKCE for desktop apps."""

    error = Signal(str)
    connection_changed = Signal(bool, str)

    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_URL = "https://api.spotify.com/v1"
    SCOPES = "user-read-currently-playing user-read-playback-state user-modify-playback-state"
    KEYRING_SERVICE = "Cassette-Spotify"

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.client_id = self._env("SPOTIFY_CLIENT_ID")
        self.redirect_uri = self._env("REDIRECT_URI", "http://127.0.0.1:8888/callback")
        self._token = None
        self._lock = threading.RLock()
        self._auth_thread = None
        self._load_token()

    @staticmethod
    def _env(name: str, default: str = "") -> str:
        value = os.getenv(name, "")
        if value:
            return value.strip()
        # Small built-in .env reader so python-dotenv is not required.
        # Prefer a writable .env beside a packaged executable, then fall back
        # to the source/package directory during development.
        candidates = []
        if getattr(sys, "frozen", False):
            if sys.platform == "darwin":
                candidates.append(Path.home() / "Library" / "Application Support" / "Cassette" / ".env")
            else:
                app_data = os.environ.get("LOCALAPPDATA")
                if app_data:
                    candidates.append(Path(app_data) / "Cassette" / ".env")
        else:
            candidates.append(Path(__file__).resolve().parent.parent / ".env")

        for path in candidates:
            if path.exists():
                try:
                    for line in path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        if key.strip() == name:
                            return value.strip().strip('"').strip("'")
                except OSError:
                    pass

        return default

    @property
    def is_connected(self) -> bool:
        return bool(self._token and self._token.get("refresh_token"))

    def status_text(self) -> str:
        return "Connected to Spotify" if self.is_connected else "Not connected"

    def connect(self):
        if not self.client_id:
            self.error.emit("SPOTIFY_CLIENT_ID is missing from .env")
            return
        if self._auth_thread and self._auth_thread.is_alive():
            return
        self._auth_thread = threading.Thread(target=self._authorize_worker, daemon=True)
        self._auth_thread.start()

    def disconnect(self):
        with self._lock:
            self._token = None
        try:
            keyring.delete_password(self.KEYRING_SERVICE, self.client_id)
        except Exception:
            pass
        self.connection_changed.emit(False, "Disconnected")

    def _authorize_worker(self):
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(24)
        parsed = urllib.parse.urlparse(self.redirect_uri)
        if parsed.hostname not in {"127.0.0.1", "[::1]", "::1"}:
            self.error.emit("Spotify desktop PKCE requires a loopback redirect such as http://127.0.0.1:8888/callback")
            return

        try:
            port = parsed.port or 8888
            server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
            server.timeout = 1
            server.callback_params = None
        except OSError as exc:
            self.error.emit(f"Could not open OAuth callback port {parsed.port or 8888}: {exc}")
            return

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": self.SCOPES,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        try:
            webbrowser.open(url)
            deadline = time.time() + 180
            while time.time() < deadline and server.callback_params is None:
                server.handle_request()
            result = server.callback_params
        finally:
            server.server_close()

        if not result:
            self.error.emit("Spotify login timed out. Choose Spotify Connection → Connect and try again.")
            return
        if result.get("state") != state:
            self.error.emit("Spotify login failed: OAuth state mismatch.")
            return
        if result.get("error"):
            self.error.emit(f"Spotify authorization was not granted: {result['error']}")
            return
        code = result.get("code")
        if not code:
            self.error.emit("Spotify authorization returned no code.")
            return

        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "code_verifier": verifier,
                },
                timeout=15,
            )
            response.raise_for_status()
            token = response.json()
            token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600)) - 30
            self._save_token(token)
            self.connection_changed.emit(True, "Connected to Spotify")
        except Exception as exc:
            self.error.emit(f"Spotify token exchange failed: {exc}")

    def _load_token(self):
        if not self.client_id:
            return
        try:
            raw = keyring.get_password(self.KEYRING_SERVICE, self.client_id)
            if raw:
                self._token = json.loads(raw)
                if self._token.get("refresh_token"):
                    self.connection_changed.emit(True, "Spotify token restored")
        except Exception:
            self._token = None

    def _save_token(self, token):
        with self._lock:
            self._token = token
        try:
            keyring.set_password(self.KEYRING_SERVICE, self.client_id, json.dumps(token))
        except Exception as exc:
            self.error.emit(f"Could not save Spotify token securely: {exc}")

    def _refresh_if_needed(self) -> bool:
        with self._lock:
            token = dict(self._token or {})
        if not token:
            return False
        if int(token.get("expires_at", 0)) > int(time.time()):
            return True
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            return False
        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                },
                timeout=15,
            )
            response.raise_for_status()
            new_token = response.json()
            new_token["refresh_token"] = new_token.get("refresh_token", refresh_token)
            new_token["expires_at"] = int(time.time()) + int(new_token.get("expires_in", 3600)) - 30
            self._save_token(new_token)
            return True
        except Exception as exc:
            self.error.emit(f"Spotify token refresh failed: {exc}")
            return False

    def _request(self, method: str, path: str, **kwargs):
        if not self._refresh_if_needed():
            return None
        with self._lock:
            access = (self._token or {}).get("access_token")
        if not access:
            return None
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {access}"
        response = requests.request(method, self.API_URL + path, headers=headers, timeout=10, **kwargs)
        if response.status_code == 401 and self._refresh_if_needed():
            with self._lock:
                access = (self._token or {}).get("access_token")
            headers["Authorization"] = f"Bearer {access}"
            response = requests.request(method, self.API_URL + path, headers=headers, timeout=10, **kwargs)
        # Spotify playback endpoints commonly return an empty successful body.
        # Never call response.json() on an empty response.
        if response.status_code == 204 or not response.content.strip():
            return {}
        if response.ok:
            try:
                return response.json()
            except ValueError:
                return {}
        if response.status_code in (401, 403):
            self.error.emit(f"Spotify playback request returned {response.status_code}. Make sure Spotify is open and your account supports playback control.")
        elif response.status_code == 429:
            self.error.emit("Spotify rate limit reached; Cassette will retry on the next poll.")
        return None

    def current(self):
        return self._request("GET", "/me/player", params={"additional_types": "track"})

    def album_artwork(self, album_id):
        if not album_id:
            return ""
        data = self._request("GET", f"/albums/{album_id}") or {}
        images = data.get("images") or []
        return images[0].get("url", "") if images else ""

    def pause(self):
        return self._request("PUT", "/me/player/pause")

    def play(self):
        return self._request("PUT", "/me/player/play")

    def next(self):
        return self._request("POST", "/me/player/next")

    def previous(self):
        return self._request("POST", "/me/player/previous")

    def seek(self, ms):
        return self._request("PUT", "/me/player/seek", params={"position_ms": max(0, int(ms))})

    def shuffle(self, state=True):
        return self._request("PUT", "/me/player/shuffle", params={"state": "true" if state else "false"})

    def volume(self, percent):
        return self._request("PUT", "/me/player/volume", params={"volume_percent": max(0, min(100, int(percent)))})
