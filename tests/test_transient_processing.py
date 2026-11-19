"""Only synthetic fixtures: float headroom, alignment and preview/export parity."""
import array
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
import json

import server
from transient_processing import validate_transient, reduction_stats
from test_audio_pipeline import write_float_wav, write_stereo_float_wav
from test_peak_processing import job


class TransientValidationTests(unittest.TestCase):
    def test_every_locale_explicitly_translates_new_keys(self):
        reference = {k for k in server.load_locale('en') if k.startswith('transient')}
        for path in server.WEB_ROOT.joinpath('locales').glob('*.json'):
            data = json.loads(path.read_text())
            strings = data.get('overrides', data)
            self.assertTrue(reference <= strings.keys(), path.name)
            self.assertTrue(all(strings[k].strip() for k in reference), path.name)

    def test_invalid_options(self):
        for value in (None, [], {"enabled": "false"}, {"drive": -1}, {"drive": 13},
                      {"drive": float('nan')}, {"drive": float('inf')}, {"drive": None}):
            with self.assertRaises(ValueError):
                validate_transient(value)
        self.assertEqual(validate_transient({}), {"enabled": False, "drive": 0})


@unittest.skipUnless(server.tool_path('ffmpeg'), 'FFmpeg required')
class TransientAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ffmpeg = server.tool_path('ffmpeg')

    def decode(self, path):
        a = array.array('f')
        a.frombytes(subprocess.check_output([self.ffmpeg, '-v', 'error', '-i', str(path), '-f', 'f32le', '-']))
        return a

    def process(self, source, drive, enabled=True):
        output = self.root / f'{uuid.uuid4().hex}.wav'
        server.render_transient(job(), source, output, {"enabled": enabled, "drive": drive})
        return output

    def signal(self):
        values = [.2 * math.sin(i * .1) for i in range(48000)]
        values[24000:24048] = [4.] * 48
        return values

    def test_zero_and_disabled_are_exact_float_bypasses(self):
        source = self.root / 'source.wav'
        write_float_wav(source, self.signal())
        original = self.decode(source)
        for drive, enabled in ((0, True), (12, False)):
            self.assertEqual(self.decode(self.process(source, drive, enabled)), original)

    def test_above_zero_float_is_not_clipped_and_stereo_is_linked(self):
        source = self.root / 'stereo.wav'
        values = self.signal()
        write_stereo_float_wav(source, [(x, x / 2) for x in values])
        original = source.read_bytes()
        output = self.process(source, 6)
        processed = self.decode(output)
        self.assertEqual(len(processed), len(values) * 2)
        self.assertGreater(max(processed), 3.9)  # NOT clipped to 1 before processing.
        self.assertLessEqual(max(processed), 4.00001)
        for i in range(0, len(processed), 2):
            self.assertAlmostEqual(processed[i + 1] * 2, processed[i], places=5)
        self.assertAlmostEqual(processed[10000], values[5000] * 10 ** (.3), places=5)
        stats = reduction_stats(self.ffmpeg, source, output, 2, 6)
        self.assertAlmostEqual(stats['maxReduction'], 6, delta=.05)
        self.assertGreater(stats['limitedPercent'], 0)
        self.assertLess(stats['limitedPercent'], 30)
        self.assertEqual(source.read_bytes(), original)

    def test_scale_invariance_and_sample_alignment(self):
        values = self.signal()
        high, low = self.root / 'high.wav', self.root / 'low.wav'
        write_float_wav(high, values)
        write_float_wav(low, [x / 16 for x in values])
        h, l = self.decode(self.process(high, 12)), self.decode(self.process(low, 12))
        self.assertEqual(len(h), len(values))
        self.assertLess(max(abs(x - y * 16) for x, y in zip(h, l)), 1e-5)
        # Delay compensation must retain the original impulse time.
        self.assertEqual(max(range(len(h)), key=lambda i: h[i]), 24000)

    def test_preview_matches_trimmed_export_with_edits_and_no_preview_gain(self):
        source = self.root / 'source.wav'
        write_float_wav(source, self.signal())
        token = uuid.uuid4().hex
        server.AUDIO_FILES[token] = source
        edits = [{"start": .49, "end": .51, "db": -3}]
        control = {"enabled": True, "drive": 6}
        jid = job()
        server.peak_job(jid, {"tracks": [{"name": source.name, "audio": f'/api/audio/{token}',
                                         "start": .1, "end": .9, "edits": edits, "transient": control}]}, True)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        result = server.JOBS[jid]['results'][0]
        preview = self.decode(server.AUDIO_FILES[result['audio'].split('/')[-1]])
        self.assertEqual(len(preview), 48000)
        self.assertTrue(all(x == 0 for x in preview[:4800]))
        options = dict(source=str(self.root), selectedFiles=[source.name], mode='original', bitrate='256',
                       ceiling='-2', outputFormat='wav', wavDepth='float32', workers='1', enforceSafety=False,
                       applyPreviewGain=False, trimStart='.1', trimEnd='.9',
                       transientControls={source.name: control}, peakEdits={source.name: edits})
        jid = job(); server.convert_job(jid, options)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        exported = self.decode(self.root / 'normalized_audio/source.wav')
        self.assertEqual(exported, preview[4800:43200])
        # Subsequent normalization must still meet the user-selected ceiling.
        options.update(mode='per_track', enforceSafety=True)
        jid = job(); server.convert_job(jid, options)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        self.assertLessEqual(server.peak_of_audio(self.root / 'normalized_audio/source.wav'), -2)

    def test_silence_short_files_and_nonfinite_input(self):
        for values in ([0.] * 48, [4.] * 48, [0., float('nan'), float('inf'), 4.] * 1000):
            source = self.root / 'source.wav'
            write_float_wav(source, values)
            cleaned, _ = server.sanitized_inputs(job(), [source], self.root / 'work', -40, 0, None, 1,
                                                transient_controls={source.name: {"enabled": True, "drive": 12}})
            output = self.decode(cleaned[source])
            self.assertEqual(len(output), len(values))
            self.assertTrue(all(math.isfinite(x) for x in output))
            self.assertLessEqual(max(map(abs, output)), 4.00001)

    def test_flat_top_release_never_ducks_beyond_drive(self):
        # Regression: the former FFmpeg limiter could dip >70 dB immediately
        # after this flat-topped burst. Envelope reduction must stay <= drive.
        values = [.05 * math.sin(i * .2) for i in range(48000)]
        values[24000:24240] = [.1264911] * 240
        source = self.root / 'plateau.wav'
        write_float_wav(source, values)
        output = self.root / 'limited.wav'
        stats = server.render_transient(job(), source, output, {"enabled": True, "drive": 6})
        self.assertAlmostEqual(stats['maxReduction'], 6, delta=.001)
        decoded = self.decode(output)
        self.assertLessEqual(max(map(abs, decoded)), max(map(abs, values)) + 1e-6)
        for a, b in zip(values, decoded):
            if abs(a) > 1e-6:
                self.assertGreaterEqual(b / a, .99999)
        self.assertLess(stats['limitedPercent'], 50)

    def test_last_sample_and_different_rates_stay_aligned(self):
        for rate in (44100, 96000):
            source = self.root / f'{rate}.wav'
            values = [.01] * 1000 + [8.]
            write_float_wav(source, values, rate)
            output = self.decode(self.process(source, 12))
            self.assertEqual(len(output), len(values))
            self.assertAlmostEqual(output[-1], 8., places=4)
            self.assertEqual(max(range(len(output)), key=lambda i: output[i]), 1000)


if __name__ == '__main__':
    unittest.main()
