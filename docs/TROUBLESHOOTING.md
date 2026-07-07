# Troubleshooting

First stop, always: `data\logs\*.log`. Every component logs there with
timestamps, and the orchestrator logs which stage failed.

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

## Nuclear option

Everything in `data\` is disposable state. Stop the tasks, delete the
whole `data` folder, start again — the system rebuilds it from scratch
(you only lose the gallery and prompt history).
