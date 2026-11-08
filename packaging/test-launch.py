"""Launch the real menu app and verify HTTP resources and process shutdown."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

url_file = Path.home() / 'Library/Application Support/Multitrack Audio Exporter/desktop.url'
if url_file.exists():
    try:
        urllib.request.urlopen(url_file.read_text().strip() + '/api/status', timeout=1)
    except OSError:
        url_file.unlink()
    else:
        raise RuntimeError('Close the packaged app before running the launch test.')
binary = Path('dist/Multitrack Audio Exporter.app/Contents/MacOS/Multitrack Audio Exporter').resolve()
process = subprocess.Popen([str(binary), '--no-browser'], env={**os.environ, 'PATH': '/usr/bin:/bin'})
try:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('App exited during startup')
        if url_file.exists():
            break
        time.sleep(.1)
    url = url_file.read_text().strip()
    status = json.load(urllib.request.urlopen(url + '/api/status', timeout=5))
    assert status == {'ffmpeg': True, 'bundled': True}, status
    assert b'convert-form' in urllib.request.urlopen(url, timeout=5).read()
    assert b'previewVolume' in urllib.request.urlopen(url + '/locales/en.json', timeout=5).read()
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
assert not url_file.exists(), 'App did not clean up its state'
assert process.returncode == 0, process.returncode
print('Native app startup, bundled status, web resources and shutdown passed.')
