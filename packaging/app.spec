from pathlib import Path
root = Path(SPECPATH).parent
a = Analysis([str(root / 'desktop.py')], pathex=[str(root), str(root / 'packaging')],
    binaries=[(str(root / 'build/vendor/bin/ffmpeg'), 'bin'), (str(root / 'build/vendor/bin/ffprobe'), 'bin')],
    datas=[(str(root / 'web'), 'web'), (str(root / 'build/notices'), 'ThirdParty')],
    hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Multitrack Audio Exporter',
          console=False, target_arch='arm64', codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name='Multitrack Audio Exporter')
app = BUNDLE(coll, name='Multitrack Audio Exporter.app',
    bundle_identifier='com.multitrackaudio.exporter',
    info_plist={'LSUIElement': False, 'LSMinimumSystemVersion': '26.0',
                'CFBundleShortVersionString': '0.1.0', 'CFBundleVersion': '2'})
