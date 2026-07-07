@echo off
rem Starts the 24/7 room listener (VAD speech capture).
cd /d "%~dp0.."
.\.venv\Scripts\python.exe -m artframe.audio_listener
