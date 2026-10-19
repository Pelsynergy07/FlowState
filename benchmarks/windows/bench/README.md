# FlowState Benchmarks

This is a separate, local benchmark project. It does not change FlowState, choose a new app default, or upload recordings. The recommendation remains to keep current models until all required evidence passes.

## For the owner

Open the local progress screen while a benchmark is running. It shows actual saved results, not simulated progress. Read REPORT.html for the detailed, readable report. REPORT.md is the same report in a text format. Interim reports identify missing tests; they are not a final verdict.

Your recording instructions are in data/RECORDING_SHEET.html. Record each clip once and preserve its original file. If you say different words, correct the reference before scoring. Use your natural accent. Hindi clips are optional examples that you can replace with languages you actually use. The long clips have duration targets, not measured durations.

The full project lives beside FlowState in `FlowState Benchmarks`. Its Python environment is `FlowState Benchmarks/.venv`; do not use FlowState's own environment.

## Mac setup and runs

Python 3.12 is required. On this Mac the interpreter is `/opt/homebrew/bin/python3.12`.

```sh
/opt/homebrew/bin/python3.12 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements.txt
```

For a CPU baseline build of llama.cpp on Apple Silicon, set `CMAKE_ARGS="-DGGML_METAL=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=Apple"` during installation. A Metal build must be separate and explicitly labelled; it is not a CPU timing.

```sh
../.venv/bin/python run_all.py --tier t3 --stage format --download
../.venv/bin/python run_all.py --tier t3 --stage audio --download
../.venv/bin/python dashboard.py
```

The first formatter stage downloads roughly 3 GB of selected weights. The entire ungated proposed matrix has 25.756869158 GB of selected weights before native Mac additions, public audio, software, source conversions, and CoreML compile caches. These are sums of verified upstream file sizes, not measured traffic. Exact sizes, commits and files are in model_manifest.json and MODEL_PLAN.md.

## Windows setup and one-command runs

Install Python 3.12 from python.org. Copy the `bench` folder onto the Windows computer. Keep it outside FlowState. Set `FLOWSTATE_SRC` to the full path of FlowState's `src` folder if it is not `~/Desktop/AI builds/FlowState/src`.

From the copied `bench` folder:

```powershell
py -3.12 setup_benchmark.py --tier t1
..\.venv-t1\Scripts\python.exe run_all.py --tier t1 --stage all --download
```

For CPU-only results, use the **separate CPU environment** so CPU ONNX Runtime and GPU ONNX Runtime are not installed together. Both environments can share the same bench folder:

```powershell
py -3.12 setup_benchmark.py --tier t2
..\.venv-t2\Scripts\python.exe run_all.py --tier t2 --stage all --download
```

T2 hides CUDA and limits backend threads to four. T1 uses Whisper CT2 float16 and Qwen CT2 int8_float16 on CUDA. Missing CUDA libraries must produce failed/missing results; they must never silently become GPU timings from a CPU fallback. GPU ONNX Runtime must expose CUDAExecutionProvider. Record the installed NVIDIA driver and VRAM through environment.json.

Windows setup and execution instructions are provided for handoff; this Mac cannot verify that Windows runs pass. Extended Qwen CT2 conversions must be generated before their conditions can run; download approval does not mean a conversion has succeeded. `--stage format` uses the shortlist, while the full GPU model list includes source conversions performed by the full runner.

## Result files

Each run writes `results/<machine>/<UTC timestamp>-<test>/environment.json` and raw JSONL measurements. Formatter runs also record prompt-free raw model responses, guard decisions, load times and resources. The dedicated speed runner performs three warm-ups and ten timed trials per input; it reports median and p95 in the report. Early timing protocol v1 used repetitive long input and can short-circuit through rejection. Protocol v2 uses natural prose; compare identical protocols and input conditions. Existing v1 files are retained as exploratory evidence, not deleted.

`python analyze.py` rebuilds reports, CSV summaries, charts and blind review sheets from completed runs. Keep the entire results folder when transferring measurements between machines. It contains source/package fingerprints needed for comparisons. Do not mix timing results across machines.

`HUMAN_REVIEW.csv` hides model identities; grade A/B/tie and note whether both are unacceptable. The key stays in results/BLIND_REVIEW_KEY.csv. Review faithfulness first, then layout, then punctuation. No model replacement qualifies until human review and owner-voice tests pass.

## Speech data

