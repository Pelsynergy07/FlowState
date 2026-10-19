# FlowState

<div align="center">

[![Release](https://img.shields.io/badge/Release-v1.0.4--beta-blue.svg?style=for-the-badge)](https://github.com/Pelsynergy07/FlowState/releases/tag/v1.0.4-beta)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20%7C%20macOS%2014%2B-0078D4.svg?style=for-the-badge)](https://github.com/Pelsynergy07/FlowState/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Privacy](https://img.shields.io/badge/Privacy-Local%20Dictation%20%7C%20Opt--in%20Stats-10B981.svg?style=for-the-badge)](HOW_IT_WORKS.md)

### *High-speed, 100% offline voice dictation with screen-context grounding for Windows and macOS.*

[**Download for Windows**](https://github.com/Pelsynergy07/FlowState/releases/latest/download/FlowStateSetup.exe) • [**Download for Mac**](https://github.com/Pelsynergy07/FlowState/releases/latest/download/FlowState-macOS.dmg) • [**Website**](https://runflowstate.vercel.app/) • [**How It Works**](HOW_IT_WORKS.md) • [**Contributing**](CONTRIBUTING.md)

</div>

---

## ⚡ What is FlowState?

**FlowState** brings effortless voice dictation to Windows without sending your voice or thoughts to cloud servers. Press a hotkey anywhere, speak naturally, and FlowState transcribes your speech, reformats it with a local AI language model into clean prose, and pastes it directly into your active window.

While dictating, you can circle an element on your screen (or Ctrl+drag a box) to capture and attach an annotated screenshot synchronized with your speech timestamps.

Everything runs **100% locally on your machine**:
* 🔒 **Private Dictation**: Audio, transcripts, screenshots, and clipboard content stay on your computer. Anonymous usage counts are optional and off by default.
* 🚀 **Instant Hardware Acceleration**: Utilizes your NVIDIA GPU via CUDA, or automatically switches to an optimized CPU engine if no GPU is present.
* 🎨 **Tactile Neo-Brutalist Interface**: Physical 3D filing folder tabs, mechanical button depressions, and paper-textured aesthetics designed with love.
* 🔄 **Seamless Auto-Updates**: 1-click built-in updater with live progress tracking and automatic relaunch.

---

## 📥 Installation

Grab the standalone setup installer from our latest release:

👉 **[Download FlowStateSetup.exe (~1.06 GB)](https://github.com/Pelsynergy07/FlowState/releases/download/v1.0.4-beta/FlowStateSetup.exe)**

* **System Requirements**: Windows 10 or 11 (64-bit).
* **Hardware**:
  * **GPU Mode (Recommended)**: NVIDIA GPU with CUDA support runs Whisper `large-v3-turbo` for near-instant transcription.
  * **CPU Mode**: Automatic fallback to lightweight Whisper `base.en` on multi-core CPUs.
* **No Prerequisites**: No Python, CUDA toolkits, or external dependencies required. The installer is completely self-contained.

### macOS (Apple silicon)

👉 **[Download FlowState-macOS.dmg](https://github.com/Pelsynergy07/FlowState/releases/latest/download/FlowState-macOS.dmg)** (~430 MB), drag **FlowState** into **Applications**, and open it. FlowState lives in the menu bar.

* **System Requirements**: macOS 14 Sonoma or later on Apple silicon (M1 or newer).
* **Speech**: NVIDIA Parakeet v2 on the Apple Neural Engine (English, about 0.1 s per 14-second stretch of speech on an M2 Max). Choose Whisper `large-v3-turbo` (MLX) in **Settings → Model** for other languages.
* **Formatting**: the same Qwen2.5-1.5B model as Windows, on the Mac's GPU through Metal.
* **Permissions**: setup walks you through Microphone, Accessibility and Input Monitoring (for shortcuts and pasting), plus Screen Recording if you want screenshots.
* **Shortcuts**: hold **Right ⌥ Option** to talk, or press **Fn + ⇧ Shift + Space** for hands-free. Drag a screenshot region with **⇧ Shift** held.
* First download: about 1.6 GB (Parakeet ~460 MB + Qwen ~1.1 GB).
* The app isn't notarized by Apple yet. The first time you open it, macOS stops it: go to **System Settings → Privacy & Security** and click **Open Anyway**.

> [!TIP]
> On first launch, FlowState displays an interactive setup dialog that downloads the local open-weights AI models (on NVIDIA GPUs: ~1.6 GB Whisper + ~1.5 GB Qwen2.5 text formatting; on CPU-only machines: a smaller Whisper + ~1.1 GB Qwen2.5) directly from Hugging Face. After this initial one-time download, FlowState functions entirely offline.

---

## 🎯 How to Use

### 🎙️ Voice Dictation
* **Hands-Free Toggle**: Press `Ctrl + Shift + Space` to begin recording. Speak at your natural pace. Press the combination again to stop, format, and paste.
* **Push-to-Talk**: Hold `Ctrl + M` while speaking; release the keys to immediately format and paste.
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
| **Speech-to-Text** | `faster-whisper` (CTranslate2); Parakeet v2 via FluidAudio/CoreML and Whisper via MLX on macOS | Local speech recognition (`large-v3-turbo` on CUDA / `base.en` on CPU; Parakeet v2 on the Apple Neural Engine). |
| **Text Structuring** | CTranslate2 on GPU / `llama-cpp-python` on CPU or Metal (`Qwen2.5-1.5B-Instruct`) | Local LLM laying out emails, lists, paragraphs and punctuation; a word-alignment guard keeps every dictated word (no paraphrasing). |
| **Visual Grounding** | `mss` + `Pillow` + Native Hooks | Gesture detection (circle bounding & rectangle drag) with timestamped annotation, Retina-aware on macOS. |
| **Desktop UI** | `PySide6` (Qt for Python) | Neo-brutalist, DPI-scaled desktop shell with tray/menu-bar menus, waveform HUD, and settings. |
| **OS integration** | `flowstate/platform/` adapters | Win32 hooks and clipboard on Windows; Quartz event taps, NSPasteboard and AppKit on macOS. |

FlowState's code is split so a feature is written once for every platform: see [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md).

For a plain-English explanation of the pipeline and local AI models, see [**HOW_IT_WORKS.md**](HOW_IT_WORKS.md).

---

## 🔒 Privacy & Storage

FlowState is built on an uncompromising privacy foundation:
- **Audio & Transcripts**: Processed solely in RAM and stored locally under `%LOCALAPPDATA%\FlowState\sessions\` (Windows) or `~/Library/Application Support/FlowState/sessions/` (macOS).
- **History**: Session history is cleared each time FlowState starts. Completed transcripts from the current run remain available locally until you clear history or restart the app.
- **Network Boundaries**: Network access covers public model downloads and GitHub update checks. Anonymous usage counters are sent to PostHog only after explicit opt-in; speech and screen content remain local.

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

#### macOS
```bash
python3.12 -m venv .venv
CMAKE_ARGS="-DGGML_METAL=on" .venv/bin/pip install -r requirements-macos.txt
swift build -c release --package-path native/macos/FlowStateParakeet   # Parakeet speech helper
PYTHONPATH=src .venv/bin/python -m flowstate
```
macOS grants Accessibility and Input Monitoring to the app you launch from (e.g. Terminal) when running from source. Build the app with `packaging/build_macos.sh` (outputs `FlowState.app`, `FlowState-macOS.zip` for in-app updates, and a `.dmg`).

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

## Usage statistics

Open **Settings → Stats** for local totals and export. Optional anonymous sharing supports a private PostHog portfolio dashboard. See [ANALYTICS.md](ANALYTICS.md) for setup, exact metrics, and privacy details.
