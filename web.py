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
var startTime = Date.now();
var attempt = 0;
var maxRetries = 120;
function poll() {{
  if (attempt >= maxRetries) {{
    document.getElementById('s').innerHTML = 'Still waiting...<br><button onclick="location.href=\\'{app_url}\\'" style="margin-top:12px;padding:8px 24px;background:#00f0ff;color:#0a0a0f;border:none;border-radius:4px;cursor:pointer;font:inherit">Retry</button>';
    return;
  }}
  var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  document.getElementById('s').textContent = 'Starting server... (' + elapsed + 's)';
  fetch('{app_url}/?r=' + attempt)
    .then(function(r) {{
      if (r.ok || r.status >= 400) {{ location.href = '{app_url}'; }}
      else {{ attempt++; setTimeout(poll, nextDelay()); }}
    }})
    .catch(function() {{ attempt++; setTimeout(poll, nextDelay()); }});
}}
function nextDelay() {{
  var delays = [500, 500, 1000, 1000, 2000, 2000, 4000, 4000];
  return attempt < delays.length ? delays[attempt] : 5000;
}}
poll();
</script>
</body></html>"""

        # --- Launch native window immediately ---
        try:
            import webview
        except ImportError:
            ctypes.windll.user32.MessageBoxW(
                0,
                "WebView2 Runtime is required but not found.\n\n"
                "Download it from:\n"
                "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
                "After installing WebView2, restart KeyHub.",
                "KeyHub - Missing Dependency",
                0x30,
            )
            sys.exit(1)

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
