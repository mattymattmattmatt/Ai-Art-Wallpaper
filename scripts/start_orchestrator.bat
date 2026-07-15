@echo off
rem Starts the continuous painting loop: a new artwork begins
rem gap_minutes after the previous one finishes, plus instant
rem response to the manual trigger flag.
cd /d "%~dp0.."
.\.venv\Scripts\python.exe -m artframe.orchestrator --loop
