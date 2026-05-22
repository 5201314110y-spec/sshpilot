# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SSHPilot single-file Windows exe.

Build with:  pyinstaller sshpilot.spec
Produces:    dist/SSHPilot.exe
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# These libraries load things dynamically; PyInstaller can't see them statically.
hiddenimports = []
hiddenimports += collect_submodules("asyncssh")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anthropic")
hiddenimports += collect_submodules("aiosqlite")
hiddenimports += collect_submodules("passlib.handlers")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "anthropic._client",
    "bcrypt",
    "passlib.handlers.bcrypt",
    "email_validator",          # pydantic EmailStr needs this
    "websockets.legacy",
    "websockets.legacy.server",
]

# Bundle data files some libs ship (certs, etc.) plus the built frontend.
datas = []
datas += collect_data_files("anthropic")
datas += collect_data_files("certifi")
# The Vite build is copied to backend/static by build.bat / CI before packaging.
datas += [("static", "static")]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SSHPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # keep a console so the user can see status / close to quit
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # drop an icon.ico next to this spec and set: icon="icon.ico"
)
