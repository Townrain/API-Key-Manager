"""API Key Manager — Unified entry point.

Modes:
    python web.py                  Server mode (headless, port 18001)
    python web.py --desktop        Desktop mode (pywebview GUI)
"""

import sys

from key_manager.web import app

if __name__ == "__main__":
    import os

    _startup_log = []
    def _log(msg):
        _startup_log.append(msg)

    # PyInstaller: chdir to exe directory → all paths stay portable
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.argv[0])
        os.chdir(exe_dir)
        _log(f"chdir to {exe_dir}")

    # PyInstaller --noconsole: stderr/stdout are None, uvicorn crashes on .isatty()
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stdin is None:
        sys.stdin = open(os.devnull)

    # --- Bootstrap: ensure data dirs and config exist ---
    def _bootstrap():
        from pathlib import Path
        # Ensure ./data/ dirs
        for d in ["data", "data/logs", "data/input"]:
            Path(d).mkdir(parents=True, exist_ok=True)
            _log(f"created dir: {d}")
        # Ensure config.yaml exists
        from key_manager.config import load_config
        load_config()
        _log("config.yaml ready")

    try:
        _bootstrap()
    except Exception as e:
        import traceback
        from pathlib import Path
        err = f"Bootstrap failed: {e}\n{traceback.format_exc()}"
        Path("startup_error.log").write_text(err)
        raise

    # --- Bootstrap: ensure data dirs and config exist ---
    def _bootstrap():
        from pathlib import Path
        # Ensure ./data/ dirs
        for d in ["data", "data/logs", "data/input"]:
            Path(d).mkdir(parents=True, exist_ok=True)
        # Ensure config.yaml exists
        from key_manager.config import load_config
        load_config()  # auto-creates config.yaml from bundled example

    try:
        _bootstrap()
    except Exception as e:
        import traceback
        from pathlib import Path
        Path("startup_error.log").write_text(f"Bootstrap failed: {e}\n{traceback.format_exc()}")
        raise
    import argparse

    parser = argparse.ArgumentParser(description="API Key Manager")
    parser.add_argument("--desktop", action="store_true", help="Launch with desktop GUI")
    parser.add_argument("--port", type=int, default=18001, help="Server port (default: 18001)")
    args = parser.parse_args()

    # PyInstaller exe: auto-enable desktop mode if not explicitly disabled
    if getattr(sys, "frozen", False):
        args.desktop = True

    if not args.desktop:
        # ------ Server mode (original behavior) ------
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=args.port)

    else:
        # ------ Desktop mode (pywebview) ------
        import ctypes
        import threading

        import uvicorn

        # --- Single-instance lock (Windows) ---
        MUTEX_NAME = "KeyHub-Desktop-Singleton-v5"
        if sys.platform == "win32":
            ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
            if ctypes.windll.kernel32.GetLastError() == 183:
                # Another instance is running — show a message and exit
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "KeyHub is already running.\nCheck your system tray or taskbar.",
                    "KeyHub",
                    0x40,  # MB_ICONINFORMATION
                )
                sys.exit(0)

        # --- Start server in background thread ---
        host = "127.0.0.1"
        port = args.port

        def _run_server():
            uvicorn.run(app, host=host, port=port, log_level="warning")

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

        _log(f"starting server on {host}:{port}")

        # --- Wait for server to be ready ---
        import time
        import urllib.request
        server_ok = False
        for i in range(30):
            time.sleep(0.5)
            try:
                resp = urllib.request.urlopen(f"http://{host}:{port}/api/stats", timeout=2)
                _log(f"server ready (status {resp.status})")
                server_ok = True
                break
            except Exception as ex:
                _log(f"waiting... ({type(ex).__name__}: {ex})")

        if not server_ok:
            from pathlib import Path
            Path("startup_error.log").write_text("\n".join(_startup_log))
            ctypes.windll.user32.MessageBoxW(
                0,
                "Server failed to start within 15 seconds.\nCheck startup_error.log for details.",
                "KeyHub - Error",
                0x10,
            )
            sys.exit(1)

        # --- Launch native window ---
        try:
            import webview
        except ImportError:
            import webbrowser
            webbrowser.open(f"http://{host}:{port}")
            print(f"pywebview not installed. Opened browser: http://{host}:{port}")
            print("Install with: pip install pywebview")
            input("Press Enter to exit...")
            sys.exit(0)

        _log("opening pywebview window")
        webview.create_window(
            title="KeyHub",
            url=f"http://{host}:{port}",
            width=1280,
            height=800,
            min_size=(960, 640),
            confirm_close=True,
        )
        webview.start()

        # Clean shutdown: pywebview.start() blocks until window closes,
        # daemon thread auto-exits when main thread exits.
        sys.exit(0)
