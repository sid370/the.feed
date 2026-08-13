"""Pull a real portrait per character from Wikipedia, into web/public/avatars/.

Only freely-licensed files are taken. English Wikipedia forbids non-free images of living
people, so a lead image hosted on Commons is reliably free; a file served from the local
/wikipedia/en/ path is fair-use and is skipped rather than downloaded. Anyone skipped keeps
the generated SVG from avatars.py, so the cast never renders with a hole in it.

CC-BY and CC-BY-SA both require attribution, so every download is recorded in
web/public/avatars/CREDITS.md with its author and licence.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "web" / "public" / "avatars"

# Handles are ours; these are the article titles they map to.
ARTICLES = {
    "darioamodei": "Dario Amodei",
    "donaldtrump": "Donald Trump",
    "drake": "Drake (musician)",
    "elonmusk": "Elon Musk",
    "jensenhuang": "Jensen Huang",
    "kendricklamar": "Kendrick Lamar",
    "killtony": "Tony Hinchcliffe",
    "kimjongun": "Kim Jong Un",
    "kyliejenner": "Kylie Jenner",
    "narendramodi": "Narendra Modi",
    "putin": "Vladimir Putin",
    "samaltman": "Sam Altman",
    "serenawilliams": "Serena Williams",
    "theweeknd": "The Weeknd",
    "travisscott": "Travis Scott",
    "markknopfler": "Mark Knopfler",
    "pankajtripathi": "Pankaj Tripathi",
    "fredagain": "Fred Again",
    "viratkohli": "Virat Kohli",
    "ronaldo": "Cristiano Ronaldo",
    "messi": "Lionel Messi",
    "federer": "Roger Federer",
    "nadal": "Rafael Nadal",
    "willsmith": "Will Smith",
    "mattdamon": "Matt Damon",
    "haaland": "Erling Haaland",
    "mcgregor": "Conor McGregor",
    # Fictional — no article lead image can serve, so FILE_OVERRIDES supplies the file.
    "tonystark": "Iron Man",
}

# Named Commons files for the two the lead image can't serve: Travis Scott's article leads
# with his signature, and Tony Stark is fictional, so the armour at a convention is the only
# free photograph of him there can be.
FILE_OVERRIDES = {
    "travisscott": "Travis Scott February 2016.jpg",
    "tonystark": "WonderCon 2014 - Iron Man Cosplay (13955026033).jpg",
}

# Zoom and offset for a source the default top-square crop frames badly, as
# (scale_width, side, offset_top, offset_left). Tony Stark's is a wide convention floor
# shot, so it needs pushing in onto the helmet and off the bystanders behind it.
CROP_OVERRIDES = {
    "tonystark": (820, 440, 40, 250),
}

FREE = ("public domain", "cc0", "cc by", "cc-by", "attribution", "godl")
# Some articles lead with a signature or logo rather than a photograph, and sips cannot
# rasterise those anyway.
RASTER = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
# Wikimedia rate-limits generic agents hard; their policy wants a contact URL in here.
UA = {"User-Agent": "charsocial-avatars/1.0 "
                    "(https://github.com/charsocial/charsocial; hobby project) python-urllib"}
SIZE = 400


def api(host: str, params: dict) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    time.sleep(1)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def lead_image(title: str) -> str | None:
    pages = api("en.wikipedia.org", {
        "action": "query", "prop": "pageimages", "piprop": "original", "titles": title,
    })["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("original", {}).get("source")


def file_url(filename: str) -> str | None:
    pages = api("commons.wikimedia.org", {
        "action": "query", "prop": "imageinfo", "iiprop": "url", "titles": f"File:{filename}",
    })["query"]["pages"]
    return next(iter(pages.values())).get("imageinfo", [{}])[0].get("url")


def licence(filename: str) -> tuple[str, str]:
    """Returns (licence, author) straight from the Commons file record."""
    pages = api("commons.wikimedia.org", {
        "action": "query", "prop": "imageinfo", "iiprop": "extmetadata",
        "titles": f"File:{filename}",
    })["query"]["pages"]
    meta = next(iter(pages.values())).get("imageinfo", [{}])[0].get("extmetadata", {})
    name = meta.get("LicenseShortName", {}).get("value", "unknown")
    # The author field arrives as HTML with links wrapped around the name.
    author = re.sub(r"<[^>]*>", " ", meta.get("Artist", {}).get("value", ""))
    author = " ".join(html.unescape(author).split()) or "unknown"
    return name, author


def square(src: Path, dst: Path, crop: tuple[int, int, int, int] | None = None) -> None:
    """Scale to width, then crop a square off the top — portraits put the face there."""
    if crop:
        scale, side, top, left = crop
        subprocess.run(["sips", "-s", "format", "jpeg", "--resampleWidth", str(scale),
                        str(src), "--out", str(dst)], check=True, capture_output=True)
        subprocess.run(["sips", "-c", str(side), str(side), "--cropOffset", str(top), str(left),
                        str(dst)], check=True, capture_output=True)
        subprocess.run(["sips", "--resampleWidth", str(SIZE), str(dst)],
                       check=True, capture_output=True)
        return

    subprocess.run(["sips", "-s", "format", "jpeg", "--resampleWidth", str(SIZE),
                    str(src), "--out", str(dst)], check=True, capture_output=True)
    height = int(subprocess.run(["sips", "-g", "pixelHeight", str(dst)],
                                check=True, capture_output=True, text=True
                                ).stdout.split(":")[-1])
    top = min(SIZE, height)
    subprocess.run(["sips", "-c", str(top), str(SIZE), "--cropOffset", "0", "0",
                    str(dst)], check=True, capture_output=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits, skipped = [], []

    for handle, title in sorted(ARTICLES.items()):
        if handle in FILE_OVERRIDES:
            filename = FILE_OVERRIDES[handle]
            source = file_url(filename)
            if not source:
                skipped.append((handle, f"override not found: {filename}"))
                continue
        else:
            source = lead_image(title)
            if not source:
                skipped.append((handle, "no lead image"))
                continue
            if "/wikipedia/commons/" not in source:
                skipped.append((handle, "non-free (local fair-use file)"))
                continue
            # The API appends utm tracking params; they are not part of the file name.
            filename = urllib.parse.unquote(source.split("?")[0].rsplit("/", 1)[-1])

        if not filename.lower().endswith(RASTER):
            skipped.append((handle, f"not a photograph: {filename}"))
            continue
        name, author = licence(filename)
        if not any(f in name.lower() for f in FREE):
            skipped.append((handle, f"licence not free: {name}"))
            continue

        raw = OUT_DIR / f".{handle}.raw"
        try:
            with urllib.request.urlopen(urllib.request.Request(source, headers=UA), timeout=60) as r:
                raw.write_bytes(r.read())
            square(raw, OUT_DIR / f"{handle}.jpg", CROP_OVERRIDES.get(handle))
        except Exception as exc:
            # One unreadable file must not cost the whole run.
            skipped.append((handle, f"could not convert: {exc}"))
            continue
        finally:
            raw.unlink(missing_ok=True)

        credits.append(f"- **{handle}** — [{filename}]"
                       f"(https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(filename)}) "
                       f"by {author}, {name}")
        print(f"ok   {handle:16} {name}")

    for handle, why in skipped:
        print(f"skip {handle:16} {why}")

    (OUT_DIR / "CREDITS.md").write_text(
        "# Avatar credits\n\n"
        "Portraits from Wikimedia Commons. Anyone not listed uses the generated SVG from\n"
        "`scripts/avatars.py` instead — no free portrait was available.\n\n"
        + "\n".join(credits) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
