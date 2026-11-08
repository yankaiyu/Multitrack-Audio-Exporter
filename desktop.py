"""Menu-bar launcher for the self-contained macOS distribution."""
import atexit
import fcntl
from pathlib import Path
import signal
import subprocess
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from AppKit import (NSApplication, NSApplicationActivationPolicyRegular,
                    NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength,
                    NSTerminateNow)
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper
import server


class DesktopDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        print("Native application ready", flush=True)

    def tick_(self, timer):
        # Re-enter Python periodically so pending OS signals are dispatched
        # even when there are no native UI events.
        pass

    def applicationShouldHandleReopen_hasVisibleWindows_(self, application, visible):
        self.openBrowser_(None)
        return True

    def openBrowser_(self, sender):
        print("Opening browser interface", flush=True)
        if self.browser_enabled:
            webbrowser.open(self.url)

    def quit_(self, sender):
        NSApplication.sharedApplication().terminate_(sender)

    def applicationShouldTerminate_(self, application):
        self.cleanup()
        return NSTerminateNow


def native_app(url, cleanup, browser_enabled=True):
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = DesktopDelegate.alloc().init()
    delegate.url = url
    delegate.cleanup = cleanup
    delegate.browser_enabled = browser_enabled
    app.setDelegate_(delegate)

    def menu():
        result = NSMenu.alloc().init()
        for title, action, shortcut in (("Open / 打开", "openBrowser:", "o"),
                                        ("Quit / 退出", "quit:", "q")):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, shortcut)
            item.setTarget_(delegate)
            result.addItem_(item)
        return result

    main_menu = NSMenu.alloc().init()
    app_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Multitrack Audio Exporter", None, "")
    app_item.setSubmenu_(menu())
    main_menu.addItem_(app_item)
    app.setMainMenu_(main_menu)
    status = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    status.button().setTitle_("♫")
    status.setMenu_(menu())
    timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        .5, delegate, "tick:", None, True)
    signal.signal(signal.SIGTERM, lambda *_: AppHelper.callAfter(delegate.quit_, None))
    if browser_enabled:
        AppHelper.callAfter(delegate.openBrowser_, None)
    # Keep the delegate and status item alive for the entire native event loop.
    AppHelper.runEventLoop()
    timer.invalidate()


def main():
    state = Path.home() / "Library/Application Support/Multitrack Audio Exporter"
    state.mkdir(parents=True, exist_ok=True)
    lock = (state / "desktop.lock").open("a+")
    url_file = state / "desktop.url"
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if url_file.exists():
            webbrowser.open(url_file.read_text().strip())
        return
    log = (state / "desktop.log").open("w", buffering=1)
    sys.stdout = sys.stderr = log
    # Prefer a stable origin for browser preferences, but never reuse an
    # unrelated service merely because it happens to occupy the default port.
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", 8765), server.Handler)
    except OSError:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    url = f"http://127.0.0.1:{httpd.server_port}"
    url_file.write_text(url)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    cleaned_up = False

    def cleanup():
        nonlocal cleaned_up
        if cleaned_up:
            return
        cleaned_up = True
        with server.JOBS_LOCK:
            for job in server.JOBS.values():
                job["cancel_requested"] = True
        with server.JOB_PROCESSES_LOCK:
            processes = [p for group in server.JOB_PROCESSES.values() for p in group]
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        httpd.shutdown()
        httpd.server_close()
        url_file.unlink(missing_ok=True)

    atexit.register(cleanup)
    native_app(url, cleanup, browser_enabled="--no-browser" not in sys.argv)


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        from packaging_smoke import run
        run()
    else:
        main()
