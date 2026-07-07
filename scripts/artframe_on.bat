@echo off
rem Turn the Art Frame back ON. Requests admin rights, re-enables
rem autostart and starts all components now (no reboot needed).
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"%~dp0artframe_on.ps1\"'"
