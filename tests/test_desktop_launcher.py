"""Native lifecycle regression tests (requires packaging dependencies on macOS)."""
import importlib.util
import sys
import unittest
from unittest.mock import Mock, patch


@unittest.skipUnless(sys.platform == 'darwin' and importlib.util.find_spec('AppKit'),
                     'Requires macOS and the packaging virtual environment')
class DesktopLifecycleTests(unittest.TestCase):
    def setUp(self):
        import desktop
        self.desktop = desktop
        self.delegate = desktop.DesktopDelegate.alloc().init()
        self.delegate.url = 'http://127.0.0.1:8765'
        self.delegate.browser_enabled = True
        self.delegate.cleanup = Mock()

    def test_reopen_opens_existing_url(self):
        with patch.object(self.desktop.webbrowser, 'open') as open_browser:
            for visible in (False, True):
                self.assertTrue(self.delegate.applicationShouldHandleReopen_hasVisibleWindows_(None, visible))
            self.assertEqual(open_browser.call_count, 2)
            open_browser.assert_called_with(self.delegate.url)

    def test_native_termination_cleans_up(self):
        self.assertEqual(self.delegate.applicationShouldTerminate_(None), self.desktop.NSTerminateNow)
        self.delegate.cleanup.assert_called_once_with()

    def test_quit_uses_native_termination(self):
        with patch.object(self.desktop, 'NSApplication') as application:
            self.delegate.quit_(None)
            application.sharedApplication.return_value.terminate_.assert_called_once_with(None)


if __name__ == '__main__':
    unittest.main()
