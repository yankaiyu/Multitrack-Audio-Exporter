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

import rumps
import server


def main():
    state = Path.home() / "Library/Application Support/Multitrack Audio Exporter"
    state.mkdir(parents=True, exist_ok=True)
    log = (state / "desktop.log").open("w", buffering=1)
    sys.stdout = sys.stderr = log
    lock = (state / "desktop.lock").open("a+")
    url_file = state / "desktop.url"
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if url_file.exists():
            webbrowser.open(url_file.read_text().strip())
        return
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
    app = rumps.App("Multitrack Audio Exporter", title="♫", quit_button=None)
    def quit_app(_):
        cleanup()
        rumps.quit_application()

    signal.signal(signal.SIGTERM, lambda *_: quit_app(None))

    app.menu = [rumps.MenuItem("Open / 打开", callback=lambda _: webbrowser.open(url)),
                rumps.MenuItem("Quit / 退出", callback=quit_app)]
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    app.run()


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        from packaging_smoke import run
        run()
    else:
        main()
