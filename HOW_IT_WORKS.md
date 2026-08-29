# How FlowState works

A plain-English tour of what actually happens when you use FlowState, and
what the AI models are doing. Aimed at "I'm about to install this on my
machine, what is it actually doing" more than at contributing code.

## The short version

1. You press a hotkey. FlowState starts recording your microphone.
2. You press the hotkey again (or release it, for push-to-talk).
   FlowState stops recording, transcribes the audio locally with
   [Whisper](https://github.com/openai/whisper), cleans up the text with a
   small local language model, and pastes the result into whatever text
   field was focused when you started.
3. Nothing about your voice or the transcript ever leaves your machine.
   Both AI models run locally; the only network activity FlowState ever
   does is downloading those models once, from Hugging Face, the first
   time each is needed.

## The two AI models

**Speech-to-text: Whisper (large-v3-turbo, or a smaller CPU model).**
Runs via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). If
your machine has a compatible NVIDIA GPU, FlowState uses the full-size
`large-v3-turbo` model on the GPU. If not, it automatically falls back to
a much smaller model (`base.en`) that runs comfortably on CPU. Either way
this is what turns your audio into raw text.

**Text cleanup: a small local LLM (Qwen2.5-1.5B-Instruct).** Runs via
[llama.cpp](https://github.com/ggml-org/llama.cpp), CPU-only (deliberately
-- see the comment in `text/formatter.py` for why). Raw transcripts read
like speech, not writing: run-on sentences, "number one... number
two..." instead of an actual list, no punctuation. This model turns that
into properly formatted text -- real numbered lists, correct
capitalization and punctuation, a greeting/sign-off if you were clearly
dictating a message to someone. It's given a strict instruction to only
reformat, never to respond to or act on what you said, even if a
transcript happens to read like a question or a command.

Both models are ordinary, publicly available open models -- nothing
proprietary or FlowState-specific about them.

## Screenshot capture

While recording, you can also grab an annotated screenshot: either draw a
loop with your mouse (circle mode) or hold Ctrl and drag a box (drag
mode). FlowState screenshots that monitor, draws a highlight around the
area you indicated, and saves it into that recording's session folder.
If you took any screenshots, the pasted text ends with a short block
naming each one, when it was taken, and what you were saying around that
moment -- so if you say "look at this," whoever (or whatever) reads the
pasted text can tell which screenshot you meant.

## Where things are stored

Everything lives under `%LOCALAPPDATA%\FlowState`:

- `models\` -- the downloaded AI models.
- `sessions\` -- one folder per recording: the transcript and any
  screenshots. Kept for a while, then pruned automatically.
- `config.json` -- your settings (shortcuts, microphone, capture mode,
  etc).
- `logs\flowstate.log` -- a rotating log file, the main way to debug
  anything that isn't behaving.

None of it is uploaded anywhere. Uninstalling FlowState deliberately
leaves this folder alone (your session history and downloaded models
aren't deleted out from under you), so remove it by hand if you want a
completely clean uninstall.

## The hotkey mechanism

FlowState listens for its hotkeys with a low-level Windows keyboard hook,
which is what lets it recognize a chord like `Ctrl+Shift+Space` globally
(in any app) without swallowing every other keystroke you type. It only
intercepts the exact key combinations you've configured; everything else
passes through untouched.

## Pasting

FlowState puts the cleaned-up text on your clipboard and simulates
Ctrl+V into whichever window had focus when you started recording, then
restores your previous clipboard contents afterward. If you captured
screenshots, each one gets pasted the same way, right after the text, so
everything lands in one place without you doing anything extra.
