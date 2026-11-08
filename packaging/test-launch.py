"""Launch the native app and verify resources, Finder reopen and native Quit."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from AppKit import NSRunningApplication, NSApplicationActivationPolicyRegular

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
    log_file = url_file.with_name('desktop.log')
    for _ in range(100):
        if 'Native application ready' in log_file.read_text():
            break
        time.sleep(.1)
    else:
        raise AssertionError('Native application did not finish launching')
    running_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(process.pid)
    assert running_app.activationPolicy() == NSApplicationActivationPolicyRegular, 'App must appear in Dock'
    subprocess.run(['open', '-a', str(binary.parents[2])], check=True)
    for _ in range(100):
        if 'Opening browser interface' in log_file.read_text():
            break
        time.sleep(.1)
    else:
        raise AssertionError('Finder reopen did not reach the running app')
    subprocess.run(['osascript', '-e',
                    'tell application id "com.multitrackaudio.exporter" to quit'], check=True)
    process.wait(timeout=10)
finally:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
assert not url_file.exists(), 'App did not clean up its state'
assert process.returncode == 0, process.returncode
try:
    urllib.request.urlopen(url + '/api/status', timeout=1)
except OSError:
    pass
else:
    raise AssertionError('Server still responds after native Quit')
print('Native startup, Dock policy, bundled resources, Finder reopen and clean native Quit passed.')
