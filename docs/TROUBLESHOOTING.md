# Troubleshooting

First stop, always: `data\logs\*.log`. Every component logs there with
timestamps, and the orchestrator logs which stage failed.

## Setup / Python

**`setup.ps1` fails building `webrtcvad-wheels`: "Microsoft Visual C++ 14.0 or greater is required"**
- This means `python` resolved to a very new release (3.13/3.14+) that
  doesn't have a prebuilt wheel yet for that package, so pip tried to
  compile it from source. Install **Python 3.11 (64-bit)** from
  <https://www.python.org/downloads/release/python-3119/> alongside your
  existing Python (no need to uninstall anything) — the Windows installer
  registers it with the `py` launcher automatically. Then delete the
  broken environment and re-run setup, which now prefers 3.11 via
  `py -3.11` automatically:
  ```powershell
  Remove-Item -Recurse -Force .venv
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
  ```
  The script prints "Using interpreter: py -3.11" when this worked.

**`python` shows a Microsoft Store prompt instead of a version number**
- Python isn't actually installed (or PATH hasn't refreshed). Install
  from python.org with "Add python.exe to PATH" checked, then open a
  **new** PowerShell window before trying again.

## Audio / listener

**No clips appear when I talk**
- `python -m artframe.audio_listener --list-devices` — is the headset
  listed with input channels? Is `audio.device_name` a fragment of that
  exact name?
- Windows mic privacy: Settings → Privacy & security → Microphone →
  allow desktop apps.
- Lower `vad_aggressiveness` to 1 (quiet/distant voices get through more).

**Clips appear constantly, even in silence**
- Raise `vad_aggressiveness` to 3.
- USB hum/hiss can read as voice — check Windows input level (~70-80%),
  and disable "listen to this device".

**`webrtcvad` import error**
- The package is `webrtcvad-wheels` (prebuilt for Windows). Reinstall:
  `.venv\Scripts\pip install --force-reinstall webrtcvad-wheels`

## Transcription

**Whisper model download blocked (offline setup)**
- Run `python -m artframe.transcriber --keep` once while online; the
  model caches to `%USERPROFILE%\.cache\huggingface` and works offline
  forever after.

**Transcripts are gibberish**
- Move the mic more centrally; VAD clips of far-field audio are hard.
- Step up from `tiny.en` to `base.en` (or `small.en` if you accept ~2×
  transcription time).

## Prompts / Ollama

**Every cycle uses `random`/`remix` even though people talked**
- Read `data\last_transcript.txt` — did speech actually make it to text?
- Lower `prompting.min_words` / `min_content_words`.

**Cycle log shows `LLM crafting failed`**
- Is the service up? `ollama ps` / `ollama list` in a terminal.
- Model name in `config.yaml` must exactly match `ollama list`.
- First call after boot loads the model from disk and can take a couple
  of minutes on the N150 — `llm.timeout_seconds: 300` covers it; don't
  reduce it much.

## ComfyUI / generation

**`ComfyUI is not reachable`**
- Is the console window from `start_comfyui.bat` open and showing the
  `127.0.0.1:8188` line? Did you edit the `COMFYUI_DIR` path in the bat?

**Workflow rejected (HTTP 400)**
- Almost always the checkpoint filename: `comfyui.checkpoint` in
  `config.yaml` must exactly match the file in
  `ComfyUI\models\checkpoints\`.

**Generation extremely slow (>40 min)**
- Power plan on *Best performance*; check Task Manager: if disk is at
  100% during sampling, RAM is exhausted — make sure Ollama unloaded
  (`ollama ps` should be empty mid-generation; `llm.keep_alive` must be 0).
- Drop `comfyui.steps` to 14–16.

**Images look digital/photographic instead of painted**
- Strengthen `prompting.style_suffix`, raise `comfyui.cfg` to 7–7.5,
  and confirm the negative prompt survived into the workflow
  (check `generator.log` / ComfyUI console).

## Display / kiosk

**TV page is black with "Waiting for the first artwork…"**
- Normal until the first cycle completes. Confirm `data\images\` has
  images and `http://localhost:8800/api/latest` returns a filename.

**Kiosk didn't start at boot**
- `Get-ScheduledTask "ArtFrame*"` — all five present and "Ready"?
- The kiosk bat waits 20 s for the display server; if your machine boots
  slower, raise the `timeout /t 20` in `scripts\start_kiosk.bat`.

**Two cycles seem stuck / nothing generates**
- A crashed cycle can leave `data\cycle.lock`; it auto-expires after the
  generation timeout + 30 min, or just delete the file.

**A dot in the System health row is red**
- **Mic** — the listener stopped beating (>2 min). Check `listener.log`;
  usually the USB headset was unplugged. The listener auto-restarts, so
  a brief red after replugging is normal.
- **Cycles** — the orchestrator loop hasn't beaten in >6 min. Check
  `orchestrator.log`; restart the "ArtFrame Orchestrator" task.
- **Painter** — ComfyUI isn't answering on port 8188. Is its console
  window still open?
- **Ollama** — the Ollama service isn't answering. `ollama list` in a
  terminal; note the frame still works without it (fallback prompts).

**Gallery thumbnails don't load**
- Pillow may be missing (added later in the project):
  `.venv\Scripts\pip install -r requirements.txt`, then restart the
  "ArtFrame Display" task.

## Nuclear option

Everything in `data\` is disposable state. Stop the tasks, delete the
whole `data` folder, start again — the system rebuilds it from scratch
(you only lose the gallery and prompt history).
