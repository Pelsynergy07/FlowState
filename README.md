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
needed. On first launch FlowState downloads its AI models -- the speech
model (~1.6GB with a GPU, ~150MB without one) plus a small local model for
text cleanup (~1.1GB, downloaded either way) -- then works fully offline.

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

## Your own vocabulary

FlowState ships with a built-in pass that fixes common casing --
`github` -> `GitHub`, `json` -> `JSON`, and so on -- but it can't know
`kubectl`, an internal project name, or a colleague's surname. Add your
own by creating (or editing):

```
%LOCALAPPDATA%\FlowState\vocabulary_user.json
```

```json
{
  "cube cuttle": "kubectl",
  "engine x": "nginx"
}
```

The key is what the transcript tends to say, the value is what you
meant. Matching is whole-word and case-insensitive, and longer phrases
win over a shorter one contained inside them, so `"ci cd"` beats a bare
`"ci"`. The file is re-read automatically whenever it changes -- no
restart needed. A term you list here overrides the built-in spelling for
that same word. One rule worth respecting: don't map an ordinary word
(e.g. `"read me"`) to something else -- it'll rewrite every sentence that
happens to contain that phrase. A malformed file is just ignored rather
than breaking transcription.

## Clipboard behavior

When you stop recording, FlowState puts the cleaned-up transcript on
your clipboard and sends one Ctrl+V into whichever window was focused
when you *started* recording, then restores whatever was on your
clipboard before. If you captured any screenshots, each one gets pasted
the same way right after, as its own separate Ctrl+V -- deliberately one
item per paste, since putting text and an image on the clipboard
together made some apps (browsers, chat inputs that accept image paste)
treat the whole thing as an image attach and silently drop the text.
Your original clipboard content is restored once everything's landed.

## Privacy and storage

- Speech-to-text and text cleanup both run locally. The only network
  activity FlowState ever does is downloading its models from Hugging
  Face, once, the first time each is needed -- nothing about your voice
  or transcripts is ever sent anywhere.
- Models live in `%LOCALAPPDATA%\FlowState\models\`: the speech model
  (Whisper `large-v3-turbo` on a GPU, or the smaller `base.en` on CPU)
  and a small local LLM used for text cleanup.
- Sessions (transcript + any screenshots) are saved to
  `%LOCALAPPDATA%\FlowState\sessions\`, kept for 7 days, and capped at
  500MB total -- oldest deleted first once that's exceeded.
- Settings live in `config.json`, logs in `logs\flowstate.log`, both
  under the same `%LOCALAPPDATA%\FlowState` folder.
- Uninstalling deliberately leaves this folder alone (so an upgrade or
  reinstall doesn't wipe your models and history) -- delete it by hand
  if you want a fully clean removal.

## Troubleshooting

- **A shortcut does nothing:** open Settings -> Shortcuts. Toggle and
  push-to-talk can't share all their keys with each other (e.g. don't
  set push-to-talk to `shift+space` while the toggle is
  `ctrl+shift+space`) -- FlowState refuses to save a combination like
  that, since a quick tap of the longer one gets misread as the shorter
  one. If both look fine, check `%LOCALAPPDATA%\FlowState\logs\flowstate.log`
  for `Keyboard hook installed`; if that line is missing, restart
  FlowState.
- **"FlowState is already running" but you don't see the tray icon:** a
  previous instance may still be holding the single-instance lock. Check
  Task Manager for a leftover `FlowState.exe` (or `python.exe` in a dev
  setup), end it, then relaunch.
- **Transcript or screenshot lands in the wrong window:** FlowState
  pastes into whichever window was focused the moment you *started*
  recording -- if you switch windows mid-recording, that's where it'll
  land.
- **Transcription feels slow:** check Settings -> Model. If it says
  "Currently running on: CPU," no compatible NVIDIA GPU/CUDA was found,
  so FlowState fell back to a smaller model automatically -- this is
  expected on machines without an NVIDIA GPU, just slower than GPU mode.
- **Nothing happens for the first few seconds after launch:** the AI
  models are still loading in the background; give it a moment, or use
  the first-run setup dialog, which waits for both models before it lets
  you finish.
- **Screenshot capture isn't grabbing anything:** confirm the right mode
  is picked in Settings -> Capture (circle vs. Ctrl+drag), and that
  you're actively recording when you gesture -- capture only listens
  while a recording is in progress.
- **A model failed to download:** usually a network hiccup on first
  launch. Just restart FlowState to retry.

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
