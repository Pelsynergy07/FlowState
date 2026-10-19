"""Local LLM runtimes for the formatter.

NVIDIA GPU: Qwen2.5-1.5B-Instruct (int8) through CTranslate2, the same
runtime faster-whisper already uses, so no extra native dependency. On an
RTX 2070 it formats a 60-word live window in well under two seconds.

Everything else: the same model as a GGUF file through llama.cpp on the
CPU. The CUDA-enabled llama-cpp-python wheels are not an option for the
GPU path: they assume AVX-512 and crash with an illegal instruction on
common CPUs even with no layers offloaded.

A machine downloads only the model for the runtime it will use.
"""
from __future__ import annotations

import ctypes
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .. import paths

logger = logging.getLogger("flowstate.text.llm")


@dataclass(frozen=True)
class FormatterModel:
    runtime: str  # "cuda" (CTranslate2) or "cpu" (llama.cpp)
    repo: str
    folder: str  # under paths.models_dir()
    weights: str  # file whose presence marks a complete download
    approx_size_mb: int
    min_bytes: int
    display_name: str


CUDA_MODEL = FormatterModel(
    runtime="cuda",
    repo="jncraton/Qwen2.5-1.5B-Instruct-ct2-int8",
    folder="formatter-cuda",
    weights="model.bin",
    approx_size_mb=1560,
    min_bytes=1000 * 1024 * 1024,
    display_name="Qwen 1.5B, GPU",
)
CPU_MODEL = FormatterModel(
    runtime="cpu",
    repo="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    folder="formatter",
    weights="qwen2.5-1.5b-instruct-q4_k_m.gguf",
    approx_size_mb=1150,
    min_bytes=100 * 1024 * 1024,
    display_name="Qwen 1.5B, CPU",
)
# Model weights plus activations and KV cache for a ~1k-token request.
_CUDA_FREE_BYTES_REQUIRED = 2200 * 1024 * 1024
_END_TOKENS = ["<|im_end|>", "<|endoftext|>"]


def model_dir(model: FormatterModel) -> Path:
    return paths.models_dir() / model.folder


def is_cached(model: FormatterModel) -> bool:
    weights = model_dir(model) / model.weights
    if not (weights.is_file() and weights.stat().st_size > model.min_bytes):
        return False
    return model.runtime != "cuda" or (model_dir(model) / "tokenizer.json").is_file()


def download(model: FormatterModel) -> Path:
    target = model_dir(model)
    target.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading formatter model %s to %s", model.repo, target)
    if model.runtime == "cuda":
        from huggingface_hub import snapshot_download

        snapshot_download(model.repo, local_dir=str(target),
                          allow_patterns=["*.json", "model.bin"])
    else:
        from huggingface_hub import hf_hub_download

        hf_hub_download(model.repo, model.weights, local_dir=str(target))
    if not is_cached(model):
        raise RuntimeError(f"Formatter download incomplete: {target}")
    return target


def cuda_device_available() -> bool:
    try:
        from ..cuda_support import ensure_cuda_dll_search_paths

        ensure_cuda_dll_search_paths()
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        logger.info("CUDA probe for the formatter failed", exc_info=True)
        return False


def _nvml_query(query):
    """Run query(nvml, handle) against GPU 0 via NVML, which ships with every
    NVIDIA driver. None when there is no NVIDIA driver or the call fails."""
    try:
        nvml = ctypes.WinDLL("nvml.dll") if hasattr(ctypes, "WinDLL") else ctypes.CDLL("libnvidia-ml.so.1")
    except OSError:
        return None
    try:
        if nvml.nvmlInit_v2() != 0:
            return None
        try:
            handle = ctypes.c_void_p()
            if nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                return None
            return query(nvml, handle)
        finally:
            nvml.nvmlShutdown()
    except Exception:
        return None


def cuda_free_bytes() -> int | None:
    """Free memory on GPU 0."""
    class Memory(ctypes.Structure):
        _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]

    def query(nvml, handle):
        memory = Memory()
        return int(memory.free) if nvml.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(memory)) == 0 else None

    return _nvml_query(query)


