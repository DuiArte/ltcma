"""Wave r3: the share images, written into <repo>/assets/img (their source of truth; 17 copies them into docs/ through
design_system.emit_share, like the hero images).
  favicon.svg          the header's CD mark (design_system ET_CSS .brand::before: Oxford-blue rounded square, white
                       serif "CD"); a prefers-color-scheme:dark variant inside the SVG (the dark theme's accent
                       #9CBDEB with the dark on-accent ink #0C1420), so it reads on light and dark browser chrome.
                       Text, not glyph outlines: no font data is embedded (the browser's serif draws it, like the header)
  favicon_32.png       32 x 32, the light mark (rounded, transparent corners)
  apple_touch_180.png  180 x 180, full-bleed square (iOS rounds it; a transparent corner would turn black)
  og_<key>.png         1200 x 630 typographic link-preview cards, one per main tab (+ one for the Research corner):
                       warm ground, the CD mark, the page name, one line, the URL. No figure (it would go stale in
                       every preview cache) and no photograph (a JWST crop in a preview travels without its CC BY credit)
Raster text is drawn with the system's Georgia / Segoe UI / Consolas (the site's Spectral / Inter / JetBrains Mono are
web fonts, not installed here); the output is an image, no font file is shipped. No metadata chunk is written (PNG:
IHDR / PLTE? / IDAT / IEND only; checked here and by ds_gate R5).
usage: python -X utf8 -B tools/make_share_assets.py <repo>   (rewrites the 10 files; commit them as sources)
Shipped by wave r3 (2026-11-10); the card text lives in CARDS below, the page metadata in design_system.PAGE_META."""
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(sys.argv[1]).resolve()
assert (REPO / "scripts" / "design_system.py").is_file(), f"refused: {REPO} is not the site repo"
OUT = REPO / "assets" / "img"
F = Path(r"C:\Windows\Fonts")
SERIF, SANS, SANS_B, MONO = F / "georgia.ttf", F / "segoeui.ttf", F / "segoeuib.ttf", F / "consola.ttf"
NAVY, WHITE, GROUND, INK, SEC, MUTED, AMBER, LINE = ("#0A2540", "#FFFFFF", "#F6F5F1", "#0E1726", "#4A5568", "#667085",
                                                       "#B45309", "#E3E1DA")
CARDS = {
    "home": ("Capital Market Assumptions", "A long-run model, my own live book and the markets around it", ""),
    "portfolio": ("Portfolio", "My own equity book, in pesos or dollars, against the S&P 500", "portfolio.html"),
    "stocks": ("Stock Research", "Composite picks, a pick tracker and CFA-style analyses of stocks", "stocks.html"),
    "regime": ("Regime Tracker", "A composite stress index: economic, political, AI-cycle, environmental", "regime.html"),
    "market_intel": ("Market Intel", "What the Street expects, set against this site's own model", "ltcma-consensus.html"),
    "congress": ("Congress", "The trades members of Congress disclose, checked every weekday",
                 "congressional-activity.html"),
    "research": ("Research", "The model, the research record, the strategies and the sources", "research-library.html"),
}
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
       '<style>rect{fill:#0A2540}text{fill:#FFFFFF}'
       '@media (prefers-color-scheme:dark){rect{fill:#9CBDEB}text{fill:#0C1420}}</style>'
       '<rect width="64" height="64" rx="17"/>'
       '<text x="32" y="43.5" text-anchor="middle" font-family="Georgia,\'Times New Roman\',serif" font-size="30"'
       ' font-weight="500" letter-spacing="-0.5">CD</text></svg>\n')


def mark(size, radius_frac=0.27, ss=8):
    """The CD mark at `size` px, drawn at ss x and downsampled (anti-aliased)."""
    s = size * ss
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * radius_frac), fill=NAVY)
    f = ImageFont.truetype(str(SERIF), int(s * 0.47))
    bb = d.textbbox((0, 0), "CD", font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((s - w) / 2 - bb[0], (s - h) / 2 - bb[1] + s * 0.01), "CD", font=f, fill=WHITE)
    return im.resize((size, size), Image.LANCZOS)


def fit(d, text, path, size, maxw):
    while size > 12:
        f = ImageFont.truetype(str(path), size)
        if d.textlength(text, font=f) <= maxw:
            return f
        size -= 2
    return ImageFont.truetype(str(path), size)


def card(key, name, line, path):
    W, H, M = 1200, 630, 84
    im = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(im)
    d.rectangle((0, H - 10, W, H), fill=NAVY)                              # a navy foot, like the header rule
    im.paste(mark(104), (M, 74), mark(104))
    fb = ImageFont.truetype(str(SANS_B), 30)
    fbl = ImageFont.truetype(str(SANS), 30)
    d.text((M + 104 + 28, 88), "Carlos Duarte", font=fb, fill=INK)
    d.text((M + 104 + 28, 128), "Quantitative Research", font=fbl, fill=SEC)
    d.rectangle((M, 262, M + 88, 268), fill=AMBER)                         # the amber kicker rule
    fn = fit(d, name, SERIF, 92, W - 2 * M)
    d.text((M, 292), name, font=fn, fill=INK)
    fl = fit(d, line, SANS, 36, W - 2 * M)
    d.text((M, 418), line, font=fl, fill=SEC)
    d.line((M, 512, W - M, 512), fill=LINE, width=2)
    fm = ImageFont.truetype(str(MONO), 27)
    d.text((M, 534), "duiarte.github.io/ltcma/" + path, font=fm, fill=MUTED)
    return im


def png_chunks(p):
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    i, out = 8, []
    while i < len(b):
        n = int.from_bytes(b[i:i + 4], "big")
        t = b[i + 4:i + 8].decode("latin-1")
        out.append(t)
        crc = int.from_bytes(b[i + 8 + n:i + 12 + n], "big")
        assert crc == zlib.crc32(b[i + 4:i + 8 + n]) & 0xFFFFFFFF, f"{p.name}: bad CRC in {t}"
        i += 12 + n
    return out


OUT.mkdir(parents=True, exist_ok=True)
(OUT / "favicon.svg").write_bytes(SVG.encode("ascii"))
mark(32).save(OUT / "favicon_32.png", "PNG", optimize=True)
t = Image.new("RGB", (180, 180), NAVY)
m = mark(180, radius_frac=0.0)
t.paste(m, (0, 0), m)
t.save(OUT / "apple_touch_180.png", "PNG", optimize=True)
for k, (name, line, path) in CARDS.items():
    card(k, name, line, path).save(OUT / f"og_{k}.png", "PNG", optimize=True)
for p in sorted(OUT.glob("*.png")):
    if p.name.startswith(("og_", "favicon", "apple_touch")):
        ch = png_chunks(p)
        extra = [c for c in ch if c not in ("IHDR", "PLTE", "tRNS", "IDAT", "IEND")]
        assert not extra, f"{p.name}: metadata chunks {extra}"
        with Image.open(p) as im:
            print(f"{p.name:22s} {im.size[0]}x{im.size[1]} {im.mode:5s} {p.stat().st_size:7,} B chunks {sorted(set(ch))}")
print(f"favicon.svg            {(OUT / 'favicon.svg').stat().st_size} B")
