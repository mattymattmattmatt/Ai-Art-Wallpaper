@echo off
rem Starts the scheduler loop: a new artwork every interval_hours,
rem plus instant response to the manual trigger flag.
cd /d "%~dp0.."
.\.venv\Scripts\python.exe -m artframe.orchestrator --loop
