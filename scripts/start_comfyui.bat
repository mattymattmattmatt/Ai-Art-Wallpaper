@echo off
rem Starts ComfyUI in CPU mode.
rem EDIT THIS PATH to where you extracted the ComfyUI portable zip:
set COMFYUI_DIR=C:\ComfyUI_windows_portable

cd /d "%COMFYUI_DIR%"
.\python_embeded\python.exe -s ComfyUI\main.py --cpu --listen 127.0.0.1 --port 8188
