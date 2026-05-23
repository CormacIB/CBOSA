"""
Download KaTeX assets into cbosa/resources/katex/ for offline use.
Run once from the project root: python tools/fetch_katex.py
"""
import pathlib
import urllib.request

VERSION = "0.16.11"
CDN = f"https://cdn.jsdelivr.net/npm/katex@{VERSION}/dist"

DEST = pathlib.Path(__file__).parent.parent / "cbosa" / "resources" / "katex"

FILES = [
    "katex.min.js",
    "katex.min.css",
    "contrib/auto-render.min.js",
]

FONTS = [
    "KaTeX_AMS-Regular.woff2",
    "KaTeX_Caligraphic-Bold.woff2",
    "KaTeX_Caligraphic-Regular.woff2",
    "KaTeX_Fraktur-Bold.woff2",
    "KaTeX_Fraktur-Regular.woff2",
    "KaTeX_Main-Bold.woff2",
    "KaTeX_Main-BoldItalic.woff2",
    "KaTeX_Main-Italic.woff2",
    "KaTeX_Main-Regular.woff2",
    "KaTeX_Math-BoldItalic.woff2",
    "KaTeX_Math-Italic.woff2",
    "KaTeX_SansSerif-Bold.woff2",
    "KaTeX_SansSerif-Italic.woff2",
    "KaTeX_SansSerif-Regular.woff2",
    "KaTeX_Script-Regular.woff2",
    "KaTeX_Size1-Regular.woff2",
    "KaTeX_Size2-Regular.woff2",
    "KaTeX_Size3-Regular.woff2",
    "KaTeX_Size4-Regular.woff2",
    "KaTeX_Typewriter-Regular.woff2",
]


def fetch(url: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  skip  {dest.relative_to(DEST.parent.parent)}")
        return
    print(f"  fetch {dest.relative_to(DEST.parent.parent)}")
    urllib.request.urlretrieve(url, dest)


if __name__ == "__main__":
    print(f"Downloading KaTeX {VERSION} → {DEST.relative_to(pathlib.Path.cwd())}\n")
    for f in FILES:
        fetch(f"{CDN}/{f}", DEST / f)
    for f in FONTS:
        fetch(f"{CDN}/fonts/{f}", DEST / "fonts" / f)
    print("\nDone. KaTeX will now load offline.")
