"""Synthetic Media Generator for ReturnLens development and testing.

As required by Brief B and 17 §8:
- Generates clearly named synthetic fixtures (e.g. synthetic_*.webm, synthetic_*.wav, synthetic_*.png).
- Records all assets in app/demo/media/manifest.json with synthetic: true.
- Never to be presented as real customer evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import wave
import zlib
from pathlib import Path


def _vint(val: int) -> bytes:
    """Encode an integer as an EBML variable-length integer (VINT)."""
    if val < 0x7F:
        return bytes([val | 0x80])
    elif val < 0x3FFF:
        return bytes([(val >> 8) | 0x40, val & 0xFF])
    elif val < 0x1FFFFF:
        return bytes([(val >> 16) | 0x20, (val >> 8) & 0xFF, val & 0xFF])
    elif val < 0x0FFFFFFF:
        return bytes([(val >> 24) | 0x10, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])
    raise ValueError(f"Value too large for VINT: {val}")


def _ebml_elem(eid: bytes, data: bytes) -> bytes:
    return eid + _vint(len(data)) + data


def _ebml_uint(eid: bytes, val: int) -> bytes:
    if val < 256:
        d = bytes([val])
    elif val < 65536:
        d = val.to_bytes(2, "big")
    elif val < 16777216:
        d = val.to_bytes(3, "big")
    else:
        d = val.to_bytes(4, "big")
    return _ebml_elem(eid, d)


def _ebml_str(eid: bytes, s: str) -> bytes:
    return _ebml_elem(eid, s.encode("ascii"))


def create_synthetic_webm(
    output_path: Path,
    duration_sec: float = 10.0,
    width: int = 64,
    height: int = 64,
    color_name: str = "black",
) -> None:
    """Generates a minimal valid WebM file with a solid color VP8 stream."""
    # EBML Header
    hdr = (
        _ebml_uint(b"\x42\x86", 1)  # EBMLVersion
        + _ebml_uint(b"\x42\xf7", 1)  # EBMLReadVersion
        + _ebml_uint(b"\x42\xf2", 4)  # EBMLMaxIDLength
        + _ebml_uint(b"\x42\xf3", 8)  # EBMLMaxSizeLength
        + _ebml_str(b"\x42\x82", "webm")  # DocType
        + _ebml_uint(b"\x42\x87", 2)  # DocTypeVersion
        + _ebml_uint(b"\x42\x85", 2)  # DocTypeReadVersion
    )
    ebml_header = _ebml_elem(b"\x1a\x45\xdf\xa3", hdr)

    # Segment Info
    duration_ms = float(duration_sec * 1000.0)
    info = (
        _ebml_uint(b"\x2a\xd7\xb1", 1000000)  # TimecodeScale (1ms)
        + _ebml_str(b"\x4d\x80", "ReturnLens Synthetic Muxer")
        + _ebml_str(b"\x57\x41", "ReturnLens Synthetic")
        + _ebml_elem(b"\x44\x89", struct.pack(">f", duration_ms))  # Duration float
    )
    info_elem = _ebml_elem(b"\x15\x49\xa9\x66", info)

    # Video Settings
    video_settings = (
        _ebml_uint(b"\xb0", width)  # PixelWidth
        + _ebml_uint(b"\xba", height)  # PixelHeight
    )
    # Track Entry
    track_entry = (
        _ebml_uint(b"\xd7", 1)  # TrackNumber
        + _ebml_uint(b"\x73\xc5", 1)  # TrackUID
        + _ebml_uint(b"\x83", 1)  # TrackType (1 = video)
        + _ebml_str(b"\x86", "V_VP8")  # CodecID
        + _ebml_elem(b"\xe0", video_settings)
    )
    tracks_elem = _ebml_elem(b"\x16\x54\xae\x6b", _ebml_elem(b"\xae", track_entry))

    # A minimal valid 16x16 VP8 keyframe (black or solid color)
    # RFC 6386 keyframe payload
    vp8_keyframe = bytes([
        0x10, 0x02, 0x00, 0x9D, 0x01, 0x2A, 0x10, 0x00, 0x10, 0x00,
        0x00, 0x47, 0x08, 0x85, 0x85, 0x88, 0x85, 0x84, 0x88, 0x02,
        0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])

    # SimpleBlock: Track 1, timecode 0ms, keyframe flag 0x80
    simple_block_0 = bytes([0x81, 0x00, 0x00, 0x80]) + vp8_keyframe
    simple_block_elem_0 = _ebml_elem(b"\xa3", simple_block_0)

    # SimpleBlock at 5000ms
    simple_block_5s = bytes([0x81, 0x13, 0x88, 0x80]) + vp8_keyframe
    simple_block_elem_5s = _ebml_elem(b"\xa3", simple_block_5s)

    cluster_content = (
        _ebml_uint(b"\xe7", 0)  # Cluster Timecode (0ms)
        + simple_block_elem_0
        + simple_block_elem_5s
    )
    cluster_elem = _ebml_elem(b"\x1f\x43\xb6\x75", cluster_content)

    segment_body = info_elem + tracks_elem + cluster_elem
    segment_elem = _ebml_elem(b"\x18\x53\x80\x67", segment_body)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(ebml_header + segment_elem)


def create_synthetic_wav(
    output_path: Path,
    duration_sec: float = 3.0,
    freq: float = 440.0,
) -> None:
    """Generates a minimal valid WAV audio file with a synthetic tone."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_sec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            # 440Hz sine wave at gentle volume
            val = int(8000 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


def create_synthetic_png(
    output_path: Path,
    width: int = 128,
    height: int = 128,
    rgb: tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Generates a valid minimal PNG image."""
    r, g, b = rgb
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter type 0: None
        raw.extend(bytes([r, g, b]) * width)
    compressed = zlib.compress(bytes(raw))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png_data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(png_data)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_all_fixtures(media_dir: Path) -> dict:
    media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthetic black unboxing video (MISMATCH Case B fixture)
    black_webm = media_dir / "synthetic_black_headphones.webm"
    create_synthetic_webm(black_webm, duration_sec=10.0, color_name="black")

    # 2. Synthetic white unboxing video (Matching item fixture)
    white_webm = media_dir / "synthetic_white_headphones.webm"
    create_synthetic_webm(white_webm, duration_sec=10.0, color_name="white")

    # 3. Synthetic damaged item video (DAMAGE Case A fixture)
    damaged_webm = media_dir / "synthetic_damaged_item.webm"
    create_synthetic_webm(damaged_webm, duration_sec=10.0, color_name="grey")

    # 4. Synthetic voice note (Audio WAV fixture)
    voice_wav = media_dir / "synthetic_voice_hindi.wav"
    create_synthetic_wav(voice_wav, duration_sec=4.0, freq=440.0)

    # 5. Synthetic shipping label close-up photo (Image fixture)
    label_png = media_dir / "synthetic_label_closeup.png"
    create_synthetic_png(label_png, width=200, height=200, rgb=(240, 240, 240))

    manifest = {
        "version": "1.0",
        "notice": (
            "DEV FIXTURES ONLY. All items in this manifest are synthetically generated in code. "
            "Never to be presented as real customer evidence per Brief B and 00_COMMON_RULES.md §5."
        ),
        "fixtures": [
            {
                "filename": black_webm.name,
                "synthetic": True,
                "media_type": "video",
                "mime_type": "video/webm",
                "size_bytes": black_webm.stat().st_size,
                "content_sha256": compute_sha256(black_webm),
                "duration_ms": 10000,
                "ground_truth": {
                    "attribute": "color",
                    "observed_color": "black",
                    "damage": "none",
                    "label_readable": False,
                    "barcode_readable": False,
                },
                "limitations": [
                    "Synthetic solid-color frame generated in code",
                    "Barcode and serial text intentionally not visible",
                    "Development/harness fallback only",
                ],
                "source_timestamps": {
                    "00:01": "Black headphones visible in frame",
                    "00:07": "Side profile of black casing visible",
                },
            },
            {
                "filename": white_webm.name,
                "synthetic": True,
                "media_type": "video",
                "mime_type": "video/webm",
                "size_bytes": white_webm.stat().st_size,
                "content_sha256": compute_sha256(white_webm),
                "duration_ms": 10000,
                "ground_truth": {
                    "attribute": "color",
                    "observed_color": "white",
                    "damage": "none",
                    "label_readable": False,
                    "barcode_readable": False,
                },
                "limitations": [
                    "Synthetic solid-color frame generated in code",
                    "Development fixture only",
                ],
                "source_timestamps": {
                    "00:02": "White headphones visible in frame",
                },
            },
            {
                "filename": damaged_webm.name,
                "synthetic": True,
                "media_type": "video",
                "mime_type": "video/webm",
                "size_bytes": damaged_webm.stat().st_size,
                "content_sha256": compute_sha256(damaged_webm),
                "duration_ms": 10000,
                "ground_truth": {
                    "attribute": "damage",
                    "observed_damage": "visible crack",
                    "color": "grey",
                },
                "limitations": [
                    "Synthetic test fixture",
                ],
                "source_timestamps": {
                    "00:04": "Damage crack visible on surface",
                },
            },
            {
                "filename": voice_wav.name,
                "synthetic": True,
                "media_type": "audio",
                "mime_type": "audio/wav",
                "size_bytes": voice_wav.stat().st_size,
                "content_sha256": compute_sha256(voice_wav),
                "duration_ms": 4000,
                "ground_truth": {
                    "language": "hi",
                    "transcript_intent": "RETURN",
                    "mentioned_order_id": "ORD-7729",
                },
                "limitations": [
                    "Synthetic tone fixture for audio pipeline integrity verification",
                ],
            },
            {
                "filename": label_png.name,
                "synthetic": True,
                "media_type": "image",
                "mime_type": "image/png",
                "size_bytes": label_png.stat().st_size,
                "content_sha256": compute_sha256(label_png),
                "ground_truth": {
                    "attribute": "label_text",
                    "order_id": "ORD-7729",
                    "sku": "HEAD-WHT-02",
                },
                "limitations": [
                    "Synthetic close-up label image fixture",
                ],
            },
        ],
    }

    manifest_path = media_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    target_dir = Path(__file__).resolve().parent / "media"
    print(f"Generating synthetic fixtures in {target_dir}...")
    m = generate_all_fixtures(target_dir)
    print(f"Generated {len(m['fixtures'])} synthetic fixtures with manifest.json.")
