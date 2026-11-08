import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import audio_tools


class BundledToolsTests(unittest.TestCase):
    def test_bundle_never_falls_back_to_homebrew(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(audio_tools.sys, 'frozen', True, create=True), \
                 patch.object(audio_tools.sys, '_MEIPASS', directory, create=True), \
                 patch.object(audio_tools.shutil, 'which', return_value='/opt/homebrew/bin/ffmpeg') as which:
                self.assertIsNone(audio_tools.tool_path('ffmpeg'))
                binary = Path(directory) / 'bin' / 'ffmpeg'
                binary.parent.mkdir()
                binary.touch()
                binary.chmod(0o755)
                self.assertEqual(audio_tools.tool_path('ffmpeg'), str(binary))
                which.assert_not_called()
