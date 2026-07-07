"""Local transcription of buffered audio clips with faster-whisper.

The model is loaded once per cycle, all clips in the time window are
transcribed oldest-first, and (per the privacy setting) the audio files
are deleted immediately afterwards — transcribe-and-shred.

Standalone test:
    python -m artframe.transcriber            # transcribe current buffer
    python -m artframe.transcriber --keep     # ...without deleting audio
"""

from __future__ import annotations

import time
from pathlib import Path

from artframe.config import Config, load_config
from artframe.log_setup import get_logger


def clips_in_window(audio_dir: Path, window_hours: float) -> list[Path]:
    cutoff = time.time() - window_hours * 3600
    clips = [p for p in audio_dir.glob("clip_*.wav") if p.stat().st_mtime >= cutoff]
    return sorted(clips, key=lambda p: p.stat().st_mtime)


def transcribe_window(cfg: Config, delete_audio: bool | None = None) -> str:
    """Transcribe every clip in the window; return the combined transcript."""
    log = get_logger("transcriber", cfg)
    t = cfg["transcription"]
    if delete_audio is None:
        delete_audio = cfg["privacy"]["delete_audio_after_transcription"]

    audio_dir = cfg.path("paths", "audio_dir")
    clips = clips_in_window(audio_dir, cfg["schedule"]["window_hours"])
    if not clips:
        log.info("no audio clips in the last %sh", cfg["schedule"]["window_hours"])
        return ""

    # Import here so the listener/display never pay the import cost.
    from faster_whisper import WhisperModel

    log.info("loading whisper model %s (%s)...", t["model"], t["compute_type"])
    model = WhisperModel(t["model"], device="cpu",
                         compute_type=t["compute_type"],
                         cpu_threads=t["cpu_threads"])

    pieces: list[str] = []
    for clip in clips:
        try:
            segments, _info = model.transcribe(
                str(clip),
                language=t["language"],
                beam_size=1,          # greedy — fastest on CPU
                vad_filter=True,      # second-pass VAD trims residual silence
                condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            if text:
                pieces.append(text)
            log.info("transcribed %s: %d chars", clip.name, len(text))
        except Exception as exc:  # noqa: BLE001
            log.error("failed on %s: %r", clip.name, exc)
        finally:
            if delete_audio:
                clip.unlink(missing_ok=True)

    transcript = "\n".join(pieces)
    log.info("window transcript: %d clips, %d chars", len(clips), len(transcript))

    if cfg["privacy"]["keep_last_transcript"]:
        cfg.path("paths", "last_transcript").write_text(transcript, encoding="utf-8")
    return transcript


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArtFrame transcriber test")
    parser.add_argument("--keep", action="store_true", help="do not delete audio")
    args = parser.parse_args()
    result = transcribe_window(load_config(), delete_audio=not args.keep)
    print("---- TRANSCRIPT ----")
    print(result or "(empty)")
