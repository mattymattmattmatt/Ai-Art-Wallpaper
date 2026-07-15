"""Tiny shared status file so the display panel can show live pipeline state.

The orchestrator calls set_status() as it moves through a cycle; the
display server reads it for the /api/status endpoint. Writes are atomic
(temp file + replace) so the display never reads a half-written file.

Stages: idle | transcribing | prompting | generating | error
"""

from __future__ import annotations

import json
import os
import time

from artframe.config import Config


def set_status(cfg: Config, stage: str, message: str = "",
               prompt: str | None = None, source: str | None = None,
               expected_seconds: float | None = None) -> None:
    path = cfg.path("paths", "status_file")
    data = read_status(cfg)
    now = time.time()

    # Track when we ENTERED the generating stage, so the UI can show elapsed.
    if stage == "generating" and data.get("stage") != "generating":
        data["generating_since"] = now
    if stage != "generating":
        data.pop("generating_since", None)
        data.pop("expected_seconds", None)
    elif expected_seconds is not None:
        # rolling estimate of how long this painting should take,
        # so the display can draw a progress bar
        data["expected_seconds"] = expected_seconds

    data.update({
        "stage": stage,
        "message": message,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_epoch": now,
    })
    if prompt is not None:
        data["prompt"] = prompt
    if source is not None:
        data["source"] = source

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_status(cfg: Config) -> dict:
    path = cfg.path("paths", "status_file")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


# ------------------------------------------------------------- heartbeats
# Long-running components call beat() periodically; the display server
# reads the ages to render the health row. A missing/old beat = trouble.

def beat(cfg: Config, component: str) -> None:
    path = cfg.path("paths", "heartbeats_dir") / component
    try:
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass  # a failed heartbeat must never crash the component


def beat_ages(cfg: Config) -> dict[str, float]:
    """Seconds since each component last beat (component -> age)."""
    ages: dict[str, float] = {}
    hb_dir = cfg.path("paths", "heartbeats_dir")
    now = time.time()
    for f in hb_dir.iterdir():
        try:
            ages[f.name] = max(0.0, now - float(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return ages
