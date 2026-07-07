@echo off
rem Asks the running orchestrator loop to paint a new artwork ASAP
rem (equivalent to tapping the bottom-right corner of the TV page).
cd /d "%~dp0.."
if not exist data mkdir data
echo now> data\trigger.flag
echo Trigger set - the orchestrator will start a new painting within 30 seconds.
pause
