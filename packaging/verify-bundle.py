"""Fail the release build if a Mach-O needs a build-machine library."""
from pathlib import Path
import plistlib
import subprocess

bundle = Path('dist/Multitrack Audio Exporter.app')
with (bundle / 'Contents/Info.plist').open('rb') as handle:
    metadata = plistlib.load(handle)
icon = bundle / 'Contents/Resources' / metadata['CFBundleIconFile']
assert icon.read_bytes() == Path('assets/app-icon.icns').read_bytes(), 'Missing or stale application icon'
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
