# Contributing to FlowState

Thank you for your interest in contributing to **FlowState**! We welcome contributions from developers of all backgrounds—whether fixing bugs, improving the local AI speech and text formatting pipelines, adding accessibility enhancements, or refining our tactile neo-brutalist interface.

---

## 🧭 Core Tenets & Architectural Philosophy

Before writing code, please keep FlowState's core design principles in mind:

1. **100% Offline & Zero Telemetry**:
   FlowState is strictly local-first. Audio recording, Whisper transcription, and LLM text reformatting happen exclusively on the user's machine. **No telemetry, analytics, or user data may ever be transmitted over the network.** Network access is permitted solely for downloading public Hugging Face model weights on initial setup and checking GitHub Releases for updates.
2. **Warm Neo-Brutalist Aesthetic**:
   Our interface avoids generic flat minimalism. It embraces tactile, physical metaphors: 3D mechanical button depressions, filing folder tabs, high-contrast ink borders (`#111111`), warm paper tones (`#F4F0E8`), and intentional micro-interactions.
3. **Rock-Solid Windows Reliability**:
   Low-level global keyboard and mouse hooks must be fail-safe, memory-efficient, and non-blocking. Background threads must never touch Qt widgets directly—all UI communication must route through Qt Signals.

For a plain-English breakdown of every component and AI model, read [**HOW_IT_WORKS.md**](HOW_IT_WORKS.md).

---

## 🛠️ Development Setup

### Prerequisites
- **Operating System**: Windows 10 or 11 (64-bit).
- **Python**: Python 3.12 (recommended: install via `python.org` or `winget install Python.Python.3.12`).
- **GPU (Optional)**: NVIDIA GPU with CUDA support for accelerated Whisper inference. If no NVIDIA GPU is detected, FlowState gracefully falls back to CPU mode.
- **Inno Setup 6 (Optional)**: Required only if compiling the standalone `FlowStateSetup.exe` installer.

### 1. Clone the Repository
```powershell
git clone https://github.com/Pelsynergy07/FlowState.git
cd FlowState
```

### 2. Create and Activate Virtual Environment
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
Install runtime and test requirements:
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

> [!NOTE]
> `requirements.txt` installs a pre-built CPU wheel for `llama-cpp-python` from its dedicated index. This ensures broad compatibility without requiring a local MSVC C++ toolchain.

---

## 🚀 Running FlowState in Development

To launch the application from source:
```powershell
python -m flowstate
```
Or use the convenience launcher in the repository root:
```powershell
.\run.bat
```

To test the first-run onboarding experience (which lets you inspect model downloading and microphone calibration):
```powershell
python -m flowstate --first-run
```

---

## 🧪 Running Automated Tests

FlowState maintains a thorough unit test suite covering hotkey interception, session storage, audio capture, Whisper integration, config migration, and UI components.

Before submitting any code changes, ensure all tests pass cleanly:

```powershell
python -m pytest
```

To run a specific test module or test case:
```powershell
python -m pytest tests/test_hotkeys.py -v
python -m pytest tests/test_onboarding.py -k "test_dialog_initial_state"
```

---

## 📦 Building the Standalone Installer

To compile the standalone PyInstaller distribution and Inno Setup installer:

1. Ensure [Inno Setup 6](https://jrsoftware.org/isdl.php) is installed in its default location (`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`).
2. Run the packaging PowerShell script:
   ```powershell
   powershell -File packaging\build.ps1
   ```
3. The resulting single-file setup executable will be generated at:
   ```
   packaging\dist_installer\FlowStateSetup.exe
   ```

---

## 📐 Code Guidelines

- **Type Annotations**: FlowState uses strict type annotations with `from __future__ import annotations`.
- **Qt Threading**: Never call Qt GUI functions directly from worker threads. Always emit Qt `Signal` objects connected to main-thread slots.
- **Dynamic Dialog Sizing**: When adding dynamic elements to Qt dialogs (e.g. progress bars or expandable cards), enforce minimum size constraints (`QVBoxLayout.SetMinimumSize`) and call geometry synchronization so layouts never squeeze or clip text.
- **Process Termination & Mutexes**: FlowState relies on a named Windows global mutex (`Global\FlowStateSingleInstance`) to ensure only one instance runs. Any code that terminates or restarts the application must cleanly release this lock.

---

## 🤝 Submitting Pull Requests

1. **Fork** the repository and create your feature branch from `main`:
   ```powershell
   git checkout -b feature/my-cool-feature
   ```
2. **Write clean, documented code** adhering to our tenets.
3. **Add or update unit tests** in `tests/` covering your changes.
4. **Run `pytest`** and ensure the test suite is 100% green.
5. **Commit your changes** with descriptive commit messages:
   ```powershell
   git commit -m "feat(ui): add customizable audio cue volume slider"
   ```
6. **Push to your fork** and open a Pull Request against `main`.

Thank you for helping make FlowState the best private, offline voice dictation tool for Windows!
