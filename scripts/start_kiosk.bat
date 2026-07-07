@echo off
rem Opens Microsoft Edge fullscreen on the art display.
rem Waits for the display server to come up first.
timeout /t 20 /nobreak >nul
start "" msedge --kiosk http://localhost:8800 --edge-kiosk-type=fullscreen --no-first-run
