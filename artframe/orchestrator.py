"""The conductor: audio window -> transcript -> prompt -> painting -> display.

One "cycle" is:
    1. transcribe all VAD clips from the last window (then shred the audio)
    2. build a prompt (transcript-driven, or smart fallback)
    3. generate the image via ComfyUI
    4. drop it into the images folder (the display picks it up automatically)
    5. record the prompt in history, prune the gallery

Run modes:
    python -m artframe.orchestrator --once      # single cycle, then exit
    python -m artframe.orchestrator --once --force-fallback
    python -m artframe.orchestrator --loop      # run forever on the schedule
                                                # (also watches the trigger flag)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from statistics import median

from artframe.config import Config, load_config
from artframe.gallery import load_favorites, prune_thumbs
from artframe.generator import GenerationError, check_server, generate
from artframe.log_setup import get_logger
from artframe.prompt_builder import append_history, build_prompt, load_history
from artframe.status import beat, set_status
from artframe.transcriber import transcribe_window

LOCK_NAME = "cycle.lock"
DEFAULT_EXPECTED_SECONDS = 25 * 60  # until real durations exist in history


def expected_duration(cfg: Config) -> int:
    """Rolling estimate of painting time: the median of the last few real
    durations. Drives the display's progress bar."""
    durations = [e["duration_seconds"] for e in load_history(cfg)
                 if e.get("duration_seconds")][-7:]
    return int(median(durations)) if durations else DEFAULT_EXPECTED_SECONDS


class CycleLock:
    """Prevents overlapping cycles (e.g. manual trigger during a scheduled run).
    A lock older than the generation timeout is considered stale and stolen."""

    def __init__(self, cfg: Config) -> None:
        self.path = cfg.path("paths", "data_dir") / LOCK_NAME
        self.max_age = cfg["comfyui"]["timeout_minutes"] * 60 + 1800

    def acquire(self) -> bool:
        if self.path.exists():
            if time.time() - self.path.stat().st_mtime < self.max_age:
                return False
            self.path.unlink(missing_ok=True)  # stale lock from a crash
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


def prune_gallery(cfg: Config, log) -> None:
    images_dir = cfg.path("paths", "images_dir")
    keep = cfg["display"]["gallery_keep"]
    favorites = load_favorites(cfg)
    # favorites are exempt AND don't use up the keep budget
    files = sorted((p for p in images_dir.glob("art_*.png")
                    if p.name not in favorites),
                   key=lambda p: p.stat().st_mtime)
    for old in files[:-keep] if keep else []:
        old.unlink(missing_ok=True)
        log.info("pruned old artwork %s", old.name)
    prune_thumbs(cfg)


def run_cycle(cfg: Config, force_fallback: bool = False) -> bool:
    """Run one full cycle. Returns True on success."""
    log = get_logger("orchestrator", cfg)
    lock = CycleLock(cfg)
    if not lock.acquire():
        log.warning("another cycle is already running — skipping")
        return False
    try:
        log.info("=== cycle start ===")

        if not check_server(cfg):
            log.error("ComfyUI is not reachable at %s — is it running?",
                      cfg["comfyui"]["base_url"])
            set_status(cfg, "error", "ComfyUI is not running")
            return False

        set_status(cfg, "transcribing", "Listening back over the last few hours...")
        transcript = "" if force_fallback else transcribe_window(cfg)

        set_status(cfg, "prompting", "Dreaming up a new scene...")
        positive, source, scene = build_prompt(cfg, transcript)
        negative = cfg["prompting"]["negative_prompt"]

        out = cfg.path("paths", "images_dir") / time.strftime(
            "art_%Y%m%d_%H%M%S.png")
        set_status(cfg, "generating", "Painting the new artwork...",
                   prompt=positive, source=source,
                   expected_seconds=expected_duration(cfg))
        started = time.monotonic()
        try:
            generate(cfg, positive, negative, out)
        except GenerationError as exc:
            log.error("generation failed: %s", exc)
            set_status(cfg, "error", f"Generation failed: {exc}",
                       prompt=positive, source=source)
            return False
        duration = int(time.monotonic() - started)

        # Only successful generations enter history — that keeps the
        # remix fallback pool high quality. The image link feeds the gallery,
        # the duration feeds the progress-bar estimate.
        append_history(cfg, positive, source, scene=scene, image=out.name,
                       duration_seconds=duration)
        prune_gallery(cfg, log)
        log.info("=== cycle complete: %s (source=%s) ===", out.name, source)
        set_status(cfg, "idle", "Waiting for the next painting",
                   prompt=positive, source=source)
        return True
    except Exception as exc:  # noqa: BLE001
        log.exception("cycle crashed: %r", exc)
        set_status(cfg, "error", f"Cycle crashed: {exc!r}")
        return False
    finally:
        lock.release()


def run_loop(cfg: Config) -> None:
    """Run forever: continuous painting with a short breather between
    cycles (gap_minutes counts from one painting FINISHING to the next
    STARTING), plus instant manual triggers."""
    log = get_logger("orchestrator", cfg)
    gap = cfg["schedule"]["gap_minutes"] * 60
    poll = cfg["schedule"]["trigger_poll_seconds"]
    flag = cfg.path("paths", "trigger_flag")

    log.info("loop mode: %s min between paintings, trigger flag %s",
             cfg["schedule"]["gap_minutes"], flag)
    set_status(cfg, "idle", "Warming up — first painting shortly")
    next_run = time.time() + 120  # first artwork ~2 min after boot
    while True:
        beat(cfg, "orchestrator")
        triggered = flag.exists()
        if triggered or time.time() >= next_run:
            if triggered:
                flag.unlink(missing_ok=True)
                log.info("manual trigger detected")
            ok = run_cycle(cfg)
            next_run = time.time() + gap
            if ok:  # on failure keep the error status visible instead
                set_status(cfg, "idle", "Next painting at "
                           + time.strftime("%H:%M", time.localtime(next_run)))
        time.sleep(poll)


def main() -> None:
    parser = argparse.ArgumentParser(description="ArtFrame orchestrator")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one cycle and exit")
    mode.add_argument("--loop", action="store_true", help="run on the schedule forever")
    parser.add_argument("--force-fallback", action="store_true",
                        help="skip transcription; exercise the fallback path")
    args = parser.parse_args()

    cfg = load_config()
    if args.once:
        sys.exit(0 if run_cycle(cfg, force_fallback=args.force_fallback) else 1)
    run_loop(cfg)


if __name__ == "__main__":
    main()
