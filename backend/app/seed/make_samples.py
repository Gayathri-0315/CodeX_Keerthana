"""Draws the sample posters (and, later, timetables) with dates relative to today.

They're regenerated on every seed so the date printed on a poster matches what mock extraction returns.
"""

import json
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..services.extraction import next_weekday
from ..timeutil import ist_today

SEED_DIR = Path(__file__).parent
POSTERS = SEED_DIR / "posters"
W, H = 900, 1200


# System fonts with a ₹ glyph; Pillow's built-in font lacks it, so it's the last resort.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]
_FONT_PATH = next((p for p in FONT_CANDIDATES if Path(p).is_file()), None)


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size) if _FONT_PATH else ImageFont.load_default(size=size)


def _txt(s: str) -> str:
    return s if _FONT_PATH else s.replace("₹", "Rs. ").replace("–", "-")


def _gradient(a: str, b: str) -> Image.Image:
    ca = tuple(int(a[i : i + 2], 16) for i in (1, 3, 5))
    cb = tuple(int(b[i : i + 2], 16) for i in (1, 3, 5))
    mid = tuple((ca[i] + cb[i]) // 2 for i in range(3))
    # A 2x2 image scaled up bilinearly is a diagonal gradient, without a per-pixel loop.
    corners = Image.new("RGB", (2, 2))
    corners.putdata([ca, mid, mid, cb])
    return corners.resize((W, H), Image.Resampling.BILINEAR, reducing_gap=None)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _clock(hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h = h % 12 or 12
    return f"{h}{'' if m == 0 else f':{m:02d}'} {suffix}"


def draw_poster(spec: dict, today: date) -> Image.Image:
    style = spec["poster"]
    img = _gradient(*style["bg"])
    d = ImageDraw.Draw(img)
    white = (255, 255, 255)
    x, y = 70, 90
    d.text((x, y), style["kicker"], font=_font(30), fill=white)
    y += 90
    title_font = _font(78)
    for line in _wrap(d, spec["title"], title_font, W - 140):
        d.text((x, y), line, font=title_font, fill=white)
        y += 92
    y += 30
    for line in _wrap(d, spec["description"], _font(32), W - 140)[:5]:
        d.text((x, y), line, font=_font(32), fill=(255, 255, 255, 230))
        y += 44

    when = next_weekday(spec["day"], today)
    end = style.get("end_display") or _clock(spec["end_time"])
    lines = [
        when.strftime("%A, %d %B").upper(),
        f"{_clock(spec['start_time'])} – {end}",
        spec["venue_name"] or "ONLINE",
        spec["address"] or (spec.get("registration_url") or ""),
    ]
    y = H - 420
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle((50, y - 30, W - 50, H - 150), radius=36, fill=(0, 0, 0, 64), outline=white, width=4)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((x + 10, y), _txt(line), font=_font(44 if i < 2 else 34), fill=white)
        y += 62 if i < 2 else 50
    d.text((x, H - 110), _txt(style["price"]), font=_font(52), fill=white)
    if style.get("extra"):
        d.text((x + 420, H - 100), _txt(style["extra"]), font=_font(30), fill=white)
    return img


def make_posters(today: date | None = None) -> list[Path]:
    today = today or ist_today()
    out_dir = POSTERS / "generated"
    out_dir.mkdir(exist_ok=True)
    stamp = out_dir / ".date"
    specs = sorted(POSTERS.glob("*.json"))
    fresh = stamp.is_file() and stamp.read_text() == today.isoformat()
    if fresh and all((out_dir / f"{s.stem}.png").is_file() for s in specs):
        return [out_dir / f"{s.stem}.png" for s in specs]  # already drawn for today's dates
    written = []
    for spec_file in specs:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        path = out_dir / f"{spec_file.stem}.png"
        draw_poster(spec, today).save(path, "PNG")
        written.append(path)
    stamp.write_text(today.isoformat())
    return written


def sample_posters() -> list[dict]:
    out_dir = POSTERS / "generated"
    return [{"name": p.stem, "title": json.loads((POSTERS / f"{p.stem}.json").read_text(encoding="utf-8"))["title"]}
            for p in sorted(out_dir.glob("*.png")) if (POSTERS / f"{p.stem}.json").is_file()]


if __name__ == "__main__":
    for p in make_posters():
        print(p)
