#!/usr/bin/env python3
"""Generate the Hi-EV application icon set for the Tauri desktop wrapper.

This script is a build-time helper. It creates deterministic PNG/ICO/ICNS assets
from a simple vector-like design so the installer has a real logo even when no
external asset file has been provided yet.
"""

from __future__ import annotations

import logging
import struct
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a usable TrueType font, falling back to PIL default."""
    candidates: list[Path] = [
        # Windows
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/Segoe UI/segoeui.ttf"),
        # macOS
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/SFPro.ttf"),
        # Linux
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
        except Exception:  # noqa: BLE001
            logger.debug("Could not load font %s: skipping", candidate)
            continue
    return ImageFont.load_default()


def _make_base(size: int) -> Image.Image:
    """Render the Hi-EV logo at the requested square size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 12
    bbox = [margin, margin, size - margin, size - margin]

    # Outer glow / shadow.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(bbox, fill=(0, 220, 180, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(size // 16))
    img = Image.alpha_composite(img, glow)

    draw = ImageDraw.Draw(img)

    # Background gradient circle (dark teal core).
    draw.ellipse(bbox, fill=(18, 24, 36, 255))

    # Inner ring.
    ring_margin = size // 8
    ring_bbox = [
        margin + ring_margin,
        margin + ring_margin,
        size - margin - ring_margin,
        size - margin - ring_margin,
    ]
    draw.ellipse(ring_bbox, outline=(0, 220, 180, 255), width=max(2, size // 48))

    # Accent arc at top-right.
    arc_width = max(4, size // 24)
    draw.arc(
        ring_bbox,
        start=-60,
        end=30,
        fill=(0, 255, 200, 255),
        width=arc_width,
    )

    # Text "EV" centered.
    font_size = size // 3
    font = _find_font(font_size)
    text = "EV"
    # Text bounding box differs by font; use textbbox to center.
    tb = draw.textbbox((0, 0), text, font=font)
    text_w = tb[2] - tb[0]
    text_h = tb[3] - tb[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - (text_h // 8)
    draw.text((x, y), text, font=font, fill=(240, 248, 255, 255))

    return img


def _ico_header(count: int) -> bytes:
    """Return an ICO directory header for `count` images."""
    return struct.pack("<HHH", 0, 1, count)


def _ico_entry(width: int, height: int, offset: int, size: int) -> bytes:
    """Return a single ICO directory entry."""
    w = 0 if width >= 256 else width
    h = 0 if height >= 256 else height
    return struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, offset)


def _build_ico(images: Iterable[tuple[int, Image.Image]]) -> bytes:
    """Build a Windows ICO file from a list of (size, image) tuples."""
    size_list = [(size, img.copy()) for size, img in images]
    pngs: list[bytes] = []
    entries: list[bytes] = []
    offset = 6 + 16 * len(size_list)
    for size, img in size_list:
        # Ensure square at exact size.
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        png_bytes = _png_bytes(img)
        entries.append(_ico_entry(size, size, offset, len(png_bytes)))
        pngs.append(png_bytes)
        offset += len(png_bytes)
    return _ico_header(len(size_list)) + b"".join(entries) + b"".join(pngs)


def _png_bytes(img: Image.Image) -> bytes:
    """Return PNG bytes for an image."""
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_icns(images: Iterable[tuple[str, Image.Image]]) -> bytes:
    """Build a macOS ICNS file from a list of (type, image) tuples.

    This is a minimal ICNS writer sufficient for Tauri bundle validation.
    """
    chunks: list[bytes] = []
    for type_code, img in images:
        png = _png_bytes(img)
        chunks.append(type_code.encode("ascii") + struct.pack(">I", 8 + len(png)) + png)
    return b"".join(chunks)


def generate_icon_set(out_dir: Path) -> list[Path]:
    """Generate all icon files required by Tauri and return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256, 512, 1024]
    rendered = {size: _make_base(size) for size in sizes}

    files: list[Path] = []

    # Individual PNGs used by tauri.conf.json.
    for name, size in [
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
    ]:
        path = out_dir / name
        rendered[size].save(path)
        files.append(path)

    # A larger square PNG for fallback / web use.
    icon_png = out_dir / "icon.png"
    rendered[256].save(icon_png)
    files.append(icon_png)

    # Windows ICO with common sizes.
    ico_path = out_dir / "icon.ico"
    ico_sizes = [(256, rendered[256]), (128, rendered[128]), (64, rendered[128].resize((64, 64))), (48, rendered[128].resize((48, 48))), (32, rendered[32]), (16, rendered[32].resize((16, 16)))]
    ico_path.write_bytes(_build_ico(ico_sizes))
    files.append(ico_path)

    # macOS ICNS with standard type codes.
    icns_images = [
        ("icp4", rendered[16].resize((16, 16))),
        ("icp5", rendered[32]),
        ("icp6", rendered[64].resize((64, 64))),
        ("ic07", rendered[128]),
        ("ic08", rendered[256]),
        ("ic09", rendered[512]),
        ("ic10", rendered[1024]),
    ]
    icns_path = out_dir / "icon.icns"
    icns_path.write_bytes(_build_icns(icns_images))
    files.append(icns_path)

    return files


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    icon_dir = repo_root / "desktop" / "src-tauri" / "icons"
    generated = generate_icon_set(icon_dir)
    for path in generated:
        print(path)
