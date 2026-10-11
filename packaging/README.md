# macOS build

## Shareable universal package

The newer sharing package is `Second-Presence-Mac-Gorev-Canavar.zip`. It contains one universal2 `.app` for Intel and Apple Silicon, declares macOS 11+, and preserves version 0.9. The actual library minima are audited per CPU, including the arm64-only modplug codec that is referenced only by the arm64 SDL mixer. Every Python extension and the executable have both CPU slices. Dependencies come from the official Pygame wheels rather than the earlier Homebrew SDL2-compat environment.

Build with a Python 3.13 universal2 interpreter on macOS:

```sh
python3.13 -m venv .universal-build-venv
.universal-build-venv/bin/python -m pip install --no-cache-dir --only-binary=:all: pygame==2.6.1 pyinstaller==6.22.3
.universal-build-venv/bin/python -m pip download --no-cache-dir --only-binary=:all: --no-deps --platform macosx_10_13_x86_64 --python-version 313 --implementation cp --abi cp313 --dest intel-wheel pygame==2.6.1
.universal-build-venv/bin/python packaging/merge_mac_wheel.py --intel-wheel intel-wheel/pygame-2.6.1-cp313-cp313-macosx_10_13_x86_64.whl
.universal-build-venv/bin/python -m PyInstaller --noconfirm packaging/macos-universal.spec
```

The merge helper is for an arm64 build host with the native arm64 wheel already installed. It checks matching Python code, joins matching native slices and preserves distinct codec files. PyInstaller builds the final universal2 executable. Do not join already-frozen executables with lipo.

Runtime validation covers Apple Silicon on macOS 27.0.1; Intel and older macOS versions have binary/dependency audits, not physical runtime tests. The package remains ad-hoc signed, without Developer ID/notarization. Send the ZIP as a document; the recipient extracts it with Finder before opening the .app. The included instructions distinguish an Apple developer-verification warning from a CPU/OS mismatch.

## Earlier local Apple Silicon build

The current package targets Apple Silicon (arm64), macOS 26 or later. The working title and version remain Second Presence / 0.9. Python, SDL, Pygame, fonts, audio and asset licenses are included. No personal save files are distributed.

Build on macOS with Python 3.14 and SDL3 available at build time (default `/opt/homebrew/lib/libSDL3.dylib`, or set `SDL3_BUILD_LIBRARY`). The build machine's Pygame uses SDL2-compat, which loads SDL3 dynamically; the spec explicitly collects it. Users of the final app do not need Homebrew or SDL installations.

```sh
python3 -m venv .build-venv
.build-venv/bin/python -m pip install -r packaging/requirements-build.txt
.build-venv/bin/python packaging/make_icon.py
.build-venv/bin/python -m PyInstaller --noconfirm packaging/macos.spec
```

The result is `dist/Second Presence.app`. Do not distribute the adjacent plain executable directory instead of the .app.

Verify the actual bundle from another working directory:

```sh
"/absolute/path/Second Presence.app/Contents/MacOS/Second Presence" --smoke-test /tmp/second-presence-check/result.json
codesign --verify --deep --strict "/absolute/path/Second Presence.app"
```

The explicit smoke check uses dummy SDL devices and a temporary save slot. It decodes every included OGG/MP3, renders both languages, settings, loading, daily lighting and all 12 task panels, then round-trips a partially completed task and settings. It does not alter the player's campaign.

Use `--window-test` instead of `--smoke-test` to run the same checks with a real macOS video surface. This also checks that the native menu scene remains visible with Cocoa's alpha channel. Opaque world canvases explicitly use RGB masks instead of inheriting the window's alpha format.

Finder launches use `~/Library/Application Support/Second Presence` for saves and settings. Source launches retain `.user_data` next to the source. To continue a source campaign in the .app, copy the JSON files from `.user_data` to that Library folder while the game is closed. Logs from a windowed launch are in `~/Library/Logs/Second Presence/game.log`.

The build has a local ad-hoc signature, not a Developer ID signature or Apple notarization. For a public release, rebuild/sign with the publisher's Developer ID and notarize. The minimum is macOS 26 because a collected library requires it; this build is runtime-tested on macOS 27.0.1, not every supported macOS version. To support older versions, rebuild dependencies on the oldest targeted system rather than changing this version declaration.
