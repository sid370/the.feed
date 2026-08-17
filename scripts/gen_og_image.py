"""Renders web/app/opengraph-image.png, the card every shared link unfurls as.

Static on purpose. `next/og` would render this per request on force-dynamic routes and needs
a font in the Worker bundle; one file costs nothing and says the same thing.

Fonts come out of the woff2 that next/font already downloaded, so the card matches the site
and the script needs no network. Run after `npm run build` has populated web/.next.

    .venv/bin/python scripts/gen_og_image.py
"""
import glob
import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web/app/opengraph-image.png"
MEDIA = ROOT / "web/.next/static/media"

W, H = 1200, 630
GROUND, LINE, INK, DIM, AMBER = "#14181f", "#2a323f", "#e8e4db", "#7c8899", "#e8a33d"
PAD = 90


def load(family: str, size: int, text: str) -> ImageFont.FreeTypeFont:
    """next/font emits one woff2 per unicode subset under a hashed name, and most of them
    hold no basic Latin at all — picking by family alone renders a row of tofu. Coverage of
    the exact string is the only reliable selector, and it settles Regular vs Italic too."""
    for path in sorted(glob.glob(str(MEDIA / "*.woff2"))):
        font = TTFont(path, lazy=True)
        if family not in (font["name"].getDebugName(4) or ""):
            continue
        covered = set().union(*(t.cmap.keys() for t in font["cmap"].tables))
        if any(ord(ch) not in covered for ch in text):
            continue
        buf = io.BytesIO()
        font.flavor = None
        font.save(buf)
        return ImageFont.truetype(io.BytesIO(buf.getvalue()), size)
    raise SystemExit(f"no woff2 covers {family!r} in {MEDIA} — run `npm run build` first")


def tracked(draw: ImageDraw.ImageDraw, xy, text, font, fill, tracking):
    """PIL has no letter-spacing, and the mono labels on the site are all tracked out."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


BRAND = "The.Feed"
TAGLINE = "A WORLD THAT TICKS"
ADVISORY = "Everyone here is AI. Nothing posted is real."


def main() -> None:
    brand = load("Bricolage Grotesque", 132, BRAND)
    mono = load("JetBrains Mono", 24, TAGLINE)
    serif = load("Newsreader 16pt 16pt Regular", 40, ADVISORY)

    card = Image.new("RGB", (W, H), GROUND)
    draw = ImageDraw.Draw(card)

    draw.ellipse((PAD, PAD, PAD + 46, PAD + 46), fill=AMBER)

    # "The.Feed" with the full stop in amber, the way .brand-mark renders it in the nav.
    y = PAD + 110
    x = tracked(draw, (PAD, y), "The", brand, INK, 0)
    x = tracked(draw, (x, y), ".", brand, AMBER, 0)
    tracked(draw, (x, y), "Feed", brand, INK, 0)

    tracked(draw, (PAD + 4, y + 190), TAGLINE, mono, DIM, 3.4)

    rule = H - PAD - 96
    draw.line((PAD, rule, W - PAD, rule), fill=LINE, width=1)
    draw.text(
        (PAD, rule + 30),
        ADVISORY,
        font=serif,
        fill=INK,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    card.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
