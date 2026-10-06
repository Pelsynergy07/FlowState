# How FlowState works

A plain-English tour of what actually happens when you use FlowState, and
what the AI models are doing. Aimed at "I'm about to install this on my
machine, what is it actually doing" more than at contributing code.

## The short version

1. You press a hotkey. FlowState starts recording your microphone.
2. While you speak, FlowState transcribes overlapping audio windows locally
   with [Whisper](https://github.com/openai/whisper) and polishes completed
   sections in the background. Overlap supplies context at window boundaries;
   timestamps keep each window's words in their original order.
3. You press the hotkey again (or release it, for push-to-talk). FlowState
   finishes the remaining audio, joins the completed sections, lays out emails
   and lists, and pastes the complete result into the text field focused when
   you started. Slow or incomplete model polishing retains the complete source
   wording, with fast filler cleanup and layout rules still applied.
4. Nothing about your voice or the transcript ever leaves your machine.
   Both AI models run locally. Network access is used for model downloads
   from Hugging Face and app update checks/downloads from GitHub.

## The two AI models

**Speech-to-text: Whisper (large-v3-turbo, or a smaller CPU model).**
Runs via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). If
your machine has a compatible NVIDIA GPU, FlowState uses the full-size
`large-v3-turbo` model on the GPU. If not, it automatically falls back to
a much smaller model (`base.en`) that runs comfortably on CPU. Either way
this is what turns your audio into raw text.

Whisper is prompted with punctuated text (and, for each live section, the
words just before it), so it writes sentences with punctuation and capitals
rather than one long lowercase run.

**Text cleanup: a small local LLM (Qwen2.5-1.5B-Instruct).** On an NVIDIA
GPU it runs via [CTranslate2](https://github.com/OpenNMT/CTranslate2) (the
same runtime as Whisper; ~1.5 GB download); on other machines it runs on
the CPU via [llama.cpp](https://github.com/ggml-org/llama.cpp) (~1.1 GB).
Each machine downloads only the one it uses. This model lays text out:
emails get greeting, body and sign-off lines; enumerated items become
numbered or bulleted lists; long prose gets paragraphs; spelling slips are
fixed. Fast rules remove clear speech fillers and accidental repetitions,
recognize spoken list transitions, and format unambiguous dates.

Model output is aligned word by word with what you said
(`text/guard.py`). Punctuation, layout, spelling fixes and filler removal
are kept; any reworded, added or dropped word is put back exactly as you
said it. If the model summarizes or answers your dictation instead of
formatting it, its output is discarded. Speech is formatted while you talk,
so stopping leaves only the last few seconds to process.

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
  screenshots, plus the complete raw transcript for recovery. History is cleared
  when FlowState starts; a 7-day / 500 MB limit also applies during use.
- `config.json` -- your settings (shortcuts, microphone, capture mode,
  etc).
- `usage.sqlite3` -- persistent local statistics and, only after opting in,
  a bounded queue of content-free anonymous counts.
- `logs\flowstate.log` -- a rotating log file, the main way to debug
  anything that isn't behaving.

Audio, transcripts, screenshots, and clipboard contents are never uploaded.
Optional anonymous counters are described in [ANALYTICS.md](ANALYTICS.md).
Upgrading replaces app binaries while preserving this data folder and model caches.
Uninstalling FlowState deliberately
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
restores your previous clipboard text and images afterward. If you captured
screenshots, each one gets pasted the same way, right after the text, so
everything lands in one place without you doing anything extra.
