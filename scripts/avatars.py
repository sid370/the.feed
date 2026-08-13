"""Generate one avatar per character into web/public/avatars/.

Deterministic from the handle, so a character keeps the same face across regenerations.
The hue matches lib/api.ts avatarColor() exactly: if an image ever fails to load, the
initials fallback underneath comes up in the same colour instead of flashing a new one.

Art rather than photographs on purpose. Every character here performs a real public
figure, and a real headshot on an account that posts generated text is what makes a
parody read as authentic. Drop a real <handle>.png in and point the character file at it
to override any of these.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = ROOT / "characters"
OUT_DIR = ROOT / "web" / "public" / "avatars"

JSON_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

GROUND = "#14181f"
BOX = 96


def hash32(seed: str) -> int:
    """Mirrors the `(hash * 31 + charCode) | 0` loop in lib/api.ts."""
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return h


def initials(name: str) -> str:
    words = re.sub(r"\(.*?\)", "", name).split()
    return "".join(w[0] for w in words[:2]).upper()


def texture(kind: int, hue: int) -> str:
    """A dim geometric ground per character, so two shared hues still read apart."""
    dim = f"hsl({hue} 38% 34%)"
    if kind == 0:
        return "".join(
            f'<circle cx="0" cy="{BOX}" r="{r}" fill="none" stroke="{dim}" stroke-width="3"/>'
            for r in (30, 52, 74, 96)
        )
    if kind == 1:
        return "".join(
            f'<rect x="0" y="{y}" width="{BOX}" height="4" fill="{dim}"/>'
            for y in range(6, BOX, 14)
        )
    if kind == 2:
        return "".join(
            f'<circle cx="{x}" cy="{y}" r="3" fill="{dim}"/>'
            for y in range(12, BOX, 18)
            for x in range(12, BOX, 18)
        )
    return "".join(
        f'<line x1="{x}" y1="0" x2="{x - BOX}" y2="{BOX}" stroke="{dim}" stroke-width="3"/>'
        for x in range(0, BOX * 2, 16)
    )


def svg(handle: str, name: str) -> str:
    h = hash32(handle)
    hue = abs(h) % 360
    mark = initials(name) or handle[:2].upper()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BOX} {BOX}" role="img" aria-label="{name}">
  <rect width="{BOX}" height="{BOX}" fill="{GROUND}"/>
  <g opacity="0.55">{texture(abs(h >> 8) % 4, hue)}</g>
  <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central"
        font-family="ui-monospace, SFMono-Regular, Menlo, monospace"
        font-size="40" font-weight="700" fill="hsl({hue} 62% 66%)">{mark}</text>
</svg>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in sorted(CHARACTERS_DIR.glob("*.md")):
        fence = JSON_FENCE.search(path.read_text(encoding="utf-8"))
        if not fence:
            raise ValueError(f"{path.name}: no ```json block")
        entry = json.loads(fence.group(1))
        out = OUT_DIR / f"{entry['handle']}.svg"
        out.write_text(svg(entry["handle"], entry["name"]), encoding="utf-8")
        written += 1
    print(f"wrote {written} avatars to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
