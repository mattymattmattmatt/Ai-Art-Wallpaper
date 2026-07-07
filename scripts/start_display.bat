@echo off
rem Starts the fullscreen display web server on port 8800.
cd /d "%~dp0.."
.\.venv\Scripts\python.exe -m artframe.display_server
