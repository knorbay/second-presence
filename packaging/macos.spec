# Build with: python -m PyInstaller packaging/macos.spec
from pathlib import Path
import sys
import os
from importlib.util import find_spec

project = Path(SPECPATH).parent
icon = project/'assets/branding/AppIcon.icns'
pygame_root = Path(find_spec('pygame').origin).parent
python_license = Path(sys.base_prefix)/'lib/python3.14/LICENSE.txt'
# This build's SDL2 is sdl2-compat. Its SDL3 dependency is loaded with dlopen,
# so ordinary linked-library discovery cannot see it. Keep the searched name.
sdl3 = Path(os.environ.get('SDL3_BUILD_LIBRARY', '/opt/homebrew/lib/libSDL3.dylib'))
if not sdl3.is_file():
    raise SystemExit('SDL3 is required for this SDL2-compat build. Set SDL3_BUILD_LIBRARY.')
a = Analysis(
    [str(project/'app_entry.py')],
    pathex=[str(project)],
    binaries=[(str(sdl3), '.')],
    datas=[(str(project/'assets'), 'assets'),
           (str(pygame_root/'docs/generated/LGPL.txt'), 'licenses/pygame'),
           (str(python_license), 'licenses/python'),
           (str(project/'packaging/THIRD_PARTY.md'), 'licenses')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'numpy', 'PIL', 'pytest', 'setuptools'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='Second Presence', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    argv_emulation=False, target_arch='arm64', codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Second Presence')
app = BUNDLE(
    collection, name='Second Presence.app', icon=str(icon),
    bundle_identifier='local.secondpresence.game',
    info_plist={
        'CFBundleName': 'Second Presence',
        'CFBundleDisplayName': 'Second Presence',
        'CFBundleShortVersionString': '0.9',
        'CFBundleVersion': '0.9',
        'LSMinimumSystemVersion': '26.0',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.games',
    },
)
