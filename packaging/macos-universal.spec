# Uses the official Pygame 2.6.1 cp313 wheels, merged before freezing.
from pathlib import Path
import sys
from importlib.util import find_spec
from importlib.metadata import distribution

project = Path(SPECPATH).parent
pygame_root = Path(find_spec('pygame').origin).parent
python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
assets = project/'assets'
# Earlier Homebrew-only license notices belong to the earlier build.
data = [(str(path), str(path.relative_to(project).parent))
        for path in assets.rglob('*') if path.is_file()
        and not path.is_relative_to(assets/'licenses/build-dependencies')
        and path.name != 'PyInstaller-COPYING.txt']
data += [(str(pygame_root/'docs/generated/LGPL.txt'), 'licenses/pygame'),
         (str(Path(sys.base_prefix)/f'lib/python{python_version}/LICENSE.txt'), 'licenses/python'),
         (str(project/'packaging/UNIVERSAL-NOTICES.md'), 'licenses')]
installer_license = distribution('pyinstaller').locate_file('pyinstaller-6.22.3.dist-info/licenses/COPYING.txt')
data += [(str(installer_license), 'licenses/pyinstaller')]
a = Analysis([str(project/'app_entry.py')], pathex=[str(project)],
             binaries=[], datas=data, hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['tkinter', 'numpy', 'PIL', 'pytest', 'setuptools'],
             noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Second Presence',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, argv_emulation=False, target_arch='universal2',
          codesign_identity=None, entitlements_file=None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Second Presence')
app = BUNDLE(collection, name='Second Presence.app',
             icon=str(assets/'branding/AppIcon.icns'), bundle_identifier='local.secondpresence.game',
             info_plist={'CFBundleName': 'Second Presence', 'CFBundleDisplayName': 'Second Presence',
                         'CFBundleShortVersionString': '0.9', 'CFBundleVersion': '0.9',
                         'LSMinimumSystemVersion': '11.0', 'NSHighResolutionCapable': True,
                         'LSApplicationCategoryType': 'public.app-category.games'})
