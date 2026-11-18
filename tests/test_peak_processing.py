"""Synthetic-only regressions for local edits and cross-folder selections."""
import array
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

import server
from peak_processing import detect_peaks, envelope_filter, suggest_regions, validate_edits
from test_audio_pipeline import write_float_wav, write_stereo_float_wav


def job():
    key = uuid.uuid4().hex
    server.JOBS[key] = {"status": "running", "log": "", "language": "en", "cancel_requested": False}
    return key


class PeakLogicTests(unittest.TestCase):
    def test_isolated_spike_above_zero_is_only_a_suggestion(self):
        peaks = [.1] * 800
        peaks[600] = 4
        result = suggest_regions(peaks, .01, 3, 11)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["time"], 9.005)
        self.assertGreater(result[0]["peak"], 0)
        self.assertLess(result[0]["db"], 0)

    def test_repeated_drums_silence_and_short_files_not_flagged(self):
        for peaks in ([0] * 500, [.1] * 500, [4 if i % 10 == 0 else .1 for i in range(500)], [4]):
            self.assertEqual(suggest_regions(peaks, .01, 0, 5), [])

    def test_long_loud_section_not_an_impact(self):
        peaks = [.1] * 5000
        peaks[100:150] = [4] * 50
        self.assertEqual(suggest_regions(peaks, .01, 0, 50), [])

    def test_invalid_edits_rejected(self):
        for edits in (None, {}, [{"start": -1, "end": 1, "db": -3}],
                      [{"start": 1, "end": 1, "db": -3}],
                      [{"start": 0, "end": 1, "db": 3}],
                      [{"start": 0, "end": 1, "db": float('nan')}],
                      [{"start": 0, "end": 20, "db": -3}]):
            with self.assertRaises(ValueError):
                validate_edits(edits, 10)


@unittest.skipUnless(server.tool_path('ffmpeg'), 'FFmpeg required')
class PeakAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ffmpeg = server.tool_path('ffmpeg')

    def decode(self, path):
        result = subprocess.run([self.ffmpeg, '-v', 'error', '-i', str(path), '-f', 'f32le', '-'], capture_output=True, check=True)
        values = array.array('f'); values.frombytes(result.stdout)
        return values

    def test_waveform_selection_peak_ignores_nonfinite_residue_without_clipping(self):
        source = self.root / 'mixed-float.wav'
        write_float_wav(source, [0., float('nan'), float('inf'), 4.] * 12000)
        jid = job()
        server.waveform_job(jid, str(self.root), 'en')
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        self.assertAlmostEqual(server.JOBS[jid]['preview'][0]['peak'], 20 * math.log10(4), places=4)

    def test_stereo_envelope_preserves_balance_float_range_and_edges(self):
        source = self.root / 'stereo.wav'
        write_stereo_float_wav(source, [(4., 2.)] * 48000)
        before = source.read_bytes()
        edits = [{"start": .2, "end": .4, "db": -20}]
        out = self.root / 'out.wav'
        subprocess.run([self.ffmpeg, '-v', 'error', '-i', str(source), '-af', envelope_filter(2, edits), '-c:a', 'pcm_f32le', str(out)], check=True)
        values = self.decode(out)
        self.assertEqual(len(values), 96000)
        self.assertAlmostEqual(values[0], 4.)
        self.assertAlmostEqual(values[24000], .4, places=5)
        self.assertAlmostEqual(values[24001], .2, places=5)
        self.assertAlmostEqual(values[-2], 4.)
        self.assertEqual(source.read_bytes(), before)
        self.assertLess(abs(values[19202] - values[19200]), .01)

    def test_trim_uses_original_timeline_before_peak_measurement(self):
        source = self.root / 'mono.wav'
        write_float_wav(source, [4.] * 48000)
        jid = job()
        cleaned, _ = server.sanitized_inputs(jid, [source], self.root / 'work', -40, .2, .4, 1,
            peak_edits={source.name: [{"start": .1, "end": .5, "db": -20}]})
        values = self.decode(cleaned[source])
        self.assertEqual(len(values), 9600)
        self.assertAlmostEqual(max(values), .4, places=5)

    def test_detection_and_preview_render_use_registered_sources(self):
        source = self.root / 'spike.wav'
        values = [.1 * math.sin(i * .2) for i in range(48000 * 5)]
        values[144000:144240] = [4.] * 240
        write_float_wav(source, values)
        result = detect_peaks(self.ffmpeg, source, 1, 48000, 0, 5)
        self.assertEqual(len(result), 1)
        self.assertEqual(detect_peaks(self.ffmpeg, source, 1, 48000, 0, 2), [])
        server.AUDIO_FILES['synthetic-test'] = source
        jid = job()
        server.peak_job(jid, {"tracks": [{"name": source.name, "audio": "/api/audio/synthetic-test", "edits": result}]}, True)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        media = server.JOBS[jid]['results'][0]
        rendered = server.AUDIO_FILES[media['audio'].split('/')[-1]]
        self.assertEqual(len(self.decode(rendered)), len(values))
        self.assertLess(server.peak_of_audio(rendered), -10)
        bad = job()
        server.peak_job(bad, {"tracks": [{"name": "no", "audio": str(source)}]})
        self.assertEqual(server.JOBS[bad]['status'], 'error')

    def test_export_applies_edits_even_without_preview_gain(self):
        source = self.root / 'spike.wav'
        write_float_wav(source, [.1] * 20000 + [4.] * 240 + [.1] * 27760)
        options = dict(source=str(self.root), mode='per_track', bitrate='256', ceiling='-2',
                       outputFormat='wav', wavDepth='float32', workers='1', enforceSafety=True,
                       applyPreviewGain=False, peakEdits={source.name: [{"start": .4, "end": .45, "db": -26}]})
        jid = job(); server.convert_job(jid, options)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        values = self.decode(self.root / 'normalized_audio/spike.wav')
        self.assertGreater(values[100], .3)  # Original unedited peak would keep this < .02.
        self.assertLessEqual(server.peak_of_audio(self.root / 'normalized_audio/spike.wav'), -2)

    def test_selection_mask_reused_only_for_matching_track_count_and_split(self):
        for name in ('a.wav', 'b.wav'):
            write_float_wav(self.root / name, [.1] * 1000)
        options = dict(source=str(self.root), mode='original', bitrate='256', ceiling='-2', workers='1',
                       outputFormat='wav', enforceSafety=False, selectionMask={"values": [True, False], "splitStereo": False})
        jid = job(); server.convert_job(jid, options)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        self.assertTrue((self.root / 'normalized_audio/a.wav').exists())
        self.assertFalse((self.root / 'normalized_audio/b.wav').exists())
        options['selectionMask']['values'] = [False]
        jid = job(); server.convert_job(jid, options)
        self.assertEqual(server.JOBS[jid]['status'], 'done', server.JOBS[jid]['log'])
        self.assertTrue((self.root / 'normalized_audio/b.wav').exists())


if __name__ == '__main__':
    unittest.main()
