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
    "dubaiprince": "Hamdan bin Mohammed Al Maktoum",
    "saudiking": "Salman of Saudi Arabia",
    "ericclapton": "Eric Clapton",
    "rahulgandhi": "Rahul Gandhi",
    "kanyewest": "Kanye West",
    "karanaujla": "Karan Aujla",
    "torylanez": "Tory Lanez",
    "benbohmer": "Ben Böhmer",
    # Band articles, so the lead image is the group rather than the principal.
    "tameimpala": "Tame Impala",
    "porcupinetree": "Porcupine Tree",
}

# Corporate accounts take a logo rather than a portrait, which changes two things: the file
# is usually SVG, and a wordmark must be fitted whole rather than cropped to a face.
LOGOS = {
    "meta": "Meta Platforms",
    "amazon": "Amazon (company)",
    "netflix": "Netflix",
    "google": "Google",
    "apple": "Apple Inc.",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "datadog": "Datadog",
    "aramco": "Saudi Aramco",
}

# Named Commons files for the cases the lead image can't serve.
FILE_OVERRIDES = {
    # His article leads with his signature rather than a photograph.
    "travisscott": "Travis Scott February 2016.jpg",
    # The article holds its logo in the infobox, so pageimages returns nothing.
    "aramco": "Saudi aramco logo.svg",
    # A wordmark is illegible at 26px and Amazon's article leads with a photograph of an
    # office block, so each of these names the symbol-only mark instead.
    "google": 'Google "G" logo.svg',
    "amazon": "Amazon icon.svg",
    "openai": "OpenAI logo 2025 (symbol).svg",
    "anthropic": "Anthropic.png",
}

# Named exceptions to the free-licence rule: a trademark used to identify the company it
# depicts, which is the same nominative basis Wikipedia hosts these on. A `wiki:` value is a
# filename in en.wikipedia's fair-use pool, anything else is a direct URL. Listed separately
# in CREDITS.md so the exception stays visible rather than blending into the free files.
TRADEMARKS = {
    "datadog": "wiki:Datadog logo.svg",
    "netflix": "https://images.icon-icons.com/2699/PNG/512/netflix_logo_icon_170919.png",
    "meta": "https://yt3.googleusercontent.com/iBn9KeDnKNffvLlHQXPjl8VNkhuMp8N7FPx"
            "f6n6dwI85cWH6SE4DsuDLchoQNJNb5KB9oIlyzw=s900-c-k-c0x00ffffff-no-rj",
}

FREE = ("public domain", "cc0", "cc by", "cc-by", "attribution", "godl")
RASTER = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
# Most logos on Commons are SVG, which sips cannot read. Commons renders one to PNG on
# request, so the thumbnailer does the rasterising for us.
VECTOR = (".svg",)
# Wikimedia rate-limits generic agents hard; their policy wants a contact URL in here.
UA = {"User-Agent": "charsocial-avatars/1.0 "
                    "(https://github.com/charsocial/charsocial; hobby project) python-urllib"}
SIZE = 400
LOGO_PAD = 40


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


def thumb_url(filename: str, width: int) -> str | None:
    """Commons rasterises SVG on demand, which is the only way to get a logo past sips."""
    pages = api("commons.wikimedia.org", {
        "action": "query", "prop": "imageinfo", "iiprop": "url",
        "iiurlwidth": width, "titles": f"File:{filename}",
    })["query"]["pages"]
    return next(iter(pages.values())).get("imageinfo", [{}])[0].get("thumburl")


def en_thumb_url(filename: str, width: int) -> str | None:
    """en.wikipedia hosts the fair-use pool; Commons never will."""
    pages = api("en.wikipedia.org", {
        "action": "query", "prop": "imageinfo", "iiprop": "url",
        "iiurlwidth": width, "titles": f"File:{filename}",
    })["query"]["pages"]
    return next(iter(pages.values())).get("imageinfo", [{}])[0].get("thumburl")


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


def fit_square(src: Path, dst: Path) -> None:
    """Fit a wordmark whole and pad it, because cropping a logo to a square beheads it.

    A mark that is already square usually carries its own ground, and padding one of those
    frames it in a white border instead of filling the tile.
    """
    dims = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(src)],
                          check=True, capture_output=True, text=True).stdout.split()
    width, height = int(dims[-3]), int(dims[-1])
    if 0.91 < width / height < 1.1:
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", str(SIZE),
                        str(src), "--out", str(dst)], check=True, capture_output=True)
        return

    subprocess.run(["sips", "-s", "format", "jpeg", "-Z", str(SIZE - LOGO_PAD * 2),
                    str(src), "--out", str(dst)], check=True, capture_output=True)
    subprocess.run(["sips", "-p", str(SIZE), str(SIZE), "--padColor", "FFFFFF", str(dst)],
                   check=True, capture_output=True)


def square(src: Path, dst: Path) -> None:
    """Scale to width, then crop a square off the top — portraits put the face there."""
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
    credits, trademarks, skipped = [], [], []

    for handle, title in sorted({**ARTICLES, **LOGOS}.items()):
        is_logo = handle in LOGOS
        if handle in TRADEMARKS:
            ref = TRADEMARKS[handle]
            filename = ref.removeprefix("wiki:")
            source = en_thumb_url(filename, SIZE * 2) if ref.startswith("wiki:") else ref
            if not source:
                skipped.append((handle, f"trademark not found: {filename}"))
                continue
            raw = OUT_DIR / f".{handle}.raw"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(source, headers=UA), timeout=60
                ) as r:
                    raw.write_bytes(r.read())
                fit_square(raw, OUT_DIR / f"{handle}.jpg")
            except Exception as exc:
                skipped.append((handle, f"could not convert: {exc}"))
                continue
            finally:
                raw.unlink(missing_ok=True)
            trademarks.append(f"- **{handle}** — {filename}, trademark of its owner")
            print(f"ok   {handle:16} trademark (fair use)")
            continue

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

        if filename.lower().endswith(VECTOR):
            source = thumb_url(filename, SIZE * 2)
            if not source:
                skipped.append((handle, f"could not rasterise: {filename}"))
                continue
        elif not filename.lower().endswith(RASTER):
            skipped.append((handle, f"not an image: {filename}"))
            continue

        name, author = licence(filename)
        if not any(f in name.lower() for f in FREE):
            skipped.append((handle, f"licence not free: {name}"))
            continue

        raw = OUT_DIR / f".{handle}.raw"
        try:
            with urllib.request.urlopen(urllib.request.Request(source, headers=UA), timeout=60) as r:
                raw.write_bytes(r.read())
            if is_logo:
                fit_square(raw, OUT_DIR / f"{handle}.jpg")
            else:
                square(raw, OUT_DIR / f"{handle}.jpg")
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
        "Portraits and logos from Wikimedia Commons. Anyone not listed uses the generated\n"
        "SVG from `scripts/avatars.py` instead — no free image was available.\n\n"
        + "\n".join(credits) + "\n\n"
        "## Trademarks, used to identify the company depicted\n\n"
        "Not freely licensed, and each is named in `TRADEMARKS` in `scripts/fetch_avatars.py`\n"
        "rather than passing the licence gate. Used nominatively on a parody feed.\n\n"
        + "\n".join(trademarks) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
