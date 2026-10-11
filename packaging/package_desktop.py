"""Archive, extract and validate the actual downloadable desktop package."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

project = Path(__file__).resolve().parent.parent
os.chdir(project)
platform_name = 'Windows' if sys.platform == 'win32' else 'Linux'
executable = 'Second Presence.exe' if sys.platform == 'win32' else 'Second Presence'
output = project/'dist'
staging = output/f'Second Presence - {platform_name}'
if staging.exists():
    shutil.rmtree(staging)
shutil.copytree(output/'Second Presence', staging/'Second Presence')
instructions = ('Extract the entire ZIP, then open Second Presence/Second Presence.exe. '
                'Keep the _internal folder beside the executable. Windows 10/11, x64. '
                'This prototype does not have a publisher certificate.' if sys.platform == 'win32' else
                'Extract the tar.gz archive, then run ./Second\\ Presence/Second\\ Presence. '
                'Linux x86_64, glibc 2.35+ (Ubuntu 22.04 or newer); an X11 or Wayland desktop is required.')
turkish = ('ZIP dosyasını tamamen çıkar; Second Presence klasöründeki Second Presence.exe dosyasını aç. '
           '_internal klasörünü silme veya taşıma.' if sys.platform == 'win32' else
           'tar.gz arşivini çıkar; Second Presence klasöründeki Second Presence uygulamasını çalıştır. '
           'Linux x86_64, glibc 2.35+ ve masaüstü oturumu gerekir.')
(staging/'Read me - Beni oku.txt').write_text(
    f'SECOND PRESENCE / İKİNCİ VARLIK — Prototype 0.9\n\n{instructions}\n\n{turkish}\n\n'
    'No Python installation needed. Python kurulumu gerekmez.\n'
    'L: English / Türkçe. WASD: move, E: panel, P: pause.\n'
    'Contains blood, creature violence and flashing lights.\n'
    'https://knorbay.itch.io/second-presence\nhttps://github.com/knorbay/second-presence\n', encoding='utf-8')
archive = shutil.make_archive(str(output/f'Second-Presence-{platform_name}'),
                              'zip' if sys.platform == 'win32' else 'gztar',
                              root_dir=output, base_dir=staging.name)
with tempfile.TemporaryDirectory() as temporary:
    unpacked = Path(temporary)
    shutil.unpack_archive(archive, unpacked)
    binary = unpacked/staging.name/'Second Presence'/executable
    report = output/f'{platform_name.lower()}-release-verification.json'
    command = [str(binary), '--smoke-test', str(report)]
    subprocess.run(command, cwd=unpacked, check=True, timeout=180)
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['status'] == 'passed' and result['frozen'] is True
    # Exercise a real Windows display / Linux X11 surface as well as dummy SDL.
    window_report = output/f'{platform_name.lower()}-window-verification.json'
    command = [str(binary), '--window-test', str(window_report)]
    if sys.platform != 'win32':
        command = ['xvfb-run', '-a', *command]
    subprocess.run(command, cwd=unpacked, check=True, timeout=180)
    window_result = json.loads(window_report.read_text(encoding='utf-8'))
    assert window_result['status'] == 'passed'
    assert window_result['video_driver'] != 'dummy'
print(archive)
