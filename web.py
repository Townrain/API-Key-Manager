"""API Key Manager — Unified entry point.

Modes:
    python web.py                  Server mode (headless, port 18001)
    python web.py --desktop        Desktop mode (pywebview GUI)
"""

import sys

from key_manager.web import app

if __name__ == "__main__":
    import os

    # PyInstaller: chdir to exe directory → all paths stay portable
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.argv[0]))

    # PyInstaller --noconsole: stderr/stdout are None, uvicorn crashes on .isatty()
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stdin is None:
        sys.stdin = open(os.devnull)

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
