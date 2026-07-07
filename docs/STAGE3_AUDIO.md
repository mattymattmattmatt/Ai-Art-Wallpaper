# Stage 3 — Audio capture, VAD, and local transcription

Goal: a 24/7 listener that stores **only speech** (never silence) in a
rolling buffer, and a transcriber that turns the last few hours of clips
into text — then deletes the audio.

## 1. Set up the Python environment

Install **Python 3.11 (64-bit)** from <https://www.python.org/downloads/>
(tick *Add python.exe to PATH*). Then in the project root:

```
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

This creates `.venv` and installs everything in `requirements.txt`
(sounddevice, webrtcvad-wheels, faster-whisper, flask, …).

## 2. Point it at your USB headset mic

```
.venv\Scripts\python -m artframe.audio_listener --list-devices
```

Find your headset in the list and copy a distinctive fragment of its name
(e.g. `USB Headset`) into `config.yaml`:

```yaml
audio:
  device_name: "USB Headset"
```

Windows tip: Settings → Privacy & security → Microphone → allow desktop
apps to access the microphone.

## 3. Test the listener

```
scripts\start_listener.bat
```

Talk near the mic for ~10 seconds, then stay quiet. Within a few seconds
you should see `saved clip_....wav (X.Xs)` in the console, and the file
appears in `data\audio_buffer\`. Notes:

- Silence produces **no files at all** — that's the VAD working.
- TV/music in the room will also trigger it; that's fine (and often makes
  fun artwork), but you can raise `vad_aggressiveness` to 3 to be stricter.
- Clips are capped at 60 s and the whole buffer at 500 MB (oldest deleted).

Leave it running; it's designed to run forever and auto-restarts itself
if the USB device hiccups.

## 4. Test transcription

The first run downloads the Whisper model (~150 MB for `base.en`) into the
local cache — after that it's fully offline.

```
.venv\Scripts\python -m artframe.transcriber --keep
```

`--keep` preserves the audio files while you're testing. Without it, the
transcriber follows the privacy config and **deletes each clip right after
transcribing it**. Check the output text and the timing in the console.

Speed guidance for the N150 (per minute of speech):
- `tiny.en` ≈ 15–25 s — use if your rooms are very chatty
- `base.en` ≈ 30–60 s — default, noticeably better accuracy

Change `transcription.model` in `config.yaml` to switch.

## 5. Privacy model

- Raw audio only ever exists in `data\audio_buffer\` on your own disk.
- Every clip is deleted immediately after transcription
  (`privacy.delete_audio_after_transcription: true`).
- Only the most recent transcript is kept (`data\last_transcript.txt`)
  for debugging; set `privacy.keep_last_transcript: false` to disable.
- Nothing is ever sent anywhere — there is no network code that leaves
  `127.0.0.1` except the local LAN display page.

## 6. Done when…

- [ ] Speaking creates clips in `data\audio_buffer\`; silence creates nothing
- [ ] `transcriber --keep` prints a reasonable transcript
- [ ] You've picked `tiny.en` vs `base.en`

→ Continue to **STAGE4_ORCHESTRATION.md**
