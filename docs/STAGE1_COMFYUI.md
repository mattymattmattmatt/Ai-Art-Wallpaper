# Stage 1 — ComfyUI on the N150 (CPU mode) + first test image

Goal: get ComfyUI generating locally and **measure real generation time**
on your exact hardware. Everything else is tuned around that number.

## 1. Install ComfyUI (portable build)

1. Download the Windows portable build (~1.5 GB):
   <https://github.com/comfyanonymous/ComfyUI/releases/latest>
   — grab `ComfyUI_windows_portable_nvidia.7z` (it includes CPU mode; the
   name just reflects the bundled CUDA wheels, which we won't use).
2. Extract with 7-Zip to **`C:\ComfyUI_windows_portable`**
   (if you choose another location, edit `scripts\start_comfyui.bat`).
3. Start it in CPU mode by double-clicking
   `C:\ComfyUI_windows_portable\run_cpu.bat`
   or using this repo's `scripts\start_comfyui.bat`.
4. When the console prints `To see the GUI go to: http://127.0.0.1:8188`,
   open that URL in a browser. That's the whole install.

## 2. Download a painterly SD 1.5 model

SD 1.5 checkpoints (~2 GB) are the right weight class for a CPU-only N150.
Recommended, all free:

| Model | Why | Link |
|---|---|---|
| **DreamShaper 8** (default) | Excellent painterly range, great with style prompts | <https://civitai.com/models/4384?modelVersionId=128713> or <https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors> |
| Deliberate v2 | Rich classical/oil aesthetics | <https://huggingface.co/XpucT/Deliberate/resolve/main/Deliberate_v2.safetensors> |
| ClassipeintXL alt: **Colorful v3.1** | Vivid traditional color handling | <https://civitai.com/models/7279> |

Save the file as:

```
C:\ComfyUI_windows_portable\ComfyUI\models\checkpoints\dreamshaper_8.safetensors
```

The filename must match `comfyui.checkpoint` in `config.yaml`. If you pick a
different model, update that config value.

## 3. Generate a test image and time it

In the ComfyUI browser UI, the default workflow appears on first load:

1. In **Load Checkpoint** pick `dreamshaper_8.safetensors`.
2. Set the latent size to **896 × 504** (our generation resolution).
3. Positive prompt (paste):
   ```
   a lighthouse standing on weathered cliffs at sunset, traditional oil painting on canvas, impasto, thick textured brushstrokes, visible canvas weave, rich harmonious pigments, dramatic natural lighting, masterpiece, highly detailed
   ```
4. Negative prompt (paste):
   ```
   photograph, photorealistic, 3d render, digital art, anime, cartoon, watermark, signature, text, lowres, blurry, worst quality
   ```
5. KSampler: **20 steps, cfg 6.5, sampler `dpmpp_2m`, scheduler `karras`**.
6. Click **Queue Prompt** and note the wall-clock time.

**Expected on the N150: roughly 10–25 minutes.** Write your number down.

You can also test through this repo's API client once Python is set up
(Stage 3's `setup.ps1` — or run it now):

```
.venv\Scripts\python -m artframe.generator --prompt "a lighthouse on weathered cliffs at sunset"
```

## 4. N150 performance tuning

- **Power plan**: Settings → System → Power → *Best performance*. A
  throttled N150 can double generation time.
- **Steps are your lever**: 20 → 14 steps cuts ~30% of the time with a
  modest quality cost. Adjust `comfyui.steps` in `config.yaml`.
- **Resolution is quadratic**: 896×504 is the sweet spot for the *base*
  pass. Don't generate at 1080p/4K directly — SD 1.5 degrades above
  ~768px anyway; we lanczos-upscale to `comfyui.display_width/height` in
  the workflow instead, which is near-free on CPU regardless of target
  size (1080p or native 4K both work — set it to match your TV).
- **Detail vs. time — the hires-fix pass**: `comfyui.hires_enable: true`
  (the default) adds a second sampling pass at `hires_width/height`
  (default 1280×720) that puts *real* detail into the image before the
  final upscale, so it doesn't look soft on a big 4K panel. It roughly
  doubles generation time (two passes) — expect ~25–35 min total on the
  N150. Push `hires_width/height` to 1536×864 for even more detail, or
  set `hires_enable: false` to go back to fast single-pass mode. The
  base `steps` drive the first pass; `hires_steps` (default 14) the
  second.
- **RAM**: ComfyUI CPU mode + SD 1.5 uses ~6 GB. With 16 GB you're fine
  as long as Ollama unloads between calls (already configured:
  `llm.keep_alive: 0`).
- Leave the ComfyUI console window minimized, not closed — it's the server.
- Optional deep-dive: Intel's OpenVINO custom nodes
  (<https://github.com/openvinotoolkit/openvino_contrib>) can accelerate
  UHD iGPUs, but they add fragility. Get the plain CPU pipeline working
  first; revisit only if your measured time is unacceptable.

## 5. Done when…

- [ ] `http://127.0.0.1:8188` loads
- [ ] A 896×504 painterly test image generates successfully
- [ ] You know your real minutes-per-image number

→ Continue to **STAGE2_OLLAMA.md**
