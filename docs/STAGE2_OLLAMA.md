# Stage 2 — Ollama + a prompt-crafting model

Goal: a local LLM that turns messy room transcripts into vivid painting
prompts, and unloads itself afterwards so ComfyUI gets the RAM back.

## 1. Install Ollama

1. Download the Windows installer: <https://ollama.com/download/windows>
2. Run it. Ollama installs as a background service that autostarts with
   Windows — no scheduled task needed.
3. Verify in a new terminal:
   ```
   ollama --version
   ```

## 2. Pull a model

Recommended for prompt-crafting on 16 GB RAM (pick ONE):

```
ollama pull qwen2.5:7b-instruct     # default — excellent instruction following, ~4.7 GB
```
or
```
ollama pull llama3.1:8b             # slightly more creative prose, ~4.9 GB
```

`config.yaml → llm.model` defaults to `qwen2.5:7b-instruct`; change it if
you chose Llama. (If LLM steps ever feel too slow, `qwen2.5:3b-instruct`
is a solid lightweight fallback.)

## 3. Test it

```
ollama run qwen2.5:7b-instruct "Write a 60-word Stable Diffusion prompt for an oil painting of a rainy harbor. Output only the prompt."
```

Then test through the project's actual pipeline (after `scripts\setup.ps1`):

```
.venv\Scripts\python -m artframe.prompt_builder --text "we spent the whole weekend planning the camping trip up near the lake, hoping the rain holds off, the kids want to fish at dawn"
```

You should get one long comma-separated painterly prompt ending with the
oil-painting style suffix. Also try the fallback path:

```
.venv\Scripts\python -m artframe.prompt_builder --fallback
```

## 4. How the RAM ballet works

The N150 has 16 GB shared by everything. The pipeline is strictly
sequential and the config already handles it:

1. faster-whisper loads (~1 GB), transcribes, releases.
2. Ollama loads the 7B model (~5 GB), writes the prompt, then **unloads
   immediately** because we send `keep_alive: 0` with every request.
3. Only then does ComfyUI (~6 GB) start sampling.

Peak usage stays around 8–9 GB with no swapping. If you ever see heavy
disk thrash during generation, check Task Manager for a model that didn't
unload (`ollama ps` shows what's loaded).

## 5. Done when…

- [ ] `ollama list` shows your model
- [ ] `prompt_builder --text ...` returns a painterly prompt
- [ ] `prompt_builder --fallback` returns a painterly prompt

→ Continue to **STAGE3_AUDIO.md**