`prepare_audio.py --download` retrieves LibriSpeech test-clean/test-other from OpenSLR (CC BY 4.0; https://www.openslr.org/12/). Seed 1729 selects 300 utterances from each. Ten chapter concatenations include 250ms digital gaps. Synthetic coloured-noise copies at 10 and 5 dB SNR supplement natural speech and are explicitly labelled. No MUSAN, natural accent coverage, punctuation references or word alignments are claimed from these generated files.

`import_recordings.py <folder> --references <verified JSON>` converts recordings locally to mono 16 kHz PCM16 WAV. References must include `verified: true` for every clip before it is scored; the generated script references deliberately do not assert that the owner spoke them exactly. Never upload voice recordings to a remote inference API or judge.

## Native Mac Parakeet

Portable ONNX versions and Apple CoreML versions are separate conditions. `download_native.py` downloads immutable native model files. `native/` is an offline-only Swift adapter using FluidAudio commit `6428e29186573c6d33c598e25d460e6690bc0ee1` (the dependency pinned by the inspected BetterVoice checkout). CoreML compile/load times can be long and must not be hidden as download time or excluded from first-load reporting. Native runtime build success and tests must be recorded; a downloaded CoreML bundle is not a benchmark result.

Native model revisions and downloaded-file hashes are in native_manifest.json. The compact Redux model is separately trained, not merely a lossless smaller package of standard Parakeet. It must pass its own recognition tests. No mobile or Windows runtime equivalence is assumed.

## Fidelity and limits

The benchmark imports only safe FlowState text modules and ASR helpers. Streaming processing is an attributed adaptation of the current source's window/seam/gap/final-guard code, with a different capture scheduler. It never instantiates StreamingDictation. Event-driven timing uses actual processing times but does not reproduce live capture threads and cancellation exactly. Seam-error and per-minute drift claims require reference word alignments; they are not fabricated from overall WER.

Exact matching to one hand-authored reference is not the acceptance test. Layout checks are proxies, the content guard is not an independent judge, and language pass-through needs review. A strong final recommendation requires the complete owner-voice, cross-device, streaming, deadline, preservation and blind-review evidence described in REPORT.md.

## Full versus shortlist runs

The default matrix is the smaller-model shortlist. Add `--matrix full` to include the larger 3B quality reference, the 1.7B model and CT2 conversion conditions. Full runs download additional pinned source weights and can take substantially longer. Gated Gemma/Llama conditions remain optional and require publisher access. Windows launchers use separate `.venv-t1` and `.venv-t2` environments; they share only benchmark data/models. Owner recordings are included automatically when a verified owner_manifest.jsonl is present.

## Current quick decision plan

At the owner's request, `quick_profile.json` selects 100 varied audio examples and 100 text examples, preserving all 15 text categories. Previously completed larger runs remain on disk; the report compares the selected common IDs. The quick screen uses three long recordings, keeps ten timed trials after warm-up, and defers the larger-model extras and exhaustive combinations. This gives directional guidance sooner, with wider statistical uncertainty. Windows runs use this same profile when the profile file is present.

## Second-review corrections

The formatting report is restored to all 300 rows; the 100-file audio screen remains. `run_format.py --full-set --mode forced --budgets 600 --repeats 1` explicitly enables polishing and lifts the CPU length skip while preserving the app prompt, chunking, guard and final rules. It is a diagnostic, separate from shipped behavior. Per-category results are saved in results/format_by_category.csv.

The automated Qwen3 judge is withdrawn from scoring. Only actual entered HUMAN_REVIEW.csv votes count as human grades. Blank sheets remain missing evidence.

The portable ONNX adapter now recognizes both leading spaces and raw SentencePiece markers as word starts. The installed onnx-asr library replaces the latter with spaces. Old phrase-as-word streaming results are excluded from the current comparison; raw files are retained. Token-derived word ends are still estimated and have no hand-aligned accuracy claim.

Use WINDOWS-REVIEW-GPU.bat for the actual Windows/CUDA follow-up: Qwen 1.5B CT2 int8, converted Qwen 3B CT2 int8, full-set automatic/forced conditions, and Whisper turbo plus CT2 formatting in the streaming simulation. It fails rather than silently running GPU conditions on CPU. This launcher is prepared on the Mac and remains untested on Windows. The 3B conversion needs its pinned full source weights once; resulting files and hashes are recorded separately.

The Windows handoff includes a pinned, unchanged copy of the audited FlowState Python source, used read-only. Setup can use it automatically without asking the owner to clone a repository. Its original commit and every Python-file SHA256 are verified and recorded; an altered snapshot stops the benchmark. Advanced users can point FLOWSTATE_SRC at another source checkout, which is fingerprinted separately. No installed FlowState app is edited.
