# Cassette macOS Build

The recommended macOS build is GitHub Actions. See `GITHUB_MACOS_BUILD.md` for the Windows-to-GitHub workflow.

For a local Mac build, `build_macos.sh` creates `cassette.icns`, builds `Cassette.app`, and opens it.

The app stores its packaged `.env` at:

`~/Library/Application Support/Cassette/.env`

No Spotify Client ID is bundled in this project.
