# Bundled components

- Python 3.14.6 — Python Software Foundation License. Full license included under `licenses/python`.
- Pygame 2.6.1 — LGPL 2.1. Full license included under `licenses/pygame`. Unmodified Python extensions remain separate loadable files. Source: https://github.com/pygame/pygame/tree/2.6.1
- SDL and the codec/font/image libraries included in the Pygame macOS wheel are used without source changes. Pygame's dependency license texts are included under `assets/licenses/dependencies`. Sources: https://github.com/pygame/pygame/tree/2.6.1/docs/licenses
- This build uses SDL2-compat and SDL3. Original licenses/notices for the actual collected libraries and their versions are also included under `assets/licenses/build-dependencies`, with source recipes in `SOURCES.md`.
- PyInstaller 6.22.3 bootloader — GPL with the exception permitting distribution of bundled applications. Source and license: https://github.com/pyinstaller/pyinstaller/tree/v6.22.3
- Barlow Semi Condensed — SIL Open Font License 1.1. Full license and credit included under `assets/fonts`.
- Kenney Sci-fi Sounds, Kenney Impact Sounds and Joth's Infestation in the Control Room — CC0. Source links and licenses under `assets/audio`.

Pillow is a build-only dependency for converting the existing native logo to ICNS and is not bundled in the game.
