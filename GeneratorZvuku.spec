# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec pro Generator zvuku
# Spusteni: pyinstaller GeneratorZvuku.spec --noconfirm

import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Kivy deps (SDL2, GLEW) - nutne pro Windows
try:
    from kivy_deps import sdl2, glew
    kivy_dep_bins = sdl2.dep_bins + glew.dep_bins
except ImportError:
    kivy_dep_bins = []

# Kivy ma vlastni PyInstaller hooky; collect_all("kivy") muze na Python 3.12 selhat
# kvuli nekorektnimu "kivy.garden" path. Proto Kivy nechame na vestavenych hoocich.
kivy_datas, kivy_binaries, kivy_hiddens = [], [], []
edgetss_datas, edgetss_binaries, edgetss_hiddens = collect_all("edge_tts")

# ffmpeg binarni soubor z imageio_ffmpeg
imageio_datas = collect_data_files("imageio_ffmpeg")

all_datas    = kivy_datas    + edgetss_datas    + imageio_datas
all_binaries = kivy_binaries + edgetss_binaries
all_hiddens  = kivy_hiddens  + edgetss_hiddens  + [
    "kivy.core.audio",
    "kivy.core.audio.audio_sdl2",
    "kivy.core.window",
    "kivy.core.window.window_sdl2",
    "kivy.core.text",
    "kivy.core.text.text_sdl2",
    "kivy.core.image",
    "kivy.core.clipboard",
    "kivy.core.clipboard.clipboard_winctypes",
    "asyncio",
    "tkinter",
    "edge_tts",
]

a = Analysis(
    ["tuner_ui.py"],
    pathex=[os.path.abspath(".")],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddens,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "PIL", "pandas"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GeneratorZvuku",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # bez konzoloveho okna
    icon=None,               # sem lze dat .ico soubor
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    *[Tree(p) for p in kivy_dep_bins],
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GeneratorZvuku",
)
