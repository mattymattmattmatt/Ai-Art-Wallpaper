# AI Ambient Art Frame

A 70-inch TV that behaves like a living painting. Every few hours the
system listens to the room, transcribes what it heard, distills it into a
vivid scene, and paints it as a traditional **oil painting** — entirely
offline on a GMKtec G3 Plus (Intel N150, 16 GB RAM, no dGPU, Windows 11).

```
 ┌──────────────┐   speech-only WAV clips    ┌───────────────┐
 │  USB mic +   │ ─────────────────────────► │ rolling audio │
 │  WebRTC VAD  │   (silence never stored)   │    buffer     │
 └──────────────┘                            └───────┬───────┘
        24/7 listener                                │ every 3 h
                                                     ▼
                        ┌────────────────────────────────────────┐
                        │  ORCHESTRATOR (one cycle)              │
                        │  1. faster-whisper transcribes window  │
                        │     → audio deleted (privacy)          │
                        │  2. meaningful? Ollama crafts a scene  │
                        │     else: remix history / curated      │
                        │     random painterly scene             │
                        │  3. + enforced oil-painting style      │
                        │  4. ComfyUI (SD 1.5, CPU) paints it    │
                        └───────────────────┬────────────────────┘
                                            ▼
                              data\images\art_*.png
                                            ▼
                    Flask display server + Edge kiosk fullscreen
                          (crossfades to each new artwork)
```

100% local: faster-whisper, Ollama (qwen2.5:7b), ComfyUI (DreamShaper 8),
Flask. After the initial model downloads, the network cable can go.

## Build it, stage by stage

| Stage | Doc | You end up with |
|---|---|---|
| 1 | [docs/STAGE1_COMFYUI.md](docs/STAGE1_COMFYUI.md) | ComfyUI in CPU mode + your real minutes-per-image number |
| 2 | [docs/STAGE2_OLLAMA.md](docs/STAGE2_OLLAMA.md) | Local LLM writing painterly prompts |
| 3 | [docs/STAGE3_AUDIO.md](docs/STAGE3_AUDIO.md) | VAD listener + local transcription |
| 4 | [docs/STAGE4_ORCHESTRATION.md](docs/STAGE4_ORCHESTRATION.md) | Full pipeline with smart fallback |
| 5 | [docs/STAGE5_KIOSK.md](docs/STAGE5_KIOSK.md) | Boot-to-art fullscreen TV appliance |

Something broken? [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Quick reference

```bat
scripts\setup.ps1              :: one-time venv + pip install
scripts\start_comfyui.bat      :: ComfyUI server (edit its path first)
scripts\start_listener.bat     :: 24/7 room listener
scripts\start_display.bat      :: TV web server (port 8800)
scripts\start_orchestrator.bat :: the every-3-hours painting loop
scripts\run_cycle_now.bat      :: run ONE full cycle in a console (testing)
scripts\trigger_now.bat        :: ask the running loop to paint now
scripts\register_tasks.ps1     :: autostart all of it at logon (run once, admin)
```

Manual trigger, three ways: `trigger_now.bat`, tap the TV screen's
bottom-right corner, or create the file `data\trigger.flag`.

## Layout

```
artframe/            the Python package
  audio_listener.py    24/7 VAD speech capture → data/audio_buffer
  transcriber.py       faster-whisper, transcribe-and-shred
  prompt_builder.py    Ollama + meaningfulness check + fallback logic
  generator.py         ComfyUI HTTP API client
  orchestrator.py      the cycle + schedule loop + lock
  display_server.py    fullscreen kiosk page + /api/trigger + /api/status
config.yaml          every tunable, commented
workflows/           ComfyUI API-format workflow (SD 1.5 painterly)
prompts/             LLM system prompt + curated fallback elements
scripts/             Windows .bat/.ps1 helpers
docs/                stage-by-stage build guide
data/                runtime state (gitignored, safe to delete)
```

## Privacy

Audio never leaves the machine and never outlives its transcription:
clips are deleted the moment they're transcribed, only the latest
transcript is kept for debugging (config-gated), and no component talks
to anything beyond `127.0.0.1` / your LAN.

## Day-2 ideas

- Swap checkpoints seasonally (`comfyui.checkpoint`) — watercolor and
  gouache models exist too.
- Edit `prompting.style_suffix` to steer toward impressionism, Dutch
  Golden Age, tonalism…
- A resin-printed bezel mount for the mini PC behind the TV (you have
  the printer for it).
