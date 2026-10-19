# PyInstaller spec for FlowState on macOS: builds dist/FlowState.app.
#
# Run through packaging/build_macos.sh, which also builds the Parakeet
# speech helper (native/macos/FlowStateParakeet) into
# FlowState.app/Contents/Helpers, signs the bundle and makes the release
# zip (used by the in-app updater) and the .dmg.
#
# Same approach as flowstate.spec on Windows: onedir inside the .app, ML
# packages collected in full because their native libraries and lazy
# imports defeat static analysis. No CUDA packages: Apple silicon runs
# speech on the Neural Engine (Parakeet) or GPU (MLX Whisper), and the
# formatter on the GPU through llama.cpp's Metal backend.

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))  # lets collect_submodules find flowstate

namespace = {}
exec((SRC_DIR / "flowstate" / "__init__.py").read_text(), namespace)
VERSION = namespace["__version__"]
SHORT_VERSION = VERSION.split("-")[0]

datas = []
binaries = []
hiddenimports = [
    "pynput.keyboard._darwin",
    "pynput.mouse._darwin",
    "Quartz",
    "AppKit",
    "Foundation",
    "AVFoundation",
    "ApplicationServices",
    "objc",
]

packages = ["huggingface_hub", "_sounddevice_data", "av", "ctranslate2", "faster_whisper", "llama_cpp", "tokenizers"]
if platform.machine() == "arm64":
    packages += ["mlx", "mlx_whisper"]
for pkg in packages:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

datas += [(str(SRC_DIR / "flowstate" / "resources"), "flowstate/resources")]
# Platform adapters are imported by name at runtime (platform.adapter()),
# which static analysis can't see.
hiddenimports += collect_submodules("flowstate.platform")

a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "entry_point.py")],
    pathex=[str(SRC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Windows-only and test-only packages never belong in the Mac app.
    excludes=["win32api", "win32con", "win32clipboard", "win32gui", "win32process", "winreg", "pytest"],
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
    argv_emulation=False,
    target_arch=None,
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

app = BUNDLE(
    coll,
    name="FlowState.app",
    icon=str(PROJECT_ROOT / "packaging" / "app_icon.icns"),
    bundle_identifier="com.pelsynergy.flowstate",
    version=SHORT_VERSION,
    info_plist={
        "CFBundleName": "FlowState",
        "CFBundleDisplayName": "FlowState",
        "CFBundleShortVersionString": SHORT_VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "14.0",
        # A regular app, so it appears in Launchpad and Spotlight's app list.
        # FlowState hides its Dock icon itself whenever no window is open
        # (platform/macos/system.py), so it still behaves like a menu-bar app.
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription":
            "FlowState listens only while you hold or tap your dictation shortcut, and turns your speech into "
            "text on this Mac.",
        "NSAppleEventsUsageDescription":
            "FlowState pastes your dictated text into the app you're using.",
        "NSHumanReadableCopyright": "FlowState by Pelsynergy. MIT License.",
    },
)
