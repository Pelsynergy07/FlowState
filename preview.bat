@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe scripts\preview_gui.py %*
