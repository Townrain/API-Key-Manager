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
            try:
                uvicorn.run(app, host=host, port=port, log_level="warning")
            except Exception:
                import traceback
                from pathlib import Path
                Path("startup_error.log").write_text(
                    "\n".join(_startup_log) + "\n\nServer crashed:\n" + traceback.format_exc()
                )

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

        _log(f"starting server on {host}:{port}")

        # --- Loading page (shown immediately while server starts) ---
        app_url = f"http://{host}:{port}"
        loading_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body{{background:#0a0a0f;color:#00f0ff;font-family:monospace;
        display:flex;align-items:center;justify-content:center;
        height:100vh;margin:0;flex-direction:column;gap:16px}}
  .spinner{{width:40px;height:40px;border:3px solid #1a1a2e;
           border-top:3px solid #00f0ff;border-radius:50%;
           animation:spin 0.8s linear infinite}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body>
<div class="spinner"></div>
<div id="s">KeyHub is starting...</div>
<script>
var n=0;
function p(){{
  n++;
  if(n>60){{document.getElementById('s').innerHTML='Server not responding.<br><small>Check startup_error.log</small>';return}}
  document.getElementById('s').textContent='Starting server... ('+(n/2).toFixed(1)+'s)';
  var i=new Image();
  i.onload=i.onerror=function(){{location.href='{app_url}'}};
  i.src='{app_url}/?'+n;
  setTimeout(p,500);
}}
p();
</script>
</body></html>"""

        # --- Launch native window immediately ---
        try:
            import webview
        except ImportError:
            import webbrowser
            webbrowser.open(app_url)
            print(f"pywebview not installed. Opened browser: {app_url}")
            print("Install with: pip install pywebview")
            input("Press Enter to exit...")
            sys.exit(0)

        _log("opening pywebview window")
        window = webview.create_window(
            title="KeyHub",
            html=loading_html,
            width=1280,
            height=800,
            min_size=(960, 640),
            confirm_close=True,
        )
        webview.start()

        # Clean shutdown: pywebview.start() blocks until window closes,
        # daemon thread auto-exits when main thread exits.
        sys.exit(0)
