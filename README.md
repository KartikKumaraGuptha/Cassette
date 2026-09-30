# Cassette — Python-only Spotify Liquid Glass UI

This build is **100% Python/PySide6/QPainter for the UI**. It does **not** use HTML, Qt WebEngine, JavaScript, or WebChannel.

## What was fixed in this revision

- Removed the Windows acrylic implementation that was creating the ugly rectangular/square backdrop around the rounded card.
- Glass is now built from a **pre-captured, blurred desktop backdrop** plus restrained translucent highlights, so the desktop remains visible through the card instead of becoming a grey slab.
- The window is sized to the supplied reference proportions: **510 × 388 px**.
- Header, artwork, progress bar, and bottom controls use fixed reference geometry so they stay aligned.
- Replaced the hand-drawn Spotify mark with a clean three-curve Spotify glyph.
- Reworked shuffle, previous/next, ±10 second, volume, and play/pause icons for consistent stroke weight and spacing.
- Added visible **synced lyrics** over the lower artwork with previous/current/next-line hierarchy.
- Demo lyrics now render correctly.
- Local demo artwork loads directly instead of trying to download a local filesystem path.
- Artwork scaling is cached instead of being rescaled every animation frame.
- Static UI no longer repaints continuously; reel animation runs only while playback is active.
- The desktop backdrop is captured **before** the window is shown, preventing the glass from blurring its own rectangular window surface.

## Spotify setup

On first launch, Cassette opens a one-time setup window asking for:

- **Spotify Client ID**
- **Redirect URI** (pre-filled with `http://127.0.0.1:8888/callback`)

The **How do I get these?** button opens a separate setup guide with reserved screenshot placeholders. Replace those placeholder panels with your screenshots later.

Cassette uses Spotify Authorization Code + PKCE, so no Client Secret is required for the desktop flow. The credentials are saved to a local `.env` file beside the app/executable.

## Run

Double-click `run_spotify.bat`.

For the offline visual test, double-click `run_demo.bat`.

The demo does not require Spotify credentials or internet access.
