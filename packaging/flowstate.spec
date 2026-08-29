# PyInstaller spec for FlowState (onedir build).
#
# onedir, not onefile: onefile re-extracts the whole bundle to a temp
# folder on every launch, which would be slow for a stack this size
# (PySide6 + ctranslate2 + llama-cpp-python). onedir starts instantly
# after the first run.
#
# The heavy ML packages below (sounddevice, av, ctranslate2, faster_whisper,
# llama_cpp, huggingface_hub, nvidia's CUDA DLL packages) are collected in
# full via collect_all/collect_dynamic_libs rather than trusted to
# PyInstaller's static import analysis, which is well known to miss lazy
# imports and bundled native binaries in packages like this.
#
# Notably absent: torch, transformers, optimum. An earlier version of the
# cleanup pipeline used an ONNX grammar model that needed them; the
# current local-LLM formatter (llama-cpp-python + a GGUF model) doesn't,
# which is a large chunk of the installer's former size gone.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

datas = []
binaries = []
hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "win32timezone",
    "win32com",
    "win32com.client",
]

for pkg in (
    "huggingface_hub",
    "sounddevice",
    "av",
    "ctranslate2",
    "faster_whisper",
    "llama_cpp",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# nvidia-*-cu12 packages are namespace packages holding only DLLs --
# collect_all doesn't pick up the binaries reliably for namespace
# packages, so their bin/ folders are added explicitly.
for nvidia_pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime", "nvidia.cuda_nvrtc"):
    binaries += collect_dynamic_libs(nvidia_pkg)

# flowstate's own bundled data (vocabulary json etc).
datas += [(str(SRC_DIR / "flowstate" / "resources"), "flowstate/resources")]

a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "entry_point.py")],
    pathex=[str(SRC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FlowState",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(PROJECT_ROOT / "packaging" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="FlowState",
)
