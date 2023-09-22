# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=[('C:\\Users\\Max\\Desktop\\spiking-tool\\spiker\\Lib\\site-packages\\vgamepad\\win\\vigem\\client\\x64\\ViGEmClient.dll', '.\\vgamepad\\win\\vigem\\client\\x64')],
    datas=[('C:\\Users\\Max\\Desktop\\spiking-tool\\afk\\anti-afk-v2.exe', 'anti-afk-v2.exe'), ('C:\\Users\\Max\\Desktop\\spiking-tool\\update.ps1', 'update.ps1')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)