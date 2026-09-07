# FlowState

<div align="center">

[![Release](https://img.shields.io/badge/Release-v1.0.0--beta-blue.svg?style=for-the-badge)](https://github.com/Pelsynergy07/FlowState/releases/tag/v1.0.0-beta)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D4.svg?style=for-the-badge&logo=windows)](https://github.com/Pelsynergy07/FlowState/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%7C%20Zero%20Telemetry-10B981.svg?style=for-the-badge)](HOW_IT_WORKS.md)

### *High-speed, 100% offline voice dictation with screen-context grounding for Windows.*

[**Download Installer (v1.0.0 Beta)**](https://github.com/Pelsynergy07/FlowState/releases/download/v1.0.0-beta/FlowStateSetup.exe) • [**How It Works**](HOW_IT_WORKS.md) • [**Contributing**](CONTRIBUTING.md)

</div>

---

## ⚡ What is FlowState?

**FlowState** brings effortless voice dictation to Windows without sending your voice or thoughts to cloud servers. Press a hotkey anywhere, speak naturally, and FlowState transcribes your speech, reformats it with a local AI language model into clean prose, and pastes it directly into your active window.

While dictating, you can circle an element on your screen (or Ctrl+drag a box) to capture and attach an annotated screenshot synchronized with your speech timestamps.

Everything runs **100% locally on your machine**:
* 🔒 **Zero Cloud Telemetry**: No audio, transcripts, or personal data ever leaves your computer.
* 🚀 **Instant Hardware Acceleration**: Utilizes your NVIDIA GPU via CUDA, or automatically switches to an optimized CPU engine if no GPU is present.
* 🎨 **Tactile Neo-Brutalist Interface**: Physical 3D filing folder tabs, mechanical button depressions, and paper-textured aesthetics designed with love.
* 🔄 **Seamless Auto-Updates**: 1-click built-in updater with live progress tracking and automatic relaunch.

---

## 📥 Installation

Grab the standalone setup installer from our latest release:

👉 **[Download FlowStateSetup.exe (~1.06 GB)](https://github.com/Pelsynergy07/FlowState/releases/download/v1.0.0-beta/FlowStateSetup.exe)**

* **System Requirements**: Windows 10 or 11 (64-bit).
* **Hardware**:
  * **GPU Mode (Recommended)**: NVIDIA GPU with CUDA support runs Whisper `large-v3-turbo` for near-instant transcription.
  * **CPU Mode**: Automatic fallback to lightweight Whisper `base.en` on multi-core CPUs.
* **No Prerequisites**: No Python, CUDA toolkits, or external dependencies required. The installer is completely self-contained.

> [!TIP]
> On first launch, FlowState displays an interactive setup dialog that downloads the local open-weights AI models (~1.6 GB for GPU Whisper + ~1.1 GB for Qwen2.5 text cleanup) directly from Hugging Face. After this initial one-time download, FlowState functions entirely offline.

---

## 🎯 How to Use

### 🎙️ Voice Dictation
* **Hands-Free Toggle**: Press `Ctrl + Shift + Space` to begin recording. Speak at your natural pace. Press the combination again to stop, format, and paste.
* **Push-to-Talk**: Hold `Right Alt` while speaking; release the key to immediately format and paste.
* **Custom Shortcuts**: Fully customizable in **Settings → Shortcuts**. FlowState includes built-in collision prevention to avoid conflicting key combinations.

### 📸 Visual Context Grounding (Screenshots)
Capture screenshots without interrupting your train of thought:
1. Start dictating (e.g., *"Look at this button styling here..."*).
2. **Circle Mode**: Draw a loop around any UI element on your screen with your mouse.
3. **Drag Mode**: Hold `Ctrl` and drag a rectangle over the target area.
4. When you finish recording, FlowState saves the annotated screenshot and inserts a clear context marker at the end of your transcript.

### 📚 Custom Personal Vocabulary
Fix uncommon names, acronyms, or technical jargon:
Create or edit `%LOCALAPPDATA%\FlowState\vocabulary_user.json`:
```json
{
  "cube cuttle": "kubectl",
  "engine x": "nginx",
  "pi torch": "PyTorch",
  "pelsynergy": "Pelsynergy"
}
```
FlowState hot-reloads this file automatically without needing a restart.

---

## 🏛️ Architecture & AI Engine

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Speech-to-Text** | `faster-whisper` (CTranslate2) | High-speed local Whisper speech recognition (`large-v3-turbo` on CUDA / `base.en` on CPU). |
| **Text Structuring** | `llama-cpp-python` (`Qwen2.5-1.5B-Instruct`) | CPU-only local LLM reformatting raw stream-of-consciousness into structured lists and punctuation. |
| **Visual Grounding** | `mss` + `Pillow` + Native Hooks | Gesture detection (circle bounding & rectangle drag) with timestamped annotation. |
| **Desktop UI** | `PySide6` (Qt for Python) | Neo-brutalist, DPI-scaled desktop shell with tray menus, waveform HUD, and settings. |
| **Input Interception** | Low-Level Windows API Hooks | Win32 keyboard & mouse hooks (`pynput` / `pywin32`) for reliable global hotkeys. |

For a plain-English explanation of the pipeline and local AI models, see [**HOW_IT_WORKS.md**](HOW_IT_WORKS.md).

---

## 🔒 Privacy & Storage

FlowState is built on an uncompromising privacy foundation:
- **Audio & Transcripts**: Processed solely in RAM and stored locally under `%LOCALAPPDATA%\FlowState\sessions\`.
- **Retention**: Local session history is kept for 7 days (capped at 500 MB) with oldest sessions automatically pruned.
- **Network Boundaries**: Network access is restricted exclusively to downloading public Hugging Face model weights on initial setup and checking GitHub Releases for updates. **Zero tracking. Zero telemetry. Zero external servers.**

---

## 🛠️ Development & Contributing

Contributions are warmly welcome! Whether you are polishing the UI, optimizing inference performance, or fixing bugs:

### Setup Local Dev Environment
```powershell
# 1. Clone repository
git clone https://github.com/Pelsynergy07/FlowState.git
cd FlowState

# 2. Create Python 3.12 virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies & editable package
python -m pip install -r requirements.txt
python -m pip install -e .

# 4. Run application from source
python -m flowstate
```

### Run Tests
```powershell
python -m pytest
```

Please read [**CONTRIBUTING.md**](CONTRIBUTING.md) for full guidelines on code style, dynamic Qt dialog sizing, and submitting Pull Requests.

---

## 📜 License & Credits

* **License**: Open source under the [MIT License](LICENSE).
* **Inspiration**: Inspired by [better-voice](https://github.com/TarunTomar122/better-voice) (macOS).
* **Crafted with love** by [**Pelsynergy**](https://github.com/Pelsynergy07).
