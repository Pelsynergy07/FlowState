# Running the same benchmark on your Windows PC

Yes—the benchmark includes separate runs for your NVIDIA graphics card and for CPU-only use.

1. Copy `FlowState-Windows-Benchmark.zip` onto the Windows PC and extract it. Keep the extracted folder separate from the FlowState app.
2. Install **Python 3.12** if it is not already installed. Enable its Python launcher during installation.
3. Open the extracted `bench` folder and double-click **WINDOWS-REVIEW-GPU.bat**. The package contains the same pinned FlowState source used on the Mac, so no coding or repository setup is needed. It creates a separate test environment and downloads any missing selected models.
4. Let that run finish. Then double-click **WINDOWS-CPU.bat**. Run these one after the other so they do not compete for resources.
5. Keep the entire `bench/results` folder. Those results can be combined with the Mac results, with each machine’s speed reported separately.

The launchers have been prepared on the Mac, but have not yet been executed on Windows. A setup error must be resolved before there can be a Windows result; a failed GPU run is never counted as a CPU substitute.

The ZIP contains the benchmark software and test descriptions. Large models, your recordings and the Mac’s software environment are excluded. The selected 100 public audio files are included so Windows can test the exact same recordings without downloading the full public archives. An internet connection is needed for initial setup/downloads; model inference runs locally. Your voice recordings are never uploaded by the benchmark.

Your 25 recordings can be added later using the recording sheet. Use the same files on both machines for a fair comparison, and check that the written reference matches what you actually said.

The review launcher compares Qwen 1.5B and 3B in the actual GPU format, tests all 300 text examples in normal and forced-AI modes, and runs the real Whisper turbo streaming combination. Audio uses the same 100-file sample as the Mac. The included README explains the larger optional comparison. Until the Windows runs, your recordings and human review are complete, keep the current FlowState defaults.
