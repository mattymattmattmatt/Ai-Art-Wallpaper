"""ComfyUI API client — submit the painterly workflow and retrieve the image.

Talks to a locally running ComfyUI (started with run_cpu.bat) over its
HTTP API: POST /prompt to queue, poll /history/<id> until done, then
GET /view to download the saved image.

Standalone test (ComfyUI must be running):
    python -m artframe.generator --prompt "a lighthouse on cliffs at sunset"
"""

from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path

import requests

from artframe.config import PROJECT_ROOT, Config, load_config
from artframe.log_setup import get_logger
from artframe.status import beat


class GenerationError(RuntimeError):
    pass


def _load_workflow(cfg: Config, positive: str, negative: str) -> dict:
    """Load the API-format workflow and fill in all configurable fields."""
    wf_path = Path(cfg["comfyui"]["workflow"])
    if not wf_path.is_absolute():
        wf_path = PROJECT_ROOT / wf_path
    wf = json.loads(wf_path.read_text(encoding="utf-8"))

    c = cfg["comfyui"]
    seed = random.randint(0, 2**32 - 1)

    wf["4"]["inputs"]["ckpt_name"] = c["checkpoint"]
    wf["5"]["inputs"]["width"] = c["gen_width"]
    wf["5"]["inputs"]["height"] = c["gen_height"]
    wf["6"]["inputs"]["text"] = positive
    wf["7"]["inputs"]["text"] = negative

    # base sampling pass
    wf["3"]["inputs"]["seed"] = seed
    wf["3"]["inputs"]["steps"] = c["steps"]
    wf["3"]["inputs"]["cfg"] = c["cfg"]
    wf["3"]["inputs"]["sampler_name"] = c["sampler"]
    wf["3"]["inputs"]["scheduler"] = c["scheduler"]

    if c.get("hires_enable", False):
        # hires-fix: latent-upscale, then a lower-denoise refinement pass
        wf["11"]["inputs"]["width"] = c["hires_width"]
        wf["11"]["inputs"]["height"] = c["hires_height"]
        wf["12"]["inputs"]["seed"] = seed
        wf["12"]["inputs"]["steps"] = c["hires_steps"]
        wf["12"]["inputs"]["cfg"] = c["cfg"]
        wf["12"]["inputs"]["sampler_name"] = c["sampler"]
        wf["12"]["inputs"]["scheduler"] = c["scheduler"]
        wf["12"]["inputs"]["denoise"] = c["hires_denoise"]
    else:
        # single-pass mode: decode straight from the base sampler and drop
        # the hires nodes so ComfyUI never runs the second pass.
        wf["8"]["inputs"]["samples"] = ["3", 0]
        wf.pop("11", None)
        wf.pop("12", None)

    wf["9"]["inputs"]["width"] = c["display_width"]
    wf["9"]["inputs"]["height"] = c["display_height"]
    return wf


def generate(cfg: Config, positive: str, negative: str, out_path: Path) -> Path:
    """Run one generation; save the image to out_path. Blocking."""
    log = get_logger("generator", cfg)
    base = cfg["comfyui"]["base_url"]
    client_id = str(uuid.uuid4())
    workflow = _load_workflow(cfg, positive, negative)

    log.info("queueing generation (%dx%d, %d steps)...",
             cfg["comfyui"]["gen_width"], cfg["comfyui"]["gen_height"],
             cfg["comfyui"]["steps"])
    resp = requests.post(f"{base}/prompt",
                         json={"prompt": workflow, "client_id": client_id},
                         timeout=30)
    if resp.status_code != 200:
        raise GenerationError(f"ComfyUI rejected the workflow: {resp.text[:500]}")
    prompt_id = resp.json()["prompt_id"]

    deadline = time.monotonic() + cfg["comfyui"]["timeout_minutes"] * 60
    started = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(5)
        # generation is the longest stage — keep the cycle engine's
        # liveness fresh so the health row doesn't false-alarm
        beat(cfg, "orchestrator")
        hist = requests.get(f"{base}/history/{prompt_id}", timeout=30).json()
        if prompt_id not in hist:
            continue  # still queued / running
        entry = hist[prompt_id]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise GenerationError(f"ComfyUI reported an error: {status}")
        images = [
            img
            for node in entry.get("outputs", {}).values()
            for img in node.get("images", [])
        ]
        if not images:
            raise GenerationError("workflow finished but produced no image")
        img = images[0]
        data = requests.get(
            f"{base}/view",
            params={"filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output")},
            timeout=120,
        ).content
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        log.info("image saved to %s (%.1f min)", out_path.name,
                 (time.monotonic() - started) / 60)
        return out_path

    raise GenerationError(
        f"generation timed out after {cfg['comfyui']['timeout_minutes']} min")


def check_server(cfg: Config) -> bool:
    try:
        requests.get(f"{cfg['comfyui']['base_url']}/system_stats", timeout=10)
        return True
    except requests.RequestException:
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArtFrame generator test")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    config = load_config()
    positive_prompt = f"{args.prompt}, {config['prompting']['style_suffix']}"
    target = config.path("paths", "images_dir") / time.strftime(
        "art_%Y%m%d_%H%M%S.png")
    generate(config, positive_prompt, config["prompting"]["negative_prompt"], target)
    print(f"done: {target}")
