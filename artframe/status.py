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
               prompt: str | None = None, source: str | None = None) -> None:
    path = cfg.path("paths", "status_file")
    data = read_status(cfg)
    now = time.time()

    # Track when we ENTERED the generating stage, so the UI can show elapsed.
    if stage == "generating" and data.get("stage") != "generating":
        data["generating_since"] = now
    if stage != "generating":
        data.pop("generating_since", None)

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
