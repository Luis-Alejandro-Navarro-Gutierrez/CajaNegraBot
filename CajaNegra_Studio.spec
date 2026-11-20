# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('.env', '.')],
    hiddenimports=['PIL', 'PIL.Image', 'edge_tts', 'groq', 'requests'],
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
    name='CajaNegra_Studio',
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
    icon=['temp_favicon.ico'],
)
