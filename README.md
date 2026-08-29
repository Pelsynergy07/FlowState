# FlowState

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local, offline voice dictation for Windows: press a hotkey, speak, and the
cleaned-up transcript is pasted into whatever text field was focused.
While recording, circle something on screen (or Ctrl+drag a box) to
capture an annotated screenshot alongside the transcript.

Everything runs on your machine -- speech-to-text and text cleanup are both
local AI models, nothing is sent anywhere over the network.

Inspired by [better-voice](https://github.com/TarunTomar122/better-voice)
(macOS-only) -- FlowState is a from-scratch Windows implementation of the
same idea, not a port. See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for a
plain-English explanation of the architecture and the AI models involved.

## Installing

Grab `FlowStateSetup.exe` from the
[latest release](../../releases/latest) and run it -- no admin rights
needed. On first launch FlowState downloads its AI models (roughly 1.6GB
with a GPU, ~150MB without one) and then works fully offline.

**Requirements:** Windows 10 or 11, 64-bit. An NVIDIA GPU is optional --
if one isn't found, FlowState automatically switches to a smaller,
CPU-friendly model, and says so in Settings -> Model. No Python or other
tooling needs to be installed separately; the installer is self-contained.

## Using it

- **Toggle:** `Ctrl+Shift+Space` starts a hands-free recording; press again
  to stop, clean up, and paste.
- **Push-to-talk:** hold `Alt` (right) to record, release to paste.
- Both shortcuts are rebindable in Settings -> Shortcuts. If you rebind
  either one, keep them from sharing all their keys with each other (e.g.
  don't set push-to-talk to `shift+space` while the toggle is
  `ctrl+shift+space`) -- FlowState will refuse to save a combination like
  that and explain why, since a quick tap of the longer one would get
  misread as the shorter one.
- **Screenshots:** while recording, either draw a loop with the mouse
  (circle mode) or hold Ctrl and drag a box (drag mode) to capture and
  annotate a screenshot alongside the transcript -- pick the mode in
  Settings -> Capture.
- Recent sessions (transcript + any screenshots) are available from the
  tray icon and in Settings -> History.

## Development setup

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e .
```

Run the app:

```
.venv\Scripts\python.exe -m flowstate
```

Run tests:

```
.venv\Scripts\python.exe -m pytest
```

## Building the installer

```
powershell -File packaging\build.ps1
```

Produces `packaging\dist_installer\FlowStateSetup.exe`. Requires
[Inno Setup 6](https://jrsoftware.org/isdl.php) on the machine doing the
build (not needed by anyone just running the resulting installer).

## Contributing

Issues and pull requests are welcome. There's no formal process yet --
just open an issue for bugs or ideas, or a PR if you've already got a
fix. `.venv\Scripts\python.exe -m pytest` should stay green.

## License

[MIT](LICENSE).
