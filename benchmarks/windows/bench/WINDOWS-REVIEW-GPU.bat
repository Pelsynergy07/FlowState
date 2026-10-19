@echo off
cd /d "%~dp0"
py -3.12 setup_benchmark.py --tier t1
if errorlevel 1 goto end
..\.venv-t1\Scripts\python.exe run_windows_review.py
:end
pause
