# Stage 4 — Orchestration + smart fallback

Goal: wire everything into the full cycle and verify both the happy path
and the fallback path end-to-end.

## What a cycle does

```
audio buffer (last 3 h) ──> faster-whisper ──> transcript ──> shred audio
                                                   │
                              meaningful? ─────────┤
                              (≥25 words,          │ no
                               ≥8 content words)   ▼
                                   │ yes      60%: remix 2-3 past prompts (Ollama)
                                   ▼          40%: random curated painterly scene
                          Ollama crafts scene      │
                                   └───────┬───────┘
                                           ▼
                        + oil-painting style suffix (always)
                                           ▼
                              ComfyUI paints (~10-25 min)
                                           ▼
                  data\images\art_YYYYMMDD_HHMMSS.png  ──> TV updates itself
                                           ▼
                       prompt saved to history (fuel for future remixes)
```

Key properties:

- **No boring images.** An empty/thin transcript never reaches the image
  model. The fallback either remixes your own past successes or composes
  from ~60 hand-curated painterly elements (`prompts\fallback_elements.json`).
- **Degrades gracefully.** Ollama down → local remix/random compose still
  works. ComfyUI down → cycle logs an error and the TV keeps showing the
  previous artwork. Nothing crashes the loop.
- **No overlap.** A lock file prevents a manual trigger from colliding
  with a scheduled run.
- **History only stores winners** — prompts that actually produced an
  image — so remixes stay high quality. Capped at 200 entries.

## 1. Test one full cycle

With ComfyUI running and some clips in the buffer (talk near the mic for
a minute first):

```
scripts\run_cycle_now.bat
```

Watch the log lines walk through transcribe → prompt → generate. When it
finishes, the image is in `data\images\` and the prompt is in
`data\prompt_history.json`.

Then test the fallback explicitly:

```
.venv\Scripts\python -m artframe.orchestrator --once --force-fallback
```

## 2. Run the schedule

```
scripts\start_orchestrator.bat
```

This is the long-running loop: first artwork ~2 minutes after start, then
one every `schedule.interval_hours` (default 3). It also checks every
30 s for the **manual trigger**:

- run `scripts\trigger_now.bat`, or
- tap the bottom-right corner of the TV display, or
- create the file `data\trigger.flag` by any means you like.

> Why a loop instead of a Task Scheduler time trigger? The loop reacts to
> the trigger flag within seconds and keeps one simple process to manage.
> If you'd rather use Task Scheduler's repetition, schedule
> `orchestrator --once` every 3 h instead — both are supported.

## 3. Logs

Every component writes a rotating log in `data\logs\`:
`orchestrator.log`, `listener.log`, `transcriber.log`, `prompts.log`,
`generator.log`, `display.log`. Each cycle logs its prompt source
(`transcript` / `remix` / `random`) — the first thing to check when
you wonder "why did it paint *that*?"

## 4. Tuning knobs (config.yaml)

| Knob | Effect |
|---|---|
| `schedule.interval_hours` | how often a new painting appears |
| `prompting.min_words` / `min_content_words` | how chatty the room must be to drive the art |
| `prompting.remix_probability` | fallback flavor: history remix vs fresh random |
| `prompting.similarity_threshold` | repeat guard: re-roll scenes whose content-word overlap with the last `similarity_window` prompts exceeds this (1 = off) |
| `comfyui.steps` | biggest speed lever (14–25 sensible) |
| `prompting.style_suffix` | the enforced painting style — edit to taste |

**The repeat guard** keeps the frame from painting "yet another lighthouse
at sunset": every candidate scene is compared to recent history, and if
it overlaps too heavily it re-rolls (up to 3 attempts, keeping the least
repetitive candidate). Watch `prompts.log` for `repeat guard:` lines to
see it working.

## 5. Done when…

- [ ] `run_cycle_now.bat` produces an image from real room audio
- [ ] `--force-fallback` also produces a (good-looking!) image
- [ ] `trigger_now.bat` kicks the running loop within ~30 s

→ Continue to **STAGE5_KIOSK.md**
