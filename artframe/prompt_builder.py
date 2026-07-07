"""Turn a transcript into a painterly text-to-image prompt.

Decision tree (the "smart fallback"):

    transcript meaningful? ──yes──> Ollama crafts a scene from it
           │no
           ▼
    coin flip (remix_probability)
      ├── remix: blend 2-3 past successful prompts (Ollama, or local splice)
      └── fresh: compose a random painterly scene from curated elements

Whatever branch runs, the configured oil-painting style suffix is
appended, so every image comes out looking like traditional fine art.

Standalone test:
    python -m artframe.prompt_builder --text "kids talking about a camping trip"
    python -m artframe.prompt_builder --fallback
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

import requests

from artframe.config import PROJECT_ROOT, Config, load_config
from artframe.log_setup import get_logger

SYSTEM_PROMPT_FILE = PROJECT_ROOT / "prompts" / "llm_system_prompt.txt"
ELEMENTS_FILE = PROJECT_ROOT / "prompts" / "fallback_elements.json"

# Filler words that don't count toward "meaningful content".
_STOPWORDS = frozenset("""
a an the and or but if then so of to in on at for with about as is are was
were be been being am do does did have has had will would can could should
shall may might must not no yes ok okay yeah nah um uh hmm like just really
very that this these those there here it its it's i i'm you you're he she
they we me him her them us my your his their our mine what when where who
why how which know think get got go going went come came say said see saw
one two too also well right now dont don't im gonna wanna kinda sorta stuff
thing things something anything nothing
""".split())


# ---------------------------------------------------------------- utilities

def is_meaningful(transcript: str, cfg: Config) -> bool:
    words = re.findall(r"[a-zA-Z']+", transcript.lower())
    content = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    p = cfg["prompting"]
    return len(words) >= p["min_words"] and len(content) >= p["min_content_words"]


def _clean(text: str) -> str:
    """Squash an LLM reply down to one clean prompt line."""
    text = text.strip().strip('"').strip()
    # drop leading labels like "Prompt:" and any chain-of-thought preamble
    text = re.sub(r"^(here.{0,40}?:|prompt:)\s*", "", text, flags=re.I | re.S)
    text = " ".join(text.split())
    return text[:600].strip()


def _ollama(cfg: Config, system: str, user: str) -> str:
    """One non-streaming Ollama generation. Raises on any failure."""
    llm = cfg["llm"]
    resp = requests.post(
        f"{llm['base_url']}/api/generate",
        json={
            "model": llm["model"],
            "system": system,
            "prompt": user,
            "stream": False,
            "keep_alive": llm["keep_alive"],  # 0 = free RAM for ComfyUI right after
            "options": {
                "temperature": llm["temperature"],
                "num_predict": llm["max_tokens"],
            },
        },
        timeout=llm["timeout_seconds"],
    )
    resp.raise_for_status()
    out = _clean(resp.json()["response"])
    if len(out) < 30:
        raise ValueError(f"LLM reply too short: {out!r}")
    return out


# ------------------------------------------------------------------ history

def load_history(cfg: Config) -> list[dict]:
    path = cfg.path("paths", "history_file")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def append_history(cfg: Config, prompt: str, source: str) -> None:
    history = load_history(cfg)
    history.append({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": source, "prompt": prompt})
    history = history[-cfg["prompting"]["history_max_entries"]:]
    cfg.path("paths", "history_file").write_text(
        json.dumps(history, indent=2), encoding="utf-8")


# ------------------------------------------------------------ prompt makers

def craft_from_transcript(cfg: Config, transcript: str) -> str:
    system = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    user = (
        "Here is a transcript of ambient conversation from the room over the "
        "last few hours. Create the image prompt now.\n\nTRANSCRIPT:\n"
        + transcript[:6000]
    )
    return _ollama(cfg, system, user)


def compose_random(cfg: Config) -> str:
    """Offline-safe random painterly scene from curated elements."""
    e = json.loads(ELEMENTS_FILE.read_text(encoding="utf-8"))
    parts = [
        random.choice(e["subjects"]),
        random.choice(e["settings"]),
        random.choice(e["moods"]),
        random.choice(e["lighting"]),
        random.choice(e["palettes"]),
    ]
    return ", ".join(parts)


def remix_history(cfg: Config, history: list[dict]) -> str:
    """Blend elements of past successful prompts into a new scene."""
    picks = random.sample(history, k=min(3, len(history)))
    sources = "\n".join(f"- {p['prompt']}" for p in picks)
    system = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    user = (
        "There was no conversation in the room. Instead, creatively BLEND "
        "elements from these previous artwork prompts into one brand new, "
        "different scene. Do not copy any of them.\n\nPREVIOUS PROMPTS:\n"
        + sources
    )
    try:
        return _ollama(cfg, system, user)
    except Exception:
        # Ollama down? Splice fragments locally so the frame never goes stale.
        fragments = []
        for p in picks:
            bits = [b.strip() for b in p["prompt"].split(",") if b.strip()]
            fragments.extend(random.sample(bits, k=min(2, len(bits))))
        random.shuffle(fragments)
        return ", ".join(dict.fromkeys(fragments)) or compose_random(cfg)


def build_prompt(cfg: Config, transcript: str) -> tuple[str, str]:
    """Return (final_positive_prompt, source_tag)."""
    log = get_logger("prompts", cfg)
    p = cfg["prompting"]

    scene, source = None, None
    if transcript and is_meaningful(transcript, cfg):
        try:
            scene = craft_from_transcript(cfg, transcript)
            source = "transcript"
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM crafting failed (%r) — using fallback", exc)

    if scene is None:
        history = load_history(cfg)
        if history and random.random() < p["remix_probability"]:
            scene = remix_history(cfg, history)
            source = "remix"
        else:
            scene = compose_random(cfg)
            source = "random"

    final = f"{scene}, {p['style_suffix']}"
    log.info("prompt source=%s: %s", source, final)
    return final, source


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArtFrame prompt builder test")
    parser.add_argument("--text", default="", help="fake transcript to test with")
    parser.add_argument("--fallback", action="store_true",
                        help="force the fallback path")
    args = parser.parse_args()
    config = load_config()
    prompt, src = build_prompt(config, "" if args.fallback else args.text)
    print(f"[{src}] {prompt}")
