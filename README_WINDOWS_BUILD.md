# Cassette — one-file Windows release

The intended user-facing deliverable is **one file**:

`Cassette_Setup.exe`

The installer contains the packaged Cassette application, Python runtime, PySide6 and its required Python dependencies. Friends installing Cassette do **not** need Python or pip.

## Easiest way to produce the installer

1. Put this project in a GitHub repository.
2. Push the project, including `.github/workflows/build-windows-installer.yml`.
3. In GitHub, open **Actions → Build Cassette Windows Installer → Run workflow**.
4. Wait for the Windows build to finish.
5. Open the completed workflow run.
6. Download the `Cassette_Setup` artifact.
7. Inside it is the single shareable file:

   `Cassette_Setup.exe`

For a permanent one-file release, create and push a tag such as `v1.0.0`. The workflow will attach `Cassette_Setup.exe` directly to the GitHub Release.

## What the friend does

They only need to run:

`Cassette_Setup.exe`

Then choose Install. Python is not required.

## Assets included

The installer packages the existing application together with:

- `logo.png`
- `s1.png`
- `s2.png`
- `s3.png`
- `s4.png`
- `s5.png`
- existing demo assets

The application's Python source files are not modified by the packaging configuration.
