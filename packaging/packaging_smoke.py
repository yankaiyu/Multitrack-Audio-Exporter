"""Synthetic self-test executed by the frozen app, with no host FFmpeg."""
import json
from pathlib import Path
import struct
import tempfile
import server
from audio_tools import tool_path, peak_of_audio


def run():
    with tempfile.TemporaryDirectory(prefix='mae-bundle-test-') as directory:
        root = Path(directory)
        data = struct.pack('<4800f', *([4.0] * 4800))
        fmt = struct.pack('<HHIIHH', 3, 1, 48000, 192000, 4, 32)
        (root / 'hot.wav').write_bytes(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<I', 16) + fmt + b'data' + struct.pack('<I', len(data)) + data)
        for format in ('mp3', 'm4a', 'wav'):
            server.JOBS['test'] = {'status': 'running', 'log': '', 'language': 'en'}
            server.convert_job('test', {'source': str(root), 'mode': 'per_track', 'outputFormat': format,
                'wavDepth': 'float32', 'bitrate': '128', 'ceiling': '-2', 'workers': '1'})
            assert server.JOBS['test']['status'] == 'done', server.JOBS['test']['log']
            assert peak_of_audio(root / 'normalized_audio' / ('hot.' + format)) <= -2
        server.JOBS['waves'] = {'status': 'running', 'log': '', 'language': 'en'}
        server.waveform_job('waves', str(root), 'en')
        assert server.JOBS['waves']['status'] == 'done', server.JOBS['waves']['log']
        assert len(server.JOBS['waves']['preview']) == 1
        print(json.dumps({'ok': True, 'ffmpeg': tool_path('ffmpeg'), 'formats': ['mp3', 'm4a', 'wav'], 'waveforms': True}))
