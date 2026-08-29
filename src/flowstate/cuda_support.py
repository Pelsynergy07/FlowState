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
from pathlib import Path

_dll_dirs_registered = False

_CUDA_PACKAGES = (
    "nvidia.cublas",
    "nvidia.cudnn",
    "nvidia.cuda_runtime",
    "nvidia.cuda_nvrtc",
)


def ensure_cuda_dll_search_paths() -> None:
    global _dll_dirs_registered
    if _dll_dirs_registered or os.name != "nt":
        return
    _dll_dirs_registered = True
    for module_name in _CUDA_PACKAGES:
        try:
            module = __import__(module_name, fromlist=["_"])
            # These are namespace packages (no __init__.py), so __file__ is
            # None; the package directory comes from __path__ instead.
            package_dir = Path(next(iter(module.__path__)))
            bin_dir = package_dir / "bin"
            if bin_dir.is_dir():
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        except (ImportError, OSError, StopIteration):
            continue
