"""Keep licenses for the Python packages shipped in the app."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

out = Path('build/notices')
for name in ('pyobjc-core', 'pyobjc-framework-Cocoa', 'pyinstaller'):
    package = distribution(name)
    for file in package.files or []:
        if 'license' in str(file).lower() and Path(str(file)).suffix not in ('.py', '.pyc'):
            source = Path(package.locate_file(file))
            if source.is_file():
                shutil.copy2(source, out / (name + '-' + source.name))
python_license = Path(sys.base_prefix).resolve()
for parent in (python_license, *python_license.parents):
    candidate = parent / 'LICENSE'
    if candidate.is_file():
        shutil.copy2(candidate, out / 'Python-LICENSE.txt')
        break
else:
    raise RuntimeError('Cannot find Python license; include it before distribution.')
