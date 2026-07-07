"""Continuous room listener with Voice Activity Detection.

Runs 24/7 in the background. Captures the microphone at 16 kHz mono,
runs every 30 ms frame through WebRTC VAD, and writes only *speech*
to timestamped WAV clips in the rolling audio buffer. Silence is never
stored. The buffer is pruned by size so it can run forever.

Run it:
    python -m artframe.audio_listener
    python -m artframe.audio_listener --list-devices
"""

from __future__ import annotations

import argparse
import collections
import queue
import sys
import time
import wave
from pathlib import Path

import sounddevice as sd
import webrtcvad  # provided by the `webrtcvad-wheels` package

from artframe.config import load_config
from artframe.log_setup import get_logger


def list_devices() -> None:
    print(sd.query_devices())


def find_input_device(name_fragment: str) -> int | None:
    """Return the index of the first input device whose name contains
    `name_fragment` (case-insensitive), or None for the system default."""
    if not name_fragment:
        return None
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and name_fragment.lower() in dev["name"].lower():
            return idx
    raise RuntimeError(
        f"No input device matching {name_fragment!r}. "
        "Run with --list-devices to see what's available."
    )


class ClipWriter:
    """Writes speech frames into timestamped WAV clips."""

    def __init__(self, audio_dir: Path, sample_rate: int, max_clip_seconds: float,
                 min_clip_seconds: float, logger) -> None:
        self.audio_dir = audio_dir
        self.sample_rate = sample_rate
        self.max_frames_bytes = int(max_clip_seconds * sample_rate) * 2  # 16-bit mono
        self.min_frames_bytes = int(min_clip_seconds * sample_rate) * 2
        self.log = logger
        self._buf = bytearray()

    def add(self, frame: bytes) -> None:
        self._buf.extend(frame)
        if len(self._buf) >= self.max_frames_bytes:
            self.flush()

    def flush(self) -> None:
        if not self._buf:
            return
        if len(self._buf) < self.min_frames_bytes:
            self._buf.clear()  # too short to be real speech — discard
            return
        name = time.strftime("clip_%Y%m%d_%H%M%S.wav")
        path = self.audio_dir / name
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(bytes(self._buf))
        self.log.info("saved %s (%.1fs)", name, len(self._buf) / 2 / self.sample_rate)
        self._buf.clear()


def prune_buffer(audio_dir: Path, max_mb: int, logger) -> None:
    """Delete oldest clips once the buffer exceeds its size cap."""
    clips = sorted(audio_dir.glob("clip_*.wav"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in clips)
    while clips and total > max_mb * 1_000_000:
        oldest = clips.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink(missing_ok=True)
        logger.info("pruned old clip %s", oldest.name)


def run_listener() -> None:
    cfg = load_config()
    log = get_logger("listener", cfg)
    a = cfg["audio"]

    sample_rate = a["sample_rate"]
    frame_ms = a["frame_ms"]
    frame_bytes = int(sample_rate * frame_ms / 1000) * 2  # 16-bit mono
    padding_frames = max(1, a["padding_ms"] // frame_ms)

    vad = webrtcvad.Vad(a["vad_aggressiveness"])
    audio_dir = cfg.path("paths", "audio_dir")
    writer = ClipWriter(audio_dir, sample_rate, a["max_clip_seconds"],
                        a["min_clip_seconds"], log)
    device = find_input_device(a["device_name"])

    frames: queue.Queue[bytes] = queue.Queue()

    def callback(indata, nframes, time_info, status):  # noqa: ARG001
        if status:
            log.warning("audio status: %s", status)
        frames.put(bytes(indata))

    # Ring buffer holds recent frames so a clip starts slightly BEFORE
    # the first voiced frame (no clipped first syllables).
    ring: collections.deque[tuple[bytes, bool]] = collections.deque(maxlen=padding_frames)
    triggered = False
    last_prune = time.monotonic()

    log.info("listening: device=%s rate=%d vad=%d",
             a["device_name"] or "default", sample_rate, a["vad_aggressiveness"])

    with sd.RawInputStream(samplerate=sample_rate, blocksize=frame_bytes // 2,
                           device=device, dtype="int16", channels=1,
                           callback=callback):
        while True:
            frame = frames.get()
            if len(frame) != frame_bytes:
                continue
            try:
                is_speech = vad.is_speech(frame, sample_rate)
            except Exception:
                continue

            if not triggered:
                ring.append((frame, is_speech))
                voiced = sum(1 for _, s in ring if s)
                # open a clip once the ring is mostly speech
                if voiced > 0.9 * ring.maxlen:
                    triggered = True
                    for f, _ in ring:
                        writer.add(f)
                    ring.clear()
            else:
                writer.add(frame)
                ring.append((frame, is_speech))
                unvoiced = sum(1 for _, s in ring if not s)
                # close the clip once the ring is mostly silence
                if unvoiced > 0.9 * ring.maxlen:
                    triggered = False
                    writer.flush()
                    ring.clear()

            if time.monotonic() - last_prune > 300:  # every 5 min
                prune_buffer(audio_dir, a["max_buffer_mb"], log)
                last_prune = time.monotonic()


def main() -> None:
    parser = argparse.ArgumentParser(description="ArtFrame room listener")
    parser.add_argument("--list-devices", action="store_true",
                        help="print audio devices and exit")
    args = parser.parse_args()
    if args.list_devices:
        list_devices()
        return
    while True:  # auto-restart on device hiccups (USB re-enumeration etc.)
        try:
            run_listener()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as exc:  # noqa: BLE001
            print(f"listener crashed: {exc!r} — restarting in 10s", file=sys.stderr)
            time.sleep(10)


if __name__ == "__main__":
    main()
