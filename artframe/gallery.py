"""Gallery helpers shared by the orchestrator and the display server:
favorites (pinned artworks that pruning never touches), the image<->prompt
join, and cached thumbnails for the panel's gallery strip.
"""

from __future__ import annotations

import json
from pathlib import Path

from artframe.config import Config
from artframe.prompt_builder import load_history

THUMB_WIDTH = 320


# ------------------------------------------------------------- favorites

def load_favorites(cfg: Config) -> set[str]:
    path = cfg.path("paths", "favorites_file")
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return set()
    return set()


def save_favorites(cfg: Config, favorites: set[str]) -> None:
    cfg.path("paths", "favorites_file").write_text(
        json.dumps(sorted(favorites), indent=2), encoding="utf-8")


def toggle_favorite(cfg: Config, name: str) -> bool:
    """Flip an artwork's pinned state; returns the new state."""
    favorites = load_favorites(cfg)
    if name in favorites:
        favorites.discard(name)
        state = False
    else:
        favorites.add(name)
        state = True
    save_favorites(cfg, favorites)
    return state


# ------------------------------------------------------- gallery listing

def gallery_entries(cfg: Config) -> list[dict]:
    """All artworks newest-first, each joined to its prompt when known."""
    images_dir = cfg.path("paths", "images_dir")
    by_image = {e["image"]: e for e in load_history(cfg) if e.get("image")}
    favorites = load_favorites(cfg)

    entries = []
    for p in sorted(images_dir.glob("art_*.png"),
                    key=lambda f: f.stat().st_mtime, reverse=True):
        hist = by_image.get(p.name, {})
        entries.append({
            "file": p.name,
            "key": f"{p.name}:{int(p.stat().st_mtime)}",
            "prompt": hist.get("prompt"),
            "scene": hist.get("scene"),
            "source": hist.get("source"),
            "ts": hist.get("ts"),
            "favorite": p.name in favorites,
        })
    return entries


# ------------------------------------------------------------ thumbnails

def ensure_thumb(cfg: Config, name: str) -> Path | None:
    """Return a cached thumbnail for an artwork, creating it on demand.
    Regenerated if the source image is newer than the cached thumb."""
    src = cfg.path("paths", "images_dir") / name
    if not src.exists() or src.suffix.lower() != ".png":
        return None
    thumb = cfg.path("paths", "thumbs_dir") / (src.stem + ".jpg")
    if thumb.exists() and thumb.stat().st_mtime >= src.stat().st_mtime:
        return thumb

    from PIL import Image  # local import: only the display server needs PIL

    with Image.open(src) as im:
        im = im.convert("RGB")
        height = max(1, round(im.height * THUMB_WIDTH / im.width))
        im.thumbnail((THUMB_WIDTH, height))
        im.save(thumb, "JPEG", quality=80)
    return thumb


def prune_thumbs(cfg: Config) -> None:
    """Drop cached thumbs whose artwork no longer exists."""
    images_dir = cfg.path("paths", "images_dir")
    for t in cfg.path("paths", "thumbs_dir").glob("*.jpg"):
        if not (images_dir / (t.stem + ".png")).exists():
            t.unlink(missing_ok=True)
