# Universal Mac package

This distribution is built with Python 3.13.7 universal2, Pygame 2.6.1 from the official cp313 arm64/x86_64 wheels and PyInstaller 6.22.3. It bundles the native SDL2/codec libraries from those wheels, without a Homebrew/SDL3 runtime dependency. Matching native slices are combined with lipo before PyInstaller creates a universal2 application; the wheels' Python source files are checked for byte-for-byte equality.

Python's PSF license and Pygame's LGPL 2.1 license are under `licenses`. The SDL and codec dependency license texts are under `assets/licenses/dependencies`. PyInstaller's bootloader license (GPL with the distribution exception) is under `licenses/pyinstaller`. Font and audio credits/licenses are under `assets/fonts` and `assets/audio`.

Original sources: https://www.python.org/downloads/release/python-3137/ ; https://pypi.org/project/pygame/2.6.1/ ; https://github.com/pygame/pygame/tree/2.6.1/docs/licenses ; https://github.com/pyinstaller/pyinstaller/tree/v6.22.3

The app retains version 0.9 and the provisional Second Presence title. Personal saves/settings are never included. The package is ad-hoc signed and not Apple-notarized. Actual compatibility/architecture audits and runtime results are supplied alongside the distribution, with runtime-tested systems distinguished from declared compatibility.
