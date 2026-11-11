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
import subprocess
import wave
import zlib
from pathlib import Path


# ---------------------------------------------------------------------------
# EBML / WebM video generation (pure Python)
# ---------------------------------------------------------------------------

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
    hdr = (
        _ebml_uint(b"\x42\x86", 1)
        + _ebml_uint(b"\x42\xf7", 1)
        + _ebml_uint(b"\x42\xf2", 4)
        + _ebml_uint(b"\x42\xf3", 8)
        + _ebml_str(b"\x42\x82", "webm")
        + _ebml_uint(b"\x42\x87", 2)
        + _ebml_uint(b"\x42\x85", 2)
    )
    ebml_header = _ebml_elem(b"\x1a\x45\xdf\xa3", hdr)

    duration_ms = float(duration_sec * 1000.0)
    info = (
        _ebml_uint(b"\x2a\xd7\xb1", 1000000)
        + _ebml_str(b"\x4d\x80", "ReturnLens Synthetic Muxer")
        + _ebml_str(b"\x57\x41", "ReturnLens Synthetic")
        + _ebml_elem(b"\x44\x89", struct.pack(">f", duration_ms))
    )
    info_elem = _ebml_elem(b"\x15\x49\xa9\x66", info)

    video_settings = (
        _ebml_uint(b"\xb0", width)
        + _ebml_uint(b"\xba", height)
    )
    track_entry = (
        _ebml_uint(b"\xd7", 1)
        + _ebml_uint(b"\x73\xc5", 1)
        + _ebml_uint(b"\x83", 1)
        + _ebml_str(b"\x86", "V_VP8")
        + _ebml_elem(b"\xe0", video_settings)
    )
    tracks_elem = _ebml_elem(b"\x16\x54\xae\x6b", _ebml_elem(b"\xae", track_entry))

    vp8_keyframe = bytes([
        0x10, 0x02, 0x00, 0x9D, 0x01, 0x2A, 0x10, 0x00, 0x10, 0x00,
        0x00, 0x47, 0x08, 0x85, 0x85, 0x88, 0x85, 0x84, 0x88, 0x02,
        0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])

    simple_block_0 = bytes([0x81, 0x00, 0x00, 0x80]) + vp8_keyframe
    simple_block_elem_0 = _ebml_elem(b"\xa3", simple_block_0)

    simple_block_5s = bytes([0x81, 0x13, 0x88, 0x80]) + vp8_keyframe
    simple_block_elem_5s = _ebml_elem(b"\xa3", simple_block_5s)

    cluster_content = (
        _ebml_uint(b"\xe7", 0)
        + simple_block_elem_0
        + simple_block_elem_5s
    )
    cluster_elem = _ebml_elem(b"\x1f\x43\xb6\x75", cluster_content)

    segment_body = info_elem + tracks_elem + cluster_elem
    segment_elem = _ebml_elem(b"\x18\x53\x80\x67", segment_body)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(ebml_header + segment_elem)


