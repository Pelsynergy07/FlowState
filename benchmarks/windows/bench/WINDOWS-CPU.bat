@echo off
cd /d "%~dp0"
py -3.12 setup_benchmark.py --tier t2
if errorlevel 1 goto error
..\.venv-t2\Scripts\python.exe run_all.py --tier t2 --stage all --download
if errorlevel 1 goto error
echo CPU benchmark ended. Open REPORT.html and check any missing tests.
pause
exit /b 0
:error
echo Benchmark needs attention. The error above has been kept visible. No FlowState files were changed.
pause
exit /b 1
