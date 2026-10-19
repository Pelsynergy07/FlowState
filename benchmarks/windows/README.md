# Windows model comparison

This is the benchmark used for the Mac comparison, including the same 100 public audio samples and a verified FlowState source snapshot. The FlowState application is unchanged.

1. Install Python 3.12 with the Python launcher.
2. Open `bench` and run `WINDOWS-REVIEW-GPU.bat` on your NVIDIA Windows computer.
3. After it finishes, run `WINDOWS-CPU.bat`.
4. Save the entire `bench/results` folder for comparison with the Mac.

Models download on the first run. No personal recordings or model weights are included in Git. Windows launchers were prepared on Mac and still need to be verified on Windows. See `WINDOWS_START_HERE.md` for details.