# ---------------------------------------------------------------------------
# Audio Generation (Windows Speech Synthesizer + pure Python Tone fallback)
# ---------------------------------------------------------------------------

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
            val = int(8000 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


def create_tts_audio_wav(
    output_path: Path,
    spoken_text: str,
    fallback_freq: float = 440.0,
) -> None:
    """Generates spoken audio using Windows System.Speech with fallback to pure WAV tone."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path = str(output_path.resolve()).replace("\\", "\\\\")
    clean_text = spoken_text.replace('"', '\\"')

    ps_script = (
        f"Add-Type -AssemblyName System.Speech\n"
        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        f"$synth.SetOutputToWaveFile('{abs_path}')\n"
        f"$synth.Speak(\"{clean_text}\")\n"
        f"$synth.Dispose()\n"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
            return
    except Exception:
        pass

    # Fallback to tone if PowerShell / System.Speech is unavailable
    create_synthetic_wav(output_path, duration_sec=4.0, freq=fallback_freq)


# ---------------------------------------------------------------------------
# Pure Python 2D Pixel Canvas & 5x7 Font Renderer for PNG Images
# ---------------------------------------------------------------------------

FONT_5X7 = {
    '0': ["11111", "10001", "10001", "10001", "10001", "10001", "11111"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["11111", "00001", "00001", "11111", "10000", "10000", "11111"],
    '3': ["11111", "00001", "00001", "11111", "00001", "00001", "11111"],
    '4': ["10001", "10001", "10001", "11111", "00001", "00001", "00001"],
    '5': ["11111", "10000", "10000", "11111", "00001", "00001", "11111"],
    '6': ["11111", "10000", "10000", "11111", "10001", "10001", "11111"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["11111", "10001", "10001", "11111", "10001", "10001", "11111"],
    '9': ["11111", "10001", "10001", "11111", "00001", "00001", "11111"],
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ':': ["00000", "00100", "00000", "00000", "00100", "00000", "00000"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


class PixelCanvas:
    """A minimal 24-bit RGB pixel canvas for drawing shapes, text, and barcodes."""

    def __init__(self, width: int, height: int, bg_rgb: tuple[int, int, int]):
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height * 3)
        for i in range(width * height):
            self.pixels[i * 3] = bg_rgb[0]
            self.pixels[i * 3 + 1] = bg_rgb[1]
            self.pixels[i * 3 + 2] = bg_rgb[2]

    def set_pixel(self, x: int, y: int, rgb: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.pixels[idx] = rgb[0]
            self.pixels[idx + 1] = rgb[1]
            self.pixels[idx + 2] = rgb[2]

    def fill_rect(self, x0: int, y0: int, w: int, h: int, rgb: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(self.height, y0 + h)):
            for x in range(max(0, x0), min(self.width, x0 + w)):
                self.set_pixel(x, y, rgb)

    def draw_thick_arc(
        self,
        cx: int,
        cy: int,
        r_inner: int,
        r_outer: int,
        rgb: tuple[int, int, int],
        upper_half_only: bool = True,
    ) -> None:
        r_in2 = r_inner * r_inner
        r_out2 = r_outer * r_outer
        y_max = cy if upper_half_only else cy + r_outer
        for y in range(max(0, cy - r_outer), min(self.height, y_max + 1)):
            for x in range(max(0, cx - r_outer), min(self.width, cx + r_outer + 1)):
                dist2 = (x - cx) ** 2 + (y - cy) ** 2
                if r_in2 <= dist2 <= r_out2:
                    self.set_pixel(x, y, rgb)

    def fill_rounded_rect(
        self,
        x0: int,
        y0: int,
        w: int,
        h: int,
        radius: int,
        rgb: tuple[int, int, int],
    ) -> None:
        self.fill_rect(x0 + radius, y0, w - 2 * radius, h, rgb)
        self.fill_rect(x0, y0 + radius, radius, h - 2 * radius, rgb)
        self.fill_rect(x0 + w - radius, y0 + radius, radius, h - 2 * radius, rgb)
        # 4 corners
        corners = [
            (x0 + radius, y0 + radius),
            (x0 + w - radius, y0 + radius),
            (x0 + radius, y0 + h - radius),
            (x0 + w - radius, y0 + h - radius),
        ]
        r2 = radius * radius
        for cx, cy in corners:
            for y in range(cy - radius, cy + radius + 1):
                for x in range(cx - radius, cx + radius + 1):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                        self.set_pixel(x, y, rgb)

    def draw_text(
        self,
        text: str,
        start_x: int,
        start_y: int,
        rgb: tuple[int, int, int],
        scale: int = 2,
    ) -> None:
        cur_x = start_x
        for ch in text.upper():
            bitmap = FONT_5X7.get(ch, FONT_5X7[' '])
            for row_idx, row_str in enumerate(bitmap):
                for col_idx, bit in enumerate(row_str):
                    if bit == '1':
                        self.fill_rect(
                            cur_x + col_idx * scale,
                            start_y + row_idx * scale,
                            scale,
                            scale,
                            rgb,
                        )
            cur_x += (len(bitmap[0]) + 1) * scale

    def to_png_bytes(self) -> bytes:
        raw = bytearray()
        row_bytes = self.width * 3
        for y in range(self.height):
            raw.append(0)  # filter type 0: None
            row_start = y * row_bytes
            raw.extend(self.pixels[row_start : row_start + row_bytes])
        compressed = zlib.compress(bytes(raw))

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", compressed)
            + chunk(b"IEND", b"")
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.to_png_bytes())


# ---------------------------------------------------------------------------
# Individual PNG Fixture Renderers
# ---------------------------------------------------------------------------

def create_drawn_white_headphones_png(output_path: Path) -> None:
    """Renders high-contrast white over-ear headphones on dark background."""
    canvas = PixelCanvas(400, 300, bg_rgb=(35, 38, 42))

    # White Headband Arc
    canvas.draw_thick_arc(cx=200, cy=160, r_inner=72, r_outer=94, rgb=(250, 250, 250))

    # Earcups
    canvas.fill_rounded_rect(x0=92, y0=140, w=34, h=76, radius=12, rgb=(250, 250, 250))
    canvas.fill_rounded_rect(x0=98, y0=148, w=22, h=60, radius=8, rgb=(200, 205, 210))

    canvas.fill_rounded_rect(x0=274, y0=140, w=34, h=76, radius=12, rgb=(250, 250, 250))
    canvas.fill_rounded_rect(x0=280, y0=148, w=22, h=60, radius=8, rgb=(200, 205, 210))

    # Label Text
    canvas.draw_text("WHITE HEADPHONES", start_x=90, start_y=255, rgb=(250, 250, 250), scale=2)
    canvas.save(output_path)


def create_drawn_black_headphones_png(output_path: Path) -> None:
    """Renders high-contrast black over-ear headphones on light background."""
    canvas = PixelCanvas(400, 300, bg_rgb=(228, 232, 238))

    # Black Headband Arc
    canvas.draw_thick_arc(cx=200, cy=160, r_inner=72, r_outer=94, rgb=(20, 20, 22))

    # Earcups
    canvas.fill_rounded_rect(x0=92, y0=140, w=34, h=76, radius=12, rgb=(20, 20, 22))
    canvas.fill_rounded_rect(x0=98, y0=148, w=22, h=60, radius=8, rgb=(60, 64, 70))

    canvas.fill_rounded_rect(x0=274, y0=140, w=34, h=76, radius=12, rgb=(20, 20, 22))
    canvas.fill_rounded_rect(x0=280, y0=148, w=22, h=60, radius=8, rgb=(60, 64, 70))

    # Label Text
    canvas.draw_text("BLACK HEADPHONES", start_x=90, start_y=255, rgb=(20, 20, 22), scale=2)
    canvas.save(output_path)


def create_drawn_damaged_headphones_png(output_path: Path) -> None:
    """Renders white headphones with a visible cracked/broken headband on dark background."""
    canvas = PixelCanvas(400, 300, bg_rgb=(35, 38, 42))

    # White Headband Arc
    canvas.draw_thick_arc(cx=200, cy=160, r_inner=72, r_outer=94, rgb=(250, 250, 250))

    # Earcups
    canvas.fill_rounded_rect(x0=92, y0=140, w=34, h=76, radius=12, rgb=(250, 250, 250))
    canvas.fill_rounded_rect(x0=98, y0=148, w=22, h=60, radius=8, rgb=(200, 205, 210))

    canvas.fill_rounded_rect(x0=274, y0=140, w=34, h=76, radius=12, rgb=(250, 250, 250))
    canvas.fill_rounded_rect(x0=280, y0=148, w=22, h=60, radius=8, rgb=(200, 205, 210))

    # Severed Crack / Break Gap at Apex (x: 190 to 215, y: 64 to 90)
    canvas.fill_rect(x0=194, y0=64, w=14, h=28, rgb=(35, 38, 42))

    # Jagged Red Fractures
    crack_points = [
        (192, 66), (196, 72), (193, 78), (200, 84), (195, 88),
        (208, 66), (204, 73), (209, 80), (205, 87),
    ]
    for px, py in crack_points:
        canvas.fill_rect(px, py, 3, 3, rgb=(240, 50, 50))

    # Label Text
    canvas.draw_text("CRACKED HEADBAND", start_x=85, start_y=255, rgb=(240, 60, 60), scale=2)
    canvas.save(output_path)


def create_drawn_shipping_label_png(output_path: Path) -> None:
    """Renders crisp outer box shipping label with barcode stripes and readable text."""
    canvas = PixelCanvas(400, 300, bg_rgb=(245, 245, 248))

    # Label Border
    canvas.fill_rect(20, 20, 360, 260, rgb=(255, 255, 255))
    for x in range(20, 380):
        canvas.set_pixel(x, 20, (30, 30, 30))
        canvas.set_pixel(x, 279, (30, 30, 30))
    for y in range(20, 280):
        canvas.set_pixel(20, y, (30, 30, 30))
        canvas.set_pixel(379, y, (30, 30, 30))

    # Title header
    canvas.draw_text("RETURNLENS DISPATCH", start_x=45, start_y=35, rgb=(40, 40, 40), scale=2)

    # Separator line
    canvas.fill_rect(35, 60, 330, 2, rgb=(180, 180, 180))

    # Barcode Stripes
    stripe_pattern = [
        3, 2, 4, 1, 2, 3, 1, 4, 2, 2, 1, 3, 4, 1, 2, 3, 2, 1, 4, 2,
        3, 1, 2, 4, 1, 3, 2, 2, 4, 1, 3, 2, 1, 4, 2, 3, 1, 2, 3, 4,
    ]
    cur_x = 45
    for idx, width in enumerate(stripe_pattern):
        color = (15, 15, 15) if idx % 2 == 0 else (255, 255, 255)
        canvas.fill_rect(cur_x, 75, width * 2, 70, color)
        cur_x += width * 2
        if cur_x >= 350:
            break

    # Order ID & SKU Text (Crystal clear 5x7 font)
    canvas.draw_text("ORD-7729", start_x=90, start_y=165, rgb=(10, 10, 10), scale=4)
    canvas.draw_text("SKU: HEAD-WHT-02", start_x=65, start_y=220, rgb=(20, 20, 20), scale=2)
    canvas.draw_text("COLOR: WHITE", start_x=65, start_y=245, rgb=(60, 60, 60), scale=2)

    canvas.save(output_path)


# ---------------------------------------------------------------------------
# SHA-256 and Manifest Generation
# ---------------------------------------------------------------------------

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_all_fixtures(media_dir: Path) -> dict:
    media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Video fixtures (WebM)
    black_webm = media_dir / "synthetic_black_headphones.webm"
    create_synthetic_webm(black_webm, duration_sec=10.0, color_name="black")

    white_webm = media_dir / "synthetic_white_headphones.webm"
    create_synthetic_webm(white_webm, duration_sec=10.0, color_name="white")

    damaged_webm = media_dir / "synthetic_damaged_item.webm"
    create_synthetic_webm(damaged_webm, duration_sec=10.0, color_name="grey")

    # 2. Image fixtures (PNG)
    black_png = media_dir / "synthetic_black_headphones.png"
    create_drawn_black_headphones_png(black_png)

    white_png = media_dir / "synthetic_white_headphones.png"
    create_drawn_white_headphones_png(white_png)

    damaged_png = media_dir / "synthetic_damaged_item.png"
    create_drawn_damaged_headphones_png(damaged_png)

    label_png = media_dir / "synthetic_label_closeup.png"
    create_drawn_shipping_label_png(label_png)

    # 3. Audio voice note fixtures (WAV)
    voice_hindi_wav = media_dir / "synthetic_voice_hindi.wav"
    create_tts_audio_wav(
        voice_hindi_wav,
        spoken_text="I want to return order 1042. The headphones are cracked and damaged.",
        fallback_freq=440.0,
    )

    voice_english_wav = media_dir / "synthetic_voice_english.wav"
    create_tts_audio_wav(
        voice_english_wav,
        spoken_text="I ordered white headphones for order 7729 but received black ones.",
        fallback_freq=520.0,
    )

    manifest = {
        "version": "1.1",
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
                },
                "limitations": [
                    "Synthetic solid-color frame generated in code",
                    "Development/harness fallback only",
                ],
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
                },
                "limitations": [
                    "Synthetic solid-color frame generated in code",
                    "Development fixture only",
                ],
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
            },
            {
                "filename": black_png.name,
                "synthetic": True,
                "media_type": "image",
                "mime_type": "image/png",
                "size_bytes": black_png.stat().st_size,
                "content_sha256": compute_sha256(black_png),
                "ground_truth": {
                    "attribute": "color",
                    "observed_color": "black",
                    "damage": "none",
                },
                "limitations": [
                    "High-contrast drawn black headphones shape for vision models",
                ],
            },
            {
                "filename": white_png.name,
                "synthetic": True,
                "media_type": "image",
                "mime_type": "image/png",
                "size_bytes": white_png.stat().st_size,
                "content_sha256": compute_sha256(white_png),
                "ground_truth": {
                    "attribute": "color",
                    "observed_color": "white",
                    "damage": "none",
                },
                "limitations": [
                    "High-contrast drawn white headphones shape for vision models",
                ],
            },
            {
                "filename": damaged_png.name,
                "synthetic": True,
                "media_type": "image",
                "mime_type": "image/png",
                "size_bytes": damaged_png.stat().st_size,
                "content_sha256": compute_sha256(damaged_png),
                "ground_truth": {
                    "attribute": "damage",
                    "observed_damage": "cracked headband",
                    "color": "white",
                },
                "limitations": [
                    "High-contrast drawn headphones with severed red crack fracture",
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
                    "barcode_readable": True,
                },
                "limitations": [
                    "Synthetic crisp shipping label with barcode stripes and text",
                ],
            },
            {
                "filename": voice_hindi_wav.name,
                "synthetic": True,
                "media_type": "audio",
                "mime_type": "audio/wav",
                "size_bytes": voice_hindi_wav.stat().st_size,
                "content_sha256": compute_sha256(voice_hindi_wav),
                "duration_ms": 4000,
                "ground_truth": {
                    "transcript_intent": "RETURN",
                    "mentioned_order_id": "ORD-1042",
                    "issue": "cracked and damaged",
                },
                "limitations": [
                    "Customer voice note synthesized via Windows System.Speech",
                ],
            },
            {
                "filename": voice_english_wav.name,
                "synthetic": True,
                "media_type": "audio",
                "mime_type": "audio/wav",
                "size_bytes": voice_english_wav.stat().st_size,
                "content_sha256": compute_sha256(voice_english_wav),
                "duration_ms": 4000,
                "ground_truth": {
                    "transcript_intent": "RETURN",
                    "mentioned_order_id": "ORD-7729",
                    "issue": "ordered white but received black",
                },
                "limitations": [
                    "Customer voice note synthesized via Windows System.Speech",
                ],
            },
        ],
    }

    stock_manifest_path = media_dir / "stock" / "manifest.json"
    if stock_manifest_path.exists():
        with open(stock_manifest_path, "r", encoding="utf-8") as sf:
            stock_data = json.load(sf)
        manifest["stock_note"] = stock_data.get("note")
        manifest["missing"] = stock_data.get("missing", [])
        stock_assets = []
        for asset in stock_data.get("assets", []):
            item = dict(asset)
            f_name = asset.get("file", "")
            item["filename"] = f"stock/{f_name}"
            item["file"] = f_name
            target_path = media_dir / "stock" / f_name
            if target_path.exists():
                item["size_bytes"] = target_path.stat().st_size
                item["content_sha256"] = compute_sha256(target_path)
            if "duration_s" in asset:
                item["duration_ms"] = int(asset["duration_s"] * 1000)
            item["media_type"] = asset.get("kind", "video")
            stock_assets.append(item)
            manifest["fixtures"].append(item)
        manifest["assets"] = stock_assets

    manifest_path = media_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    target_dir = Path(__file__).resolve().parent / "media"
    print(f"Generating synthetic fixtures in {target_dir}...")
    m = generate_all_fixtures(target_dir)
    print(f"Generated {len(m['fixtures'])} synthetic fixtures with manifest.json.")
