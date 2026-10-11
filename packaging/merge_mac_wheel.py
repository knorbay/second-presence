"""Join matching native slices from official Pygame wheels before freezing."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sysconfig
import tempfile
from zipfile import ZipFile


def native(path):
    with path.open('rb') as stream:
        return stream.read(4) in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                                  b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intel-wheel', type=Path, required=True)
    args = parser.parse_args()
    package_root = Path(sysconfig.get_path('purelib'))
    pygame_root = package_root/'pygame'
    with tempfile.TemporaryDirectory(prefix='pygame-wheel-merge-') as directory:
        extracted = Path(directory)
        with ZipFile(args.intel_wheel) as archive:
            for entry in archive.namelist():
                assert not Path(entry).is_absolute() and '..' not in Path(entry).parts
            archive.extractall(extracted)
        # The Python code must be identical across architectures.
        for path in pygame_root.rglob('*.py'):
            other = extracted/path.relative_to(package_root)
            assert other.is_file() and path.read_bytes() == other.read_bytes(), path
        pairs = []
        for path in pygame_root.rglob('*'):
            if not path.is_file() or not native(path):
                continue
            arches = set(subprocess.check_output(['/usr/bin/lipo', '-archs', str(path)], text=True).split())
            if arches == {'arm64', 'x86_64'}:
                continue
            other = extracted/path.relative_to(package_root)
            assert arches == {'arm64'}, path
            if not other.is_file():
                # Some codec ABIs have distinct filenames in the two wheels.
                # Preserve both names; each SDL slice keeps its own dependency.
                assert path.suffix == '.dylib' and '.dylibs' in path.parts, path
                continue
            assert native(other), path
            assert subprocess.check_output(['/usr/bin/lipo', '-archs', str(other)], text=True).strip() == 'x86_64'
            pairs.append((path, other))
        additions = []
        for other in (extracted/'pygame/.dylibs').glob('*.dylib'):
            path = package_root/other.relative_to(extracted)
            if not path.exists():
                assert native(other)
                additions.append((path, other))
        for path, other in pairs:
            merged = path.with_name(path.name+'.universal-build')
            subprocess.run(['/usr/bin/lipo', '-create', str(path), str(other), '-output', str(merged)], check=True)
            subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(merged)],
                           check=True, capture_output=True)
            shutil.copymode(path, merged)
            merged.replace(path)
        for path, other in additions:
            shutil.copy2(other, path)
        print(f'Merged {len(pairs)} Pygame extension/library files; kept {len(additions)} architecture-specific codec files. Python code unchanged.')


if __name__ == '__main__':
    main()
