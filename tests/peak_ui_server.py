"""Private, disposable UI-test server using generated audio only."""
import json
import math
from pathlib import Path
import signal
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from test_audio_pipeline import write_float_wav

with tempfile.TemporaryDirectory(prefix='mae-ui-synthetic-') as temp:
    root = Path(temp)
    folders = []
    for index, count in enumerate((2, 2, 3)):
        folder = root / f'session-{index}'
        folder.mkdir()
        folders.append(str(folder))
        for track in range(count):
            values = [.05 * math.sin(i * .2) for i in range(48000 * 6)] if track == 0 else [0.] * (48000 * 6)
            if track == 0:
                values[144000:144240] = [4.] * 240
            write_float_wav(folder / f'Track{track+1:02}.wav', values)
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    print(json.dumps({'url': f'http://127.0.0.1:{httpd.server_port}', 'folders': folders}), flush=True)
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
