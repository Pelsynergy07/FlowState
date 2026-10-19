# FlowState architecture

FlowState ships on Windows and macOS from one codebase, and is laid out so an
Android app can reuse the same core. This page explains where code goes, so
a feature built once reaches every platform.

## The four layers

```
┌───────────────────────────────────────────────────────────────┐
│ 4. Shell (UI)          src/flowstate/ui, __main__.py            │  PySide6 on desktop
│    tray/menu bar, HUD, onboarding, settings, history            │  (Android: its own UI)
├───────────────────────────────────────────────────────────────┤
│ 3. Platform adapters   src/flowstate/platform/{windows,macos,…} │  one package per OS
│    keyboard hook, clipboard + paste, focus, window effects,     │
│    single instance, login item, sounds, permissions             │
├───────────────────────────────────────────────────────────────┤
│ 2. Engines             src/flowstate/asr, src/flowstate/text/llm│  chosen per hardware
│    speech: faster-whisper (CUDA/CPU), Parakeet (Neural Engine), │
│    Whisper on MLX; formatter: Qwen 1.5B (CUDA, Metal, CPU)      │
├───────────────────────────────────────────────────────────────┤
│ 1. Core (pure Python)  text/, streaming.py, session/, config.py,│  identical everywhere
│    hotkeys/manager.py matching, capture/gesture.py, guard        │
└───────────────────────────────────────────────────────────────┘
```

Rules that keep it working:

1. **Core imports nothing OS-specific and no Qt widgets.** Text cleanup,
   the word-preserving guard, live-window streaming, gesture detection,
   hotkey matching, config and session storage are plain Python and fully
   unit tested. This is what Android reuses.
2. **Only `platform/<os>/` may import `win32*`, `ctypes.windll`, `winreg`,
   `AppKit`, `Quartz` or other OS APIs.** Everything else calls
   `platform.adapter("keyboard" | "clipboard" | "focus" | "window" | "system")`.
3. **UI asks what the platform can do, not which OS it is.** Use
   `platform.supports("drag_capture")`, `platform.drag_modifier_token()`,
   `platform.device_noun()` ("PC"/"Mac"), `platform.name()`. A feature
   then appears wherever it is supported without per-OS branches.
4. **Engines are picked by hardware, behind one interface.** Every speech
   backend returns faster-whisper-shaped `(segments, info)` with word
   timings, so streaming, screenshot references and history never change.

## Platform adapter contract

Each adapter package (`platform/windows`, `platform/macos`,
`platform/generic`) provides:

| Module | What it provides |
|---|---|
| `__init__` | `CAPABILITIES`, `DEFAULT_TOGGLE`, `DEFAULT_PUSH_TO_TALK`, `DRAG_MODIFIER_TOKEN`, `KNOWN_SHORTCUT_CONFLICTS`, `open_path()` |
| `keyboard` | `KeyboardHook(on_event)` with `start()`, `stop()`, `failed`; `modifier_held(token)`. Reports keys as shared tokens: `ctrl_l`, `ctrl`, `alt_r`, `shift`, `cmd`, `space`, `a`–`z`, `0`–`9` |
| `clipboard` | `save_clipboard`, `set_clipboard_text`, `set_clipboard_image`, `restore_clipboard`, `send_paste_shortcut`, optional `PASTE_SETTLE_SECONDS` |
| `focus` | `get_foreground_window`, `get_window_title`, `restore_foreground_window` (an opaque handle: HWND on Windows, process id on macOS) |
| `window` | `make_overlay(widget, click_through, exclude_from_capture)`, `bring_to_front(widget)`, `global_to_logical(x, y)` |
| `system` | `prepare_process`, `configure_qt_application`, `acquire_single_instance_lock`, `set_launch_at_login`, `autostart_command`, `spawn_relaunch`, `play_tone`, `microphone_access_blocked`, `MICROPHONE_SETTINGS_URL`, `cpu_name` |

`platform/permissions.py` turns OS privacy permissions into a list of
`Permission(id, title, why, required, check, request, settings_url)`, which
onboarding and Settings render as one checklist on any OS.

`platform/generic` is the minimal template for a new adapter: the app
starts and dictation lands on the clipboard, with no global shortcuts.

## Models per platform

| Machine | Speech | Formatting |
|---|---|---|
| Windows + NVIDIA GPU | Whisper large-v3-turbo, CTranslate2 on CUDA | Qwen 2.5 1.5B, CTranslate2 int8 on CUDA |
| Windows, no NVIDIA GPU | Whisper base.en on the CPU (to be revisited after the Windows benchmark) | Qwen 2.5 1.5B GGUF, llama.cpp on the CPU |
| Mac, Apple silicon | NVIDIA Parakeet TDT 0.6B v2 on the Neural Engine (Swift helper, FluidAudio/CoreML). Fallback and other languages: Whisper large-v3-turbo on MLX | Qwen 2.5 1.5B GGUF, llama.cpp on the GPU (Metal) |

The Mac choices come from the FlowState benchmark: Parakeet v2 matched
Whisper turbo on English accuracy (~2% word errors) at a third of the size
and handled long streamed recordings cleanly; Qwen 1.5B kept the best
layout quality. Windows keeps its models until its own benchmark run.

Selection lives in `asr/engine.py` (`TranscriptionEngine._apple_route`,
`resolve_target_model`, `model_download_plan`) and `text/llm.py`
(`preferred_model`). To add a model, register it in `asr/models.py` and,
if it needs a new runtime, add a backend shaped like
`asr/parakeet_backend.py` or `asr/mlx_backend.py`.

## Shipping one feature everywhere

1. Put the logic in core, with tests (`tests/`), so it runs on every OS.
2. If it needs the OS, add one function to the adapter contract and
   implement it in `platform/windows` and `platform/macos` (and a no-op in
   `platform/generic`). Declare a capability flag if some platforms can't
   support it.
3. In the UI, gate on `platform.supports(...)` and take OS wording from the
   facade helpers.
4. Run the tests on both platforms. OS-specific tests use
   `pytest.importorskip("win32con")` or `skipif(sys.platform != ...)`.

## Android plan

Android won't run the PySide6 shell, but it can share everything below it:

- **Core:** run `flowstate.text`, `streaming`, `session` and `config`
  inside the Android app with Chaquopy (Python on Android), or port them
  to Kotlin against the same test fixtures, so behaviour stays identical.
- **Engines:** Parakeet and Whisper both run on Android through ONNX
  (sherpa-onnx), and Qwen 1.5B through llama.cpp's Android build: the same
  model families as desktop.
- **Platform:** an Android input-method service replaces global hotkeys
  and pasting. It is the keyboard, so it inserts text directly, and
  microphone permission comes from the standard Android prompt.
- **Shell:** a Kotlin/Compose app reusing the onboarding steps and
  settings structure.

## Building

- Windows: `packaging/build.ps1` → `FlowStateSetup.exe` (PyInstaller + Inno Setup).
- macOS: `packaging/build_macos.sh` → `FlowState.app`, `FlowState-macOS.zip`
  (release asset for in-app updates) and `FlowState-<version>.dmg`.

Release assets per platform are named in `update_check.INSTALLER_ASSET_NAMES`;
attach both to the same GitHub release so each app finds its own update.
The website's download buttons (repository
[FlowState-Website](https://github.com/Pelsynergy07/FlowState-Website))
link to `releases/latest/download/FlowStateSetup.exe` and
`releases/latest/download/FlowState-macOS.dmg`, so every release needs both.
