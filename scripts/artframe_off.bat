@echo off
rem Turn the Art Frame OFF and reclaim the PC. Requests admin rights,
rem then disables autostart and stops everything currently running.
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"%~dp0artframe_off.ps1\"'"
