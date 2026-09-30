# Build Cassette.dmg from Windows with GitHub Actions

You do **not** need a Mac on your own PC to run this build. GitHub Actions uses hosted macOS machines to build Cassette.

## One-time setup

1. Create/sign in to a GitHub account.
2. Create a **new repository** on GitHub, for example `Cassette`.
3. On your Windows PC, extract this project ZIP.
4. Upload the contents of `Cassette_Windows_Release` to the GitHub repository.
   - Upload `.github/workflows/build-macos.yml` too.
   - Do **not** upload a real `.env` file containing your Spotify Client ID.
5. On GitHub, open the repository's **Actions** tab.
6. If GitHub asks whether workflows should be enabled, enable them.

## Build with a couple of clicks

1. Open **Actions**.
2. Select **Build Cassette for macOS**.
3. Click **Run workflow**.
4. Leave the version as `1.0.0` (or enter your version).
5. Leave **Create a GitHub Release** off for a normal test build.
6. Click **Run workflow**.

GitHub will build both:

- `Cassette-arm64.dmg` — Apple Silicon Macs (M1/M2/M3/M4/etc.)
- `Cassette-x86_64.dmg` — Intel Macs

It also produces a `.app.zip` for each architecture.

## Download the result

After the workflow finishes:

1. Open the completed workflow run.
2. Scroll to **Artifacts**.
3. Download `Cassette-macOS-arm64` or `Cassette-macOS-x86_64`.
4. Extract the downloaded artifact on Windows.
5. The DMG inside is the file to install on the corresponding Mac.

## Optional: make a GitHub Release

When manually running the workflow, enable **Create a GitHub Release**. The workflow will attach both DMGs and app ZIPs to the release.

Alternatively, create and push a tag such as:

```text
v1.0.0
```

A tagged build automatically attaches the macOS artifacts to that GitHub Release.

## Important

This workflow builds the application, but a Windows PC cannot launch a macOS `.app`. Actual GUI testing still requires access to macOS eventually (for example a friend's Mac or a rented/cloud Mac).

The build does run source compilation and package validation on the macOS runner, including checking that the app bundle and executable exist.

## Spotify credentials

The repository intentionally contains no real Spotify Client ID. `.env.example` keeps it empty:

```env
SPOTIFY_CLIENT_ID=
REDIRECT_URI=http://127.0.0.1:8888/callback
```

Each user enters their own Client ID in Cassette's first-launch setup.
