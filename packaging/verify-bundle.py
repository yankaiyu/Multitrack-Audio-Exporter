"""Fail the release build if a Mach-O needs a build-machine library."""
from pathlib import Path
import subprocess

bundle = Path('dist/Multitrack Audio Exporter.app')
for path in bundle.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    kind = subprocess.check_output(['file', '-b', str(path)], text=True)
    if 'Mach-O' not in kind:
        continue
    assert 'arm64' in kind, (path, kind)
    libraries = subprocess.check_output(['otool', '-L', str(path)], text=True)
    for line in libraries.splitlines()[1:]:
        library = line.strip().split(' (')[0]
        assert library.startswith(('/System/', '/usr/lib/', '@')), (path, library)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
print('Bundle architecture, library paths and ad-hoc signature verified.')