def cuda_device_name() -> str | None:
    """Marketing name of GPU 0, e.g. "NVIDIA GeForce RTX 2070"."""
    def query(nvml, handle):
        name = ctypes.create_string_buffer(96)
        if nvml.nvmlDeviceGetName(handle, name, ctypes.c_uint(96)) != 0:
            return None
        return name.value.decode("utf-8", "replace").strip() or None

    return _nvml_query(query)


def preferred_model(device_preference: str = "auto", cuda_available: bool | None = None) -> FormatterModel:
    """Which formatter this machine should download and run."""
    if device_preference == "cpu":
        return CPU_MODEL
    if cuda_available if cuda_available is not None else cuda_device_available():
        return CUDA_MODEL
    return CPU_MODEL


def chatml(messages: list[dict], *, open_assistant: bool) -> str:
    text = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
    return text + ("<|im_start|>assistant\n" if open_assistant else "")


class Ct2Backend:
    runtime = "cuda"

    def __init__(self, folder: Path):
        from ..cuda_support import ensure_cuda_dll_search_paths

        ensure_cuda_dll_search_paths()
        import ctranslate2
        import tokenizers

        free = cuda_free_bytes()
        if free is not None and free < _CUDA_FREE_BYTES_REQUIRED:
            raise RuntimeError(f"Only {free // (1024 * 1024)} MB of GPU memory free for the formatter")
        self._tokenizer = tokenizers.Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._generator = ctranslate2.Generator(str(folder), device="cuda", compute_type="int8_float16")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def stream(self, messages: list[dict], max_tokens: int) -> Iterator[str]:
        # The system prompt and examples are identical on every call; CTranslate2
        # caches their attention state once as a static prompt.
        prefix = self._tokenizer.encode(chatml(messages[:-1], open_assistant=False), add_special_tokens=False).tokens
        full = self._tokenizer.encode(chatml(messages, open_assistant=True), add_special_tokens=False).tokens
        if full[:len(prefix)] != prefix:
            prefix = []
        steps = self._generator.generate_tokens(
            full[len(prefix):], static_prompt=prefix or None, max_length=max_tokens,
            sampling_topk=1, end_token=_END_TOKENS,
        )
        ids: list[int] = []
        emitted = ""
        try:
            for step in steps:
                if step.token in _END_TOKENS:
                    break
                ids.append(step.token_id)
                text = self._tokenizer.decode(ids)
                # An incomplete multi-byte character decodes as U+FFFD; wait for the rest.
                if text.endswith("�"):
                    continue
                yield text[len(emitted):]
                emitted = text
        finally:
            # Closing CTranslate2's iterator stops decoding on the GPU.
            steps.close()


class LlamaCppBackend:
    runtime = "cpu"

    def __init__(self, path: Path, n_threads: int = 6, context: int = 2048):
        from llama_cpp import Llama

        self._llm = Llama(model_path=str(path), n_gpu_layers=0, n_ctx=context, n_threads=n_threads, verbose=False)

    def count_tokens(self, text: str) -> int:
        return len(self._llm.tokenize(text.encode("utf-8"), add_bos=False))

    def stream(self, messages: list[dict], max_tokens: int) -> Iterator[str]:
        events = self._llm.create_chat_completion(messages=messages, max_tokens=max_tokens,
                                                  temperature=0.0, stream=True)
        try:
            for event in events:
                content = event["choices"][0].get("delta", {}).get("content")
                if content:
                    yield content
        finally:
            close = getattr(events, "close", None)
            if close is not None:
                close()


def load_backend(model: FormatterModel):
    if model.runtime == "cuda":
        return Ct2Backend(model_dir(model))
    return LlamaCppBackend(model_dir(model) / model.weights)


_download_lock = threading.Lock()


def ensure_downloaded(model: FormatterModel) -> bool:
    with _download_lock:
        if is_cached(model):
            return True
        try:
            download(model)
            return True
        except Exception:
            logger.warning("Formatter model download failed: %s", model.repo, exc_info=True)
            return False
