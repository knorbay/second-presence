"""Build on Windows x64 or Linux x86_64 using the official Pygame wheel."""
from pathlib import Path
import sys
from importlib.util import find_spec

project = Path(SPECPATH).parent
pygame_root = Path(find_spec('pygame').origin).parent
licenses = [Path(sys.base_prefix)/'LICENSE.txt',
            Path(sys.base_prefix)/f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt']
python_license = next((p for p in licenses if p.is_file()), None)
if python_license is None:
    raise SystemExit('Python license was not found; do not ship without it.')
datas = [(str(project/'assets'), 'assets'),
         (str(pygame_root/'docs/generated/LGPL.txt'), 'licenses/pygame'),
         (str(python_license), 'licenses/python'),
         (str(project/'packaging/DESKTOP-NOTICES.md'), 'licenses')]
a = Analysis([str(project/'app_entry.py')], pathex=[str(project)],
             binaries=[], datas=datas, hiddenimports=[], hookspath=[],
             excludes=['tkinter', 'numpy', 'PIL', 'pytest', 'setuptools'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Second Presence', console=False, debug=False, strip=False, upx=False,
          icon=str(project/'assets/branding/emblem.png') if sys.platform=='win32' else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Second Presence')
