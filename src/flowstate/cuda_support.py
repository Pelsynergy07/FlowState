"""Makes pip-installed CUDA runtime DLLs (nvidia-cublas-cu12,
nvidia-cudnn-cu12, nvidia-cuda-runtime-cu12, nvidia-cuda-nvrtc-cu12) findable
by native loaders.

These packages ship their DLLs inside site-packages rather than anywhere
Windows normally looks, so every native library that needs CUDA at
runtime (ctranslate2 for faster-whisper, ggml-cuda for llama.cpp) needs
this run first. Both os.add_dll_directory() *and* prepending to PATH are
needed: some native loaders call the classic LoadLibraryW (which only
honors PATH), others only honor the newer AddDllDirectory mechanism.

No-op if those packages aren't installed (e.g. a CPU-only machine) or on
non-Windows platforms -- callers still work, just on CPU.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_dll_dirs_registered = False

_CUDA_PACKAGES = (
    "nvidia.cublas",
    "nvidia.cudnn",
    "nvidia.cuda_runtime",
    "nvidia.cuda_nvrtc",
)


def _add_dir(p: Path) -> None:
    if not p.is_dir():
        return
    p_str = str(p.resolve())
    try:
        os.add_dll_directory(p_str)
    except OSError:
        pass
    cur_path = os.environ.get("PATH", "")
    if p_str not in cur_path.split(os.pathsep):
        os.environ["PATH"] = p_str + os.pathsep + cur_path


def ensure_cuda_dll_search_paths() -> None:
    global _dll_dirs_registered
    if _dll_dirs_registered or os.name != "nt":
        return
    _dll_dirs_registered = True

    # 1. PyInstaller bundled paths (e.g. sys._MEIPASS or executable directory)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        _add_dir(base)
        _add_dir(base / "_internal")
        try:
            for p in base.glob("nvidia*/**/bin"):
                _add_dir(p)
        except Exception:
            pass

    exe_dir = Path(sys.executable).parent
    _add_dir(exe_dir)
    internal_dir = exe_dir / "_internal"
    if internal_dir.is_dir():
        _add_dir(internal_dir)
        try:
            for p in internal_dir.glob("nvidia*/**/bin"):
                _add_dir(p)
        except Exception:
            pass

    # 2. Pip-installed site-packages
    for module_name in _CUDA_PACKAGES:
        try:
            module = __import__(module_name, fromlist=["_"])
            # These are namespace packages (no __init__.py), so __file__ is
            # None; the package directory comes from __path__ instead.
            package_dir = Path(next(iter(module.__path__)))
            _add_dir(package_dir / "bin")
            _add_dir(package_dir)
        except (ImportError, OSError, StopIteration):
            continue

    # 3. System CUDA Toolkit paths as fallback
    for key in (
        "CUDA_PATH",
        "CUDA_PATH_V12_4",
        "CUDA_PATH_V12_3",
        "CUDA_PATH_V12_2",
        "CUDA_PATH_V12_1",
        "CUDA_PATH_V12_0",
    ):
        cuda_root = os.environ.get(key)
        if cuda_root:
            _add_dir(Path(cuda_root) / "bin")
