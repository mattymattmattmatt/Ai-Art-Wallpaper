@echo off
rem Runs ONE full cycle right now in this window (great for testing).
cd /d "%~dp0.."
.\.venv\Scripts\python.exe -m artframe.orchestrator --once
pause
