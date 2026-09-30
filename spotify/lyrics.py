from __future__ import annotations

import requests


class LyricsClient:
    """LRCLIB client with exact-match first, then a conservative search fallback."""

    URL = "https://lrclib.net/api/get"
    SEARCH_URL = "https://lrclib.net/api/search"
    HEADERS = {"User-Agent": "Cassette/1.0 (desktop music companion)"}

    def get(self, artist, title, album="", duration_ms=0):
        duration = round(duration_ms / 1000) if duration_ms else 0
        params = {"artist_name": artist, "track_name": title}
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = duration
        try:
            r = requests.get(self.URL, params=params, headers=self.HEADERS, timeout=8)
            if r.ok:
                result = self._parse_result(r.json())
                if result["synced"] or result["plain"]:
                    return result
        except requests.RequestException:
            pass

        # Duration matching can legitimately fail. Search by title + artist and
        # choose the closest matching result instead of giving up immediately.
        try:
            r = requests.get(
                self.SEARCH_URL,
                params={"track_name": title, "artist_name": artist},
                headers=self.HEADERS,
                timeout=8,
            )
            if r.ok:
                results = r.json() or []
                if results:
                    target = duration or 0
                    results.sort(key=lambda item: abs(float(item.get("duration") or 0) - target) if target else 0)
                    for item in results[:5]:
                        parsed = self._parse_result(item)
                        if parsed["synced"] or parsed["plain"]:
                            return parsed
        except requests.RequestException:
            pass
        return {"synced": [], "plain": ""}

    @classmethod
    def _parse_result(cls, data):
        return {
            "synced": cls.parse_lrc(data.get("syncedLyrics") or ""),
            "plain": data.get("plainLyrics") or "",
        }

    @staticmethod
    def parse_lrc(text):
        lines = []
        for raw in text.splitlines():
            if "]" not in raw:
                continue
            # LRC can contain multiple timestamps on one line.
            parts = raw.split("]")
            lyric = parts[-1].strip()
            for tag in parts[:-1]:
                tag = tag.lstrip("[").strip()
                try:
                    mm, ss = tag.split(":", 1)
                    lines.append((float(mm) * 60 + float(ss), lyric))
                except ValueError:
                    continue
        return sorted(lines)
