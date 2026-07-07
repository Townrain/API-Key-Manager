# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['web.py'],
    pathex=[],
    binaries=[],
    datas=[('key_manager', 'key_manager'), ('templates', 'templates'), ('static', 'static'), ('static_tauri', 'static_tauri'), ('config.yaml.example', '.')],
    hiddenimports=['key_manager.web', 'key_manager.web._app', 'key_manager.web.routes.keys', 'key_manager.web.routes.check', 'key_manager.web.routes.test', 'key_manager.web.routes.balance', 'key_manager.web.routes.models', 'key_manager.web.routes.providers', 'key_manager.web.routes.stats', 'key_manager.web.routes.misc', 'key_manager.web.middleware', 'key_manager.web.progress', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'clr', 'webview.platforms.winforms', 'pythonnet', 'pythonnet.runtime', 'cryptography.hazmat.backends.openssl.backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KeyHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)
