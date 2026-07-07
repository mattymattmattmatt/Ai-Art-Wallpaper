"""Load config.yaml and resolve all paths relative to the project root.

Usage:
    from artframe.config import load_config
    cfg = load_config()
    cfg["audio"]["sample_rate"]      # plain dict access
    cfg.path("paths", "images_dir")  # resolved absolute Path, dir auto-created
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

# Keys under `paths:` that are directories (created on demand).
_DIR_KEYS = {"data_dir", "audio_dir", "images_dir", "logs_dir"}


class Config(dict):
    """A dict with a helper that resolves configured paths."""

    def path(self, *keys: str) -> Path:
        node = self
        for key in keys:
            node = node[key]
        p = Path(node)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        # Auto-create directories; for files, create the parent.
        if keys[-1] in _DIR_KEYS:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
        return p


def load_config(config_file: Path | None = None) -> Config:
    file = config_file or CONFIG_FILE
    with open(file, "r", encoding="utf-8") as fh:
        return Config(yaml.safe_load(fh))
