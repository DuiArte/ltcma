# -*- coding: utf-8 -*-
"""The retail broker and its trading platform on public files, in general words: one scrub, one scan (wave r3s,
2026-11-17; review fix rounds 1 on 2026-11-17, 2 to 5 on 2026-11-19, 6 on 2026-11-24).

Why. Public pages describe the retail broker and its trading platform in general words (Carlos, 2026-11-17). The
words the scrub writes stay true, never name another vendor instead and never suggest exchange data.

The term list is PRIVATE: it is not in this repo, and this file spells no term. It is read at run time from
    <LTCMA_PRIVATE_DATA>/vendor_terms.txt   when that environment variable names a folder (tests), else
    <paths.DOCUMENTS>/LTCMA_private/vendor_terms.txt   (C:/Users/carlo/Documents/LTCMA_private on Windows: the private
                                            folder scripts/private_data.py uses, outside every git repo).
The file describes its own format. Importing this module never reads it; the first scrub(), hits() or scan() does.
A missing, empty or broken list, or one kept inside this repo, raises TermsMissing: the load-bearing guard, ds_gate
R2, confscan and every generator that scrubs then STOP (fail closed) instead of publishing unchecked. Nothing here
prints a matched spelling: a finding names the KIND of term (broker, platform, ...) and where it is.

  scrub(text)     The text in neutral words. Ordered phrase rules first (they read well), then catch-all rules (so a
                  NEW sentence is still neutral), then a tidy step next to each replacement. Idempotent. The words it
                  writes carry no quote mark (safe inside a quoted attribute or a script string). A link to a named
                  site is dropped (its text is kept), never rewritten inside the URL. Base64 payloads (Plotly "bdata"
                  strings, data: URIs) are never touched. A long term (broker, platform, vendor, editor) is
                  rewritten only in the brand's own spelling: the list's spelling in one piece, with its own
                  capitals (a plural "s" or a version may follow; the export file and folder rules also take it in
                  lower case). Any other spelling of a long term (spaced, dashed, other capitals) is found by
                  hits() and left as it is, so the gate fails closed: such words may be ordinary words that are
                  not the brand, and rewriting them could publish an untrue sentence (review fix round 4).
                  The same holds for the short terms (review fix round 5): the scripting language is rewritten
                  only in its own capitals with a version, in one piece; a file kind only in the list's own
                  spelling right after a file name; the short name only by the phrase rules (the home's skills
                  list, a broker server name). Every other form of them that hits() reads (the language without
                  a version, in a plural, with a separator or in other capitals; a file kind alone or in other
                  capitals; the short name outside those rules) is left as it is, so the gate fails closed; the
                  short name and the language are also ordinary acronyms elsewhere (review fix round 6).
  scrub_obj(obj)  scrub() on every string VALUE of a JSON-like object. Keys are left alone.
  hits(text)      The kinds of term a text still carries. The gate's detector; it does not reuse the scrub rules. It
                  reads the text as written; as a browser shows it (HTML entities decoded, every character a browser
                  does not draw dropped: every Unicode format character and every default-ignorable code point,
                  i.e. soft hyphens, zero-width characters, bidi controls, variation selectors, tag characters,
                  fillers, and every C0 / C1 control character but the whitespace ones (review fix round 5); the
                  Braille blank, the object replacement character and the replacement character read as spaces,
                  and a run of line breaks
                  as one line break (review fix round 5); %XX and \\uXXXX / \\xXX escapes decoded, a text data:
                  URI decoded); in plain letters
                  (Unicode NFKC + a small look-alike fold: fullwidth or Cyrillic / Greek look-alike letters); and
                  without accents (Unicode NFKD with every combining mark removed, then the same fold; review fix
                  round 4). Between a term's parts it accepts a run of spaces (one line break at most) and up to
                  three marks of this set: any Unicode dash, a dot, a slash, a middle dot, an underscore (review fix
                  round 5: up to three, e.g. a doubled dash); a plural "s" after a term written in one piece. The
                  broker in its own capitals is also read with up to three of , : ; + | ~ ' * " = ! @ # or an
                  ellipsis between its parts (the wide pass, review fix round 5); in other capitals, and for the
                  other long terms (ordinary capitalized words that ordinary text lists with a comma or a colon
                  between them), these marks are not read. A long term written with a separator inside, inside
                  one of the private list's "ordinary"
                  phrases (an ordinary phrase that is not the brand), is not counted (review fix round 4).
                  A second pass reads JOINED forms, a term right next to other letters or digits (review fix round
                  3): a long term (broker, platform, vendor, editor) in one piece anywhere, unless the run of
                  letters and digits around it is one of the ordinary words of the private list's "allow" lines;
                  a long term written with a separator inside (round 4) when it is glued to a digit, to a
                  lower-case letter on its left while it starts with a capital, or to a capital on its right
                  while it ends in a lower-case letter (the same allow check, on the run with the separators
                  squeezed out); a term the list gives versions, in the list's own capitals with one of them (a
                  separator may sit before the version, round 4), when no capital letter comes right before it
                  and no digit right after it; a symbol with its '#' when no digit follows; a symbol the list
                  lets go without its '#', in its own capitals (a separator may sit between its parts, round 4),
                  when no capital letter comes right before it and no digit right after it.
  scan(repo)      Every public file of the repo: what `git add docs data` would commit (tracked + untracked files,
                  minus what .gitignore keeps out: those are never published) when <repo> is a git work tree, else
                  every file under docs/ and data/. Pages serves docs/, and the GitHub repo shows data/. For each:
                    - its path (a file or folder name can carry a term);
                    - text of any type: UTF-8, or UTF-16 (a BOM, or NUL bytes in a text file), or UTF-32 (a BOM);
                    - Office files, .zip and .gz: every member, by the member's own type;
                    - .xls: the text of every cell and sheet name (xlrd), plus the LONG terms in its raw bytes (a
                      short term can occur by chance in megabytes of binary bytes; a long one cannot);
                    - images: the text metadata (PNG tEXt / iTXt / zTXt, JPEG COM and XMP, WebP XMP) with every
                      term, and the long terms in the binary metadata (EXIF, ICC, other APPn chunks, bytes after the
                      end of the image) -- never the pixels. Text drawn inside a picture needs a look by eye;
                    - fonts: skipped;
                    - a PDF or another binary file: FAILS (unreadable), unless DOC_ALLOW lists its md5 and why.
                  KNOWN lists a file that carries a term ON PURPOSE (data/fx_monthly.csv's column names, while that
                  file is public); every scan prints it, and any other term in that file still fails.

Who calls it.
  glossary.bt_scrub_vendor   backtest cards (23) and the bt_*.html report pages (24), the whole card / page
  glossary._bt_redact        every research text the site did not write (23, 27, research_index for 31)
                             (glossary imports this module on first use, never at import time: 30_market_intel.py
                             needs only glossary.NAV, and the Market Intel tests copy just five site scripts)
  17_build_site.py           the archived report's body
  22_ai_copies.py            report.ai.txt
  24_backtests.py            the catalogue fallback data/backtests_strategies.json
  tools/deploy_docs_r3s.py   commit 2 of the r3s deploy (the committed pages, without a generator)
  guard_vendor_names.py      the load-bearing step in daily_refresh.ps1 (after guard_no_snapshot, before commit)
  tools/ds_gate.py           R2 (site rules), on docs/ and data/
  confscan.sh                its last section; confscan exits 1 on a hit

What it does not cover. Source files (scripts/, tools/, AI_PROCEDURES/, report/, .gitignore) are not pages. git
history keeps every earlier version of every page. The market-data vendor named in the R2 denylist
(ds_gate.PRIVATE_NAMES) is scrubbed by glossary.bt_scrub_vendor, not here. CSS escapes, base64 outside a data: URI,
an entity HTML does not define and a term split across two HTML elements are not decoded. A term hidden by %XX or
JS escapes, and a JOINED form, are detected but not rewritten: the gate then fails (fail closed) until the
generator gets a phrase rule.

CLI:
  python scripts/vendor_names.py --scan [<repo>]   exit 1 when a public file carries a term or cannot be read
  python scripts/vendor_names.py --selftest        exit 1 when a scrub, detector or file-reader case fails (the
                                                   scrub and detector cases are "test" lines of the private list)
  python scripts/vendor_names.py --terms           the private term list in use: its path, md5 and counts per kind
"""
import base64
import gzip
import hashlib
import html
import io
import json
import os
import re
import struct
import subprocess
import sys
import unicodedata
import zipfile
import zlib
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIRS = ("docs", "data")
TERMS_FILE = "vendor_terms.txt"
PRIVATE_ENV = "LTCMA_PRIVATE_DATA"


class TermsMissing(RuntimeError):
    """The private term list cannot be used. Nothing can be checked, so the caller stops (fail closed)."""


# Carlos's Windows profile, as scripts/paths.py writes it (CUSER; /mnt/c/... under WSL). Not imported from paths:
# this module stays standard-library only, so the load-bearing guard cannot break on another module.
_CUSER = "C:\\Users\\carlo" if os.name == "nt" else "/mnt/c/Users/carlo"


def terms_path():
    """Where the private term list is read from (see the module docstring)."""
    folder = os.environ.get(PRIVATE_ENV) or os.path.join(_CUSER, "Documents", "LTCMA_private")
    return os.path.abspath(os.path.join(folder, TERMS_FILE))


def _inside(path, root):
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)), os.path.normcase(root)]) == \
            os.path.normcase(root)
    except ValueError:          # another drive
        return False


# ---------------------------------------------------------------------------------------------------------------
# Separators, boundaries, the plain-letter view.
# First pass: a term starts and ends next to a non-alphanumeric character, so a term inside a file name, a server
# name or brackets matches, while the same letters inside a longer word do not. Case-insensitive. The second pass
# (_Terms.joined, review fix round 3) reads the joined forms. Base64 payloads are never read as words (PROTECT).
_L, _R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
# every Unicode dash (category Pd, Unicode 15; the self-test checks the list against unicodedata), the minus sign and
# the hyphen bullet; then the dot, slash, underscore and middle-dot family (fullwidth forms included)
_DASHES = ("-\u058a\u05be\u1400\u1806\u2010\u2011\u2012\u2013\u2014\u2015\u2e17\u2e1a\u2e3a\u2e3b\u2e40\u2e5d"
           "\u301c\u3030\u30a0\ufe31\ufe32\ufe58\ufe63\uff0d\U00010ead\u2212\u2043")
_DOTS = "_./\xb7\u2022\u2027\u2219\u22c5\u30fb\uff0e\uff0f\uff3f\uff65"
_PUNCT = "[" + "".join("\\" + c if c in "-\\]^" else c for c in _DASHES + _DOTS) + "]"
_H = r"[^\S\r\n]*"                       # a run of spaces (any Unicode space, nbsp included), no line break
# between two parts: spaces, then up to three punctuation marks and at most one line break, anywhere among them
# (each with spaces around; review fix round 5: up to three marks, e.g. a doubled dash, was one)
_X1 = _PUNCT + _H
_NL = r"\r?\n" + _H
_SEP = ("(?:" + _H + "(?:" + _NL + "(?:" + _X1 + "){0,3}|" + _X1 + _NL + "(?:" + _X1 + "){0,2}|" + _X1 + _X1 + _NL +
        "(?:" + _X1 + ")?|" + _X1 + _X1 + _X1 + _NL + "|(?:" + _X1 + "){1,3})?)")
# the wide pass (review fix round 5): the broker in its own capitals with up to three of these marks (or of the
# set above) between its parts; case-sensitive, so ordinary text in other capitals is not read
_WIDE = "[" + re.escape(",:;+|~'*\"=!@#\u2026") + "]"
_XW = "(?:" + _PUNCT + "|" + _WIDE + ")" + _H
_SEPW = ("(?:" + _H + "(?:" + _NL + "(?:" + _XW + "){0,3}|" + _XW + _NL + "(?:" + _XW + "){0,2}|" + _XW + _XW + _NL +
         "(?:" + _XW + ")?|" + _XW + _XW + _XW + _NL + "|(?:" + _XW + "){1,3})?)")
_SEP_BIN = r"[\s_.\-]?"                  # binary carriers: one ASCII separator at most (fewer chance matches)
# look-alike letters (Cyrillic, Greek) folded to the Latin letter they imitate, after Unicode NFKC
_HOMO = {
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y", "\u0445": "x",
    "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u0501": "d", "\u051b": "q", "\u051d": "w", "\u04bb": "h",
    "\u0131": "i", "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K", "\u041c": "M", "\u041d": "H",
    "\u041e": "O", "\u0420": "P", "\u0421": "C", "\u0422": "T", "\u0425": "X", "\u0423": "Y", "\u0405": "S",
    "\u0406": "I", "\u0408": "J", "\u051a": "Q", "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z",
    "\u0397": "H", "\u0399": "I", "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P",
    "\u03a4": "T", "\u03a5": "Y", "\u03a7": "X", "\u03bf": "o",
}
_HOMO_T = str.maketrans(_HOMO)


_HOMO_RE = re.compile("[" + "".join(_HOMO) + "]")


def _fold(text):
    """`text` in plain letters: Unicode NFKC (fullwidth, ligatures, superscripts ...), then the look-alike fold."""
    t = text if unicodedata.is_normalized("NFKC", text) else unicodedata.normalize("NFKC", text)
    return t.translate(_HOMO_T) if _HOMO_RE.search(t) else t


# binary payloads written as text: never read as words, never rewritten
PROTECT = re.compile(r'"bdata":"[^"]*"|data:[A-Za-z0-9.+/-]*(?:;[A-Za-z0-9=._+-]+)*;base64,[A-Za-z0-9+/=]+')
_DATA_URI = re.compile(r"data:([A-Za-z0-9.+/-]*)((?:;[A-Za-z0-9=._+-]+)*);base64,([A-Za-z0-9+/=]+)")
# characters a browser does not draw (review fix round 4): every Unicode format character (category Cf, Unicode
# 15: soft hyphen, Arabic letter mark, zero-width space / non-joiner / joiner, LRM / RLM, bidi embeddings, overrides
# and isolates, word joiner, invisible operators, BOM, interlinear annotation, tag characters, ...) and every other
# default-ignorable code point (combining grapheme joiner, Hangul fillers, Khmer inherent vowels, Mongolian
# variation selectors and vowel separator, variation selectors, the reserved ignorable ranges), and every C0 / C1
# control character but the whitespace ones (tab, line feed, vertical tab, form feed, carriage return, U+001C-001F,
# U+0085; review fix round 5: an HTML parser drops a NUL, a browser draws the others as nothing or a blank). The
# self-test checks the format and control characters against unicodedata. Ranges, both ends included.
_IGNORABLE = ((0x0000, 0x0008), (0x000E, 0x001B), (0x007F, 0x0084), (0x0086, 0x009F), (0x00AD, 0x00AD), (0x034F, 0x034F), (0x0600, 0x0605), (0x061C, 0x061C), (0x06DD, 0x06DD),
              (0x070F, 0x070F), (0x0890, 0x0891), (0x08E2, 0x08E2), (0x115F, 0x1160), (0x17B4, 0x17B5),
              (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164),
              (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFFB), (0x110BD, 0x110BD),
              (0x110CD, 0x110CD), (0x13430, 0x1343F), (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A),
              (0xE0000, 0xE0FFF))


def _cls_char(c):
    return "\\U%08x" % c


_INVIS_CLASS = "[" + "".join(_cls_char(a) + ("-" + _cls_char(b) if b > a else "") for a, b in _IGNORABLE) + "]"
_INVIS_RE = re.compile(_INVIS_CLASS)
# drawn as a blank or a box (review fix round 5): the Braille pattern blank, the object replacement character and
# the replacement character (what a browser shows for a NUL entity)
_BLANKS = {0x2800: " ", 0xFFFC: " ", 0xFFFD: " "}
_BLANK_RE = re.compile("[\u2800\ufffc\ufffd]")
# a run of two or more line breaks (spaces between): one line break in the decoded view (review fix round 5; HTML
# shows it as one space)
_NLRUN = re.compile(r"\r?\n(?:[^\S\r\n]*\r?\n)+")
_MARK_RE = re.compile(r"[^\x00-\x7f]")


def _bare(text):
    """`text` without accents (review fix round 4): Unicode NFKD, every combining mark (Mn / Me) removed, then the
    look-alike fold."""
    t = unicodedata.normalize("NFKD", text)
    t = _MARK_RE.sub(lambda m: "" if unicodedata.category(m.group(0)) in ("Mn", "Me") else m.group(0), t)
    return t.translate(_HOMO_T) if _HOMO_RE.search(t) else t
_JS_ESC = re.compile(r"\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})")

# the kinds of term (what a finding says instead of the spelling)
KINDS = {"broker": "broker", "platform": "platform", "vendor": "platform-vendor", "editor": "platform-editor",
         "short": "platform-short-name", "language": "platform-language", "file": "platform-file",
         "symbol": "broker-symbol"}
BARE_SYMBOL = "broker-symbol-bare"       # a broker symbol written without its '#'
_ROLES = ("broker", "platform", "vendor", "editor", "short", "language", "file", "symbol", "allow", "ordinary",
          "company")
_NEEDED = ("broker", "platform", "vendor", "short", "language", "symbol")
_LONG = ("broker", "platform", "vendor", "editor")      # long terms: read joined anywhere, and in binary bytes
_UPPER = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")
_DIGIT = frozenset("0123456789")
_ALNUM = _UPPER | _LOWER | _DIGIT
# the self-test lines of the private list: test ["scrub", <in>, <out>] | ["pos" | "neg" | "closed", <text>]
_TEST_KINDS = {"scrub": 3, "pos": 2, "neg": 2, "closed": 2}


# ---------------------------------------------------------------------------------------------------------------
# The private term list.
class _Term:
    def __init__(self, role, parts, versions=(), required=False, hash_="", say=""):
        self.role, self.parts, self.versions, self.required, self.hash, self.say = \
            role, parts, list(versions), required, hash_, say

    @property
    def plain(self):
        return "".join(self.parts)


def _parse(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            raw = fh.read()
    except FileNotFoundError:
        raise TermsMissing(
            f"vendor_names: the private term list {path} is missing. It lives outside every git repo ({PRIVATE_ENV} "
            f"names another folder) and is never committed. Without it no public file can be checked, so this stops "
            f"here (fail closed). Put the file back from its private copy, then check it: "
            f"python scripts/vendor_names.py --terms") from None
    except OSError as e:
        raise TermsMissing(f"vendor_names: the private term list {path} cannot be read ({type(e).__name__}); "
                           f"stopping (fail closed)") from None
    terms, files, company, allow, ordinary, tests = [], [], {}, [], [], []
    for n, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("test") and line[4:5] in (" ", "\t", "["):
            try:
                case = json.loads(line[4:])
            except ValueError:
                case = None
            if not (isinstance(case, list) and case and case[0] in _TEST_KINDS and len(case) == _TEST_KINDS[case[0]]
                    and all(isinstance(x, str) for x in case)):
                raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: a test line is "
                                   f"'test [\"scrub\", <in>, <out>]' or 'test [\"pos\" | \"neg\" | \"closed\", "
                                   f"<text>]' (JSON); stopping (fail closed)")
            tests.append(tuple(case))
            continue
        fields = [f.strip() for f in line.split(";")]
        role = fields[0].lower()
        if role not in _ROLES or len(fields) < 2 or not fields[1]:
            raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: not '<kind> ; <spelling>' "
                               f"with a known kind; stopping (fail closed)")
        if role == "file":
            files += [x for x in fields[1].split() if x]
            continue
        if role == "allow":
            allow += [x.lower() for x in fields[1].split() if x]
            continue
        if role == "ordinary":           # review fix round 4: ordinary phrases, "|" between them
            ordinary += [" ".join(x.lower().split()) for x in fields[1].split("|") if x.strip()]
            continue
        if role == "company":
            if len(fields) != 3 or fields[1].lower() not in ("broker", "vendor"):
                raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: a company line is "
                                   f"'company ; broker|vendor ; <legal words>'; stopping (fail closed)")
            company[fields[1].lower()] = fields[2]
            continue
        opts = {"versions": [], "required": False, "hash": "", "say": ""}
        for o in fields[2:]:
            k, _, v = o.partition("=")
            k = k.strip().lower()
            if k == "versions" and v.strip():
                opts["versions"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k == "version-required" and not v:
                opts["required"] = True
            elif k == "hash" and v.strip() in ("optional", "required"):
                opts["hash"] = v.strip()
            elif k == "say" and v.strip():
                opts["say"] = v.strip()
            else:
                raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: unknown option; "
                                   f"stopping (fail closed)")
        parts = [p for p in fields[1].split("|")]
        if any(not p or re.search(r"\s", p) for p in parts):
            raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: an empty part or a space "
                               f"inside a spelling; stopping (fail closed)")
        t = _Term(role, parts, opts["versions"], opts["required"], opts["hash"], opts["say"])
        shortest = len(t.plain) + (min(len(v) for v in t.versions) if t.required and t.versions else 0)
        if shortest < 3:
            raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: a term shorter than 3 "
                               f"characters would block everything; stopping (fail closed)")
        if role == "symbol" and (not t.hash or not t.say):
            raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: a symbol needs hash= and "
                               f"say=; stopping (fail closed)")
        if t.required and not t.versions:
            raise TermsMissing(f"vendor_names: the private term list {path}, line {n}: version-required without "
                               f"versions; stopping (fail closed)")
        terms.append(t)
    for x in files:
        if not re.fullmatch(r"\.[A-Za-z0-9]{2,6}", x):
            raise TermsMissing(f"vendor_names: the private term list {path}: a file kind must be '.ext'; stopping "
                               f"(fail closed)")
    longs = [t.plain.lower() for t in terms if t.role in _LONG]
    for w in allow:
        if not re.fullmatch(r"[a-z0-9]+", w) or not any(x in w and x != w for x in longs):
            raise TermsMissing(f"vendor_names: the private term list {path}: an allow word must be one ordinary word "
                               f"(letters and digits) that holds a long term and more; stopping (fail closed)")
    for ph in ordinary:
        sq = ph.replace(" ", "")
        if not re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)+", ph) or not any(x in sq and x != sq for x in longs):
            raise TermsMissing(f"vendor_names: the private term list {path}: an ordinary phrase must be two or more "
                               f"ordinary words (letters and digits) that hold a long term and more; stopping "
                               f"(fail closed)")
    have = {t.role for t in terms}
    lacking = [r for r in _NEEDED if r not in have]
    if lacking:
        raise TermsMissing(f"vendor_names: the private term list {path} lacks the kind(s) {lacking}: it is empty or "
                           f"broken; stopping (fail closed)")
    return terms, files, company, allow, ordinary, tests


def _body(t, sep, plural=False):
    """The pattern of one term (non-capturing groups only). plural=True: the term in one piece, then 's'."""
    vs = "(?:" + "|".join(re.escape(v) for v in t.versions) + ")" if t.versions else ""
    head = {"optional": "#?", "required": "#"}.get(t.hash, "")
    if plural:
        return head + re.escape(t.plain) + (vs + ("" if t.required else "?") if vs else "") + "s"
    body = head + sep.join(re.escape(p) for p in t.parts)
    if vs:
        body += "(?:" + sep + vs + ")" + ("" if t.required else "?")
    return body


class _Terms:
    """The compiled detector and scrub rules for one term list."""

    def __init__(self, path):
        self.path = path
        if _inside(path, ROOT):
            raise TermsMissing(f"vendor_names: the term list {path} is inside this repo: it must live outside every "
                               f"git repo (it is private); stopping (fail closed)")
        self.terms, self.files, self.company, self.allow, self.ordinary, self.tests = _parse(path)
        with open(path, "rb") as fh:
            self.md5 = hashlib.md5(fh.read()).hexdigest()
        by = {}
        for t in self.terms:
            by.setdefault(t.role, []).append(t)
        self.by = by
        plural_ok = ("broker", "platform", "vendor", "editor", "short", "language")

        def role_pat(role, sep=_SEP, plural=None):
            ts = by.get(role, [])
            if not ts:
                return r"(?!x)x"
            if plural is True:
                return "(?:" + "|".join(_body(t, sep, True) for t in ts) + ")"
            alts = [_body(t, sep) for t in ts]
            if plural is None and role in plural_ok:
                alts += [_body(t, sep, True) for t in ts]
            return "(?:" + "|".join(alts) + ")"
        self.pat = {r: role_pat(r, plural=False) for r in plural_ok + ("symbol",)}
        self.pat_pl = {r: role_pat(r, plural=True) for r in plural_ok}
        ext = ("(?:" + "|".join(re.escape(x) for x in self.files) + ")") if self.files else r"(?!x)x"
        self.pat["file"] = ext
        groups = [f"(?P<{r}>{role_pat(r)})" for r in ("broker", "platform", "vendor", "editor", "short", "language",
                                                          "symbol")]
        self.deny = re.compile(_L + "(?:" + "|".join(groups) + ")" + _R + f"|(?P<file>{ext}){_R}", re.I)
        longs = [f"(?P<{r}>{role_pat(r, _SEP_BIN, False)})" for r in ("broker", "platform", "vendor", "editor",
                                                                         "symbol")]
        self.deny_long = re.compile(_L + "(?:" + "|".join(longs) + ")" + _R, re.I)
        # the second pass (joined forms; see the module docstring)
        jl = [f"(?P<{r}>" + "|".join(re.escape(t.plain) for t in by[r]) + ")" for r in _LONG if by.get(r)]
        self.join_long = re.compile("|".join(jl), re.I)
        # a long term with a separator inside (review fix round 4); binary carriers: one ASCII separator at most
        js = [f"(?P<{r}>" + "|".join(_SEP.join(re.escape(p) for p in t.parts) for t in by[r]) + ")"
              for r in _LONG if by.get(r)]
        jb = [f"(?P<{r}>" + "|".join(_SEP_BIN.join(re.escape(p) for p in t.parts) for t in by[r]) + ")"
              for r in _LONG if by.get(r)]
        self.join_sep = re.compile("|".join(js), re.I)
        # the wide pass (review fix round 5): the broker in its own capitals, case-sensitive (the other long terms are
        # made of ordinary capitalized words, which ordinary text lists with these marks between them)
        wd = [f"(?P<{r}>" + "|".join(_SEPW.join(re.escape(p) for p in t.parts) for t in by[r] if len(t.parts) > 1) + ")"
              for r in ("broker",) if any(len(t.parts) > 1 for t in by.get(r, []))]
        self.wide = re.compile(_L + "(?:" + "|".join(wd) + ")" + _R) if wd else None
        self.join_sep_bin = re.compile("|".join(jb), re.I)
        caps = []
        for r in KINDS:
            if r in _LONG or r in ("file", "symbol"):
                continue
            alts = [_SEP.join(re.escape(p) for p in t.parts) + _SEP + "(?:" +
                    "|".join(re.escape(v) for v in t.versions) + ")" for t in by.get(r, []) if t.versions]
            if alts:
                caps.append(f"(?P<{r}>" + "|".join(alts) + ")")
        bare = [_SEP.join(re.escape(p) for p in t.parts) for t in by.get("symbol", []) if t.hash == "optional"]
        if bare:
            caps.append("(?<!#)(?P<bare>" + "|".join(bare) + ")")      # with its '#' it is the other pass's
        self.join_caps = re.compile(r"(?<![A-Z])(?:" + "|".join(caps) + r")(?![0-9])") if caps else None
        hs = [re.escape(t.plain) for t in by.get("symbol", [])]
        self.join_hash = re.compile(r"#(?:" + "|".join(hs) + r")(?![0-9])", re.I) if hs else None
        self.symbols = [(re.compile(_body(t, _SEP) + r"\Z", re.I), t.say) for t in by.get("symbol", [])]
        self.vendor_full = re.compile(self.pat["vendor"] + r"\Z", re.I)
        # ordinary phrases that hold a long term written with a separator (review fix round 4; see hits())
        self.ordinary_rx = re.compile(_L + "(?:" + "|".join(_SEP.join(re.escape(w) for w in ph.split())
                                                       for ph in self.ordinary) + ")" + _R, re.I) \
            if self.ordinary else None

        def own_pat(role, plural, lower=False):
            """The brand's own spelling of a long term (review fix round 4): the list's spelling in one piece,
            case-sensitive (lower=True: its lower-case form too), then a version (a separator may sit before it)
            or, plural=True, an "s"."""
            alts = []
            for t in by.get(role, []):
                vs = "(?:" + "|".join(re.escape(v) for v in t.versions) + ")" if t.versions else ""
                for sp in ([t.plain, t.plain.lower()] if lower else [t.plain]):
                    one = "(?-i:" + re.escape(sp) + ")"
                    if plural:
                        alts.append(one + (vs + ("" if t.required else "?") if vs else "") + "(?-i:s)")
                    else:
                        alts.append(one + ("(?:" + _SEP + vs + ")" + ("" if t.required else "?") if vs else ""))
            return "(?:" + "|".join(alts) + ")" if alts else r"(?!x)x"
        self.own_any = re.compile("|".join(own_pat(r, pl) for r in _LONG for pl in (False, True)))

        def own_v(role):
            """A short term in the list's own capitals, in one piece, WITH a version (review fix round 5): the only
            form of the scripting language the catch-all rewrites."""
            alts = ["(?-i:" + re.escape(t.plain) + ")(?:" + "|".join(re.escape(v) for v in t.versions) + ")"
                    for t in by.get(role, []) if t.versions]
            return "(?:" + "|".join(alts) + ")" if alts else r"(?!x)x"
        own_x = ("(?-i:" + "|".join(re.escape(x) for x in self.files) + ")") if self.files else r"(?!x)x"
        # the scrub's long terms: the brand's own spelling only (see scrub() in the module docstring)
        sub = {"%B%": own_pat("broker", False), "%Bf%": own_pat("broker", False, lower=True),
               "%Bpl%": own_pat("broker", True), "%P%": own_pat("platform", False),
               "%Ppl%": own_pat("platform", True), "%Q%": own_pat("vendor", False),
               "%E%": own_pat("editor", False), "%Epl%": own_pat("editor", True), "%M%": self.pat["short"],
               "%Lv%": own_v("language"), "%Xo%": own_x, "%SYM%": self.pat["symbol"], "%CO%": _CO}
        self.rules = []
        for p, r, w in RULES:
            for k, v in sub.items():
                p = p.replace(k, v)
            if re.search(r"%[A-Za-z]+%", p):
                raise AssertionError("a rule placeholder was not filled")
            self.rules.append((re.compile(p, re.I | re.S), r, w))

    def _allowed(self, word, s, e):
        """True when the letters-and-digits run `word` (lower case) holds an allow word over [s, e)."""
        return any(0 <= p <= s and p + len(w) >= e for w in self.allow for p in _find_all(word, w))

    def ordinary_at(self, text, m, cache):
        """True when the long-term match `m`, written with a separator inside, lies inside an ordinary phrase of
        the private list (review fix round 4). `cache` (a list) keeps the phrase spans of `text`."""
        if self.ordinary_rx is None or m.lastgroup not in _LONG or m.group(0).isalnum():
            return False
        if not cache:
            cache.append([(x.start(), x.end()) for x in self.ordinary_rx.finditer(text)])
        return any(s <= m.start() and m.end() <= e for s, e in cache[0])

    def joined(self, text, long_only=False):
        """The kinds of term `text` carries in a JOINED form (the second pass; see the module docstring)."""
        out = set()
        for m in self.join_long.finditer(text):
            a, b = m.start(), m.end()
            while a and text[a - 1] in _ALNUM:
                a -= 1
            while b < len(text) and text[b] in _ALNUM:
                b += 1
            word, s, e = text[a:b].lower(), m.start() - a, m.end() - a
            if not self._allowed(word, s, e):
                out.add(KINDS[m.lastgroup])
        # a long term with a separator inside, glued to a digit or at a case change (review fix round 4)
        for m in (self.join_sep_bin if long_only else self.join_sep).finditer(text):
            g = m.group(0)
            if g.isalnum():                  # in one piece: the loop above
                continue
            a, b = m.start(), m.end()
            lft = text[a - 1] if a else ""
            rgt = text[b] if b < len(text) else ""
            if not (lft in _DIGIT and lft or (lft in _LOWER and lft and g[0] in _UPPER) or
                    rgt in _DIGIT and rgt or (rgt in _UPPER and rgt and g[-1] in _LOWER)):
                continue
            while a and text[a - 1] in _ALNUM:
                a -= 1
            while b < len(text) and text[b] in _ALNUM:
                b += 1
            sq = "".join(c for c in g if c in _ALNUM)
            s = m.start() - a
            if not self._allowed((text[a:m.start()] + sq + text[m.end():b]).lower(), s, s + len(sq)):
                out.add(KINDS[m.lastgroup])
        if long_only:
            return out
        if self.join_caps is not None:
            for m in self.join_caps.finditer(text):
                out.add(BARE_SYMBOL if m.lastgroup == "bare" else KINDS[m.lastgroup])
        if self.join_hash is not None and "#" in text:
            if self.join_hash.search(text):
                out.add(KINDS["symbol"])
        return out

    def counts(self):
        out = {}
        for t in self.terms:
            out[t.role] = out.get(t.role, 0) + 1
        if self.files:
            out["file"] = len(self.files)
        if self.allow:
            out["allow"] = len(self.allow)
        if self.ordinary:
            out["ordinary"] = len(self.ordinary)
        return out


def _find_all(word, w):
    p = word.find(w)
    while p >= 0:
        yield p
        p = word.find(w, p + 1)


_CACHE = {}


def _t():
    """The compiled term list (read once per path; TermsMissing when it cannot be used)."""
    p = terms_path()
    t = _CACHE.get(p)
    if t is None:
        t = _CACHE[p] = _Terms(p)
    return t


def __getattr__(name):                   # vendor_names.DENY / DENY_LONG for tools: built from the private list
    if name == "DENY":
        return _t().deny
    if name == "DENY_LONG":
        return _t().deny_long
    raise AttributeError(name)


def _strip_payloads(text):
    return PROTECT.sub(" ", text)


def _decoded(text):
    """`text` as a reader or a browser would see it (entities, invisible characters, %XX and JS escapes)."""
    u = text
    if "&" in u:
        u = html.unescape(u)
    if "%" in u:
        u = unquote(u, errors="replace")
    if "\\" in u:
        u = _JS_ESC.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), u)
        if "&" in u:
            u = html.unescape(u)
    if _INVIS_RE.search(u):
        u = _INVIS_RE.sub("", u)
    if _BLANK_RE.search(u):             # review fix round 5
        u = u.translate(_BLANKS)
    return _NLRUN.sub("\n", u) if _NLRUN.search(u) else u


def _found(rx, text):
    out, T, cache = set(), _t(), []
    if rx is T.deny and T.wide is not None:     # the wide pass rides along with the main detector (round 5)
        for m in T.wide.finditer(text):
            if not T.ordinary_at(text, m, cache):       # the ordinary phrases stay exempt, as in round 4
                out.add(KINDS[m.lastgroup])
    for m in rx.finditer(text):
        if T.ordinary_at(text, m, cache):    # an ordinary phrase, not the brand (review fix round 4)
            continue
        k = KINDS[m.lastgroup]
        if m.lastgroup == "symbol" and not m.group(0).startswith("#"):
            k = BARE_SYMBOL
        out.add(k)
    return out


def hits(text, _depth=0):
    """The kinds of term `text` still carries (sorted), as written, as decoded and in plain letters. Base64 payloads
    are not read as words; a text data: URI is decoded and read, an image data: URI's metadata is read."""
    T = _t()
    if not text:
        return []
    t = _strip_payloads(text)
    found = _found(T.deny, t) | T.joined(t)
    d = _decoded(t)
    if d != t:
        found |= _found(T.deny, d) | T.joined(d)
    if not d.isascii():
        f = _fold(d)
        if f != d:
            found |= _found(T.deny, f) | T.joined(f)
        k = _bare(d)                     # without accents (review fix round 4)
        if k != d and k != f:
            found |= _found(T.deny, k) | T.joined(k)
    if _depth < 3 and "base64," in text:
        for m in _DATA_URI.finditer(text):
            try:
                raw = base64.b64decode(m.group(3) + "=" * (-len(m.group(3)) % 4))
            except (ValueError, TypeError):
                continue
            mt = m.group(1).lower()
            if mt.startswith("text/") or any(k in mt for k in ("xml", "svg", "json", "javascript", "html", "csv")):
                for view in _text_views(raw):
                    found |= set(hits(view, _depth + 1))
            elif mt.startswith("image/"):
                found |= _image_found(raw)
            else:
                lat = raw.decode("latin-1")
                found |= _found(T.deny_long, lat) | T.joined(lat, long_only=True)
    return sorted(found)


def count(text):
    """How many term occurrences `text` carries as written (tools: what a change removes)."""
    return sum(1 for _m in _t().deny.finditer(text or ""))


# ---------------------------------------------------------------------------------------------------------------
# The scrub. Each rule: (pattern template, replacement, wrap). The template's %X% placeholders are filled from the
# private list when it is read (%B% broker, %P% platform, %Q% its vendor, %E% its editor, %M% its short names, %Lv% its
# scripting language in its own capitals with a version, %Xo% its file kinds as the list spells them, %SYM% the
# broker's symbols, *pl the plural in one piece, %CO% company words).
# The long terms (%B%, %P%, %Q%, %E% and their plurals) match the brand's own spelling only; %Bf% (the export file
# and folder rules) also its lower case (review fix round 4).
# A replacement is a template ("\1" groups) or a function of the match. A replacement starts with a capital letter
# only when the original did and it begins a sentence or an element: start of text, after ". " (or "!", "?", a
# line break included), after ">", at a list item, a heading or a new paragraph, after "|" or "**". A line break in
# the middle of a sentence (a wrapped line) is not a sentence start.
# The words written are wrapped in two private-use marks while the rules run (wrap=True), so a last tidy step can fix
# what a replacement does to its neighbours, and only there: "the the" -> "the", "an retail" -> "a retail", a word
# repeated right after the replacement ("export export", "CFD CFDs") once. The marks are removed before scrub()
# returns (a text that already carries one of them is scrubbed without the tidy step).
_START = re.compile(r"(?:\A|[.!?]\s+|>\s*|(?:\A|\n)[ \t]*(?:[-*+>]|\d+[.)]|#{1,6})[ \t]+|\n[ \t]*\n[ \t]*|\|\s*|\*\*)\Z")
_OPEN, _CLOSE = "\ue000", "\ue001"
# company words after a name ("<name> Financial Services Ltd.", "<name> Software Corp.")
_CO = (r"(?:(?:\s+(?:software|financial|services|holdings|group|markets|international|global|systems|technologies))*"
       r"\s+(?:ltd|limited|corp|corporation|inc|plc|llc|gmbh)\b\.?|\s+financial\s+services\b)")


def _with_article(m, noun, adjective):
    """'the' / 'from' / 'a' / 'an' / nothing before the brand -> the same article before a neutral noun. As an
    adjective the noun takes a hyphen ("the retail-broker CSVs"): no apostrophe, so it is safe in any quoting."""
    pre = (m.group(1) or "").strip().lower()
    word = noun.replace(" ", "-") if adjective else noun
    if pre == "from":
        return f"from the {word}"
    if pre in ("a", "an"):
        return f"a {word}"
    return f"the {word}"


def _the_broker(m):
    nxt = m.string[m.end():m.end() + 3].replace(_OPEN, "")
    return "the retail-broker" if re.match(r"\s[A-Za-z]", nxt) else "the retail broker"


def _server(m):
    """A broker or platform-vendor server name -> what it is, without the name ("the live broker trading server")."""
    vendor = bool(_t().vendor_full.match(m.group(1)))
    kind = (m.group(3) or (m.group(2) if m.group(2).lower() in ("demo", "live", "real") else "")).lower()
    kind = {"real": "live"}.get(kind, kind)
    plural = "s" if (m.group(4) or "").lower().endswith("servers") else ""
    if vendor:
        return f"the platform-vendor {kind + ' ' if kind else ''}server{plural}"
    return f"the {kind + ' ' if kind else ''}broker trading server{plural}"


def _site(m):
    """A URL that names a term -> what it points to, never a rewritten (broken) URL."""
    url = m.group(0)
    if not hits(url):
        return url
    return "the retail-broker website" if "broker" in _found(_t().deny, _decoded(url)) else "the platform-vendor website"


def _unwrap_link(m):
    """An HTML link whose attributes name a term -> its text alone (the link is dropped)."""
    return m.group(2) if hits(m.group(1)) else m.group(0)


def _unwrap_md(m):
    return m.group(1) if hits(m.group(2)) else m.group(0)


def _symbol(m):
    for rx, say in _t().symbols:
        if rx.match(m.group(1)):
            return say
    return "the broker index CFD"


def _symbol_etc(m):
    return "(" + _symbol(m) + " etc.)"


RULES = [
    # links first: a link to a named site keeps its text and loses its target (never a rewrite inside the URL)
    (r"<a\b([^>]*)>(.*?)</a>", _unwrap_link, False),
    (r"\[([^\]\n]*)\]\(([^)\s]*)\)", _unwrap_md, False),
    (r"(?:https?://|www\.)[^\s\"'<>()\[\]]+", _site, True),
    # the archived report's reference (Markdown or HTML): same place in the alphabetical list, no name
    (r"%B%\.\s+\((\d{4})\)\.\s+(\*|<em>)%P%\s+historical\s+price\s+data(\*|</em>)\s+\[data\s+set\]\.\s+%B%%CO%",
     r"FX/CFD retail broker. (\1). \2Intraday price history (M5 bars), exported from a retail trading platform\3 "
     r"[Data set].", True),
    # a broker or platform-vendor server name: the name, a dash, a server word
    (_L + r"(%B%|%Q%)(?:\.com)?-(%M%|real|demo|live|server|ecn)[\w.-]*"
     r"(?:\s+(live|demo|real)" + _R + r")?(\s+servers?" + _R + r")?", _server, True),
    # the broker's export files and folder
    (r"(?:<code>|`)?(?:[\w.-]+[\\/]+)*%Bf%_forex_m5[\\/]+%Bf%_m5_(\w+?)\.csv(?:</code>|`)?",
     r"the retail-broker \1 M5 file", True),
    (_L + r"%Bf%_m5_(\w+?)\.csv", r"the retail-broker \1 M5 file", True),
    (_L + r"%Bf%_forex_m5" + _R, "the retail-broker M5 export", True),
    # the broker's own symbols: "(<symbol> etc.)", then each one in its own neutral words
    (r"\((%SYM%) etc\.\)", _symbol_etc, True),
    (_L + r"(%SYM%)" + _R, _symbol, True),
    # the home page's skills list
    (r"\(IBKR,\s*%B%,\s*%M%\)", "(IBKR, retail broker platforms)", True),
    # "<broker> <platform> M5 data"
    (_L + r"%B%\s+%P%" + _R, "retail-broker trading-platform", True),
    # "<broker> M5 ...", "<broker> intraday FX ..." (with or without "the")
    (_L + r"(the\s+)?%B%(?=\s+(?:M5|intraday)" + _R + ")", r"\1retail-broker", True),
    (_L + r"%B%\s+data" + _R, "retail-broker data", True),
    (_L + r"%B%(?=\s+(?:window|metrics)" + _R + ")", "broker-data", True),
    (_L + r"%B%(?=\s+spreads?" + _R + ")", "broker", True),
    # "the <broker> CSVs", "from <broker> <code>Spread</code> column", "(<broker> embedded per-bar spread", ...
    (_L + r"((?:the|from|an?)\s+)?%B%(?=\s+(?:(?:embedded|CSVs?|historical|index|series|feed|quotes?|"
     r"prices?|account|server|terminal|symbols?)" + _R + r"|<code>|`))",
     lambda m: _with_article(m, "retail broker", True), True),
    # catch-all: the broker
    (_L + r"the\s+%B%" + _R, _the_broker, True),
    (_L + r"%B%(?=[_-])", "broker", True),
    (_L + r"%B%%CO%", "a retail broker", True),
    (_L + r"%Bpl%" + _R, "retail brokers", True),
    (_L + r"((?:an?)\s+)?%B%" + _R, lambda m: "a retail broker" if m.group(1) else "the retail broker", True),
    # catch-all: the platform, its vendor, its editor (the short terms below: only their clearly-platform forms)
    (_L + r"%Ppl%" + _R, "retail trading platforms", True),
    (_L + r"((?:the|an?)\s+)?%P%" + _R,
     lambda m: "the trading platform" if (m.group(1) or "").strip().lower() == "the" else "a retail trading platform",
     True),
    (_L + r"((?:the)\s+)?%Q%(?:%CO%|\s+software" + _R + r")?" + _R, "the platform vendor", True),
    (_L + r"%Epl%" + _R, "the platform script editors", True),
    (_L + r"((?:the)\s+)?%E%" + _R, "the platform script editor", True),
    # the short terms (review fix round 5): only the forms that are clearly the platform. The short name has no
    # catch-all (the same letters name other things: a transit line, a CSS class); the phrase and server rules
    # above cover it. The language only in its own capitals with a version (without one, the same letters are
    # ordinary acronyms); a file kind only right after a file name, in the list's own spelling. Every other form
    # is found by hits() and left as it is (fail closed).
    (_L + r"%Lv%" + _R, "trading-platform scripting", True),
    (r"(?<![\w.-])([A-Za-z0-9][\w-]*)%Xo%" + _R, r"\1 (a trading-platform script)", True),
]


def _apply(rx, repl, wrap, seg):
    def sub(m):
        out = repl(m) if callable(repl) else m.expand(repl)
        if out == m.group(0):
            return out
        # the 24 characters before the match; "\x00" in front when they are not the start of the text, so the \A
        # alternatives of _START only ever see the real start
        ctx = ("" if m.start() <= 24 else "\x00") + m.string[max(0, m.start() - 24):m.start()]
        ctx = ctx.replace(_OPEN, "").replace(_CLOSE, "")
        if out and m.group(0)[:1].isupper() and _START.search(ctx):
            out = out[:1].upper() + out[1:]
        return _OPEN + out + _CLOSE if wrap else out
    return rx.sub(sub, seg)


_AN_INITIAL = re.compile(r"[AEFHILMNORSX][A-Z0-9/-]*(?![a-z])")


def _agree(m):
    art, sp, lead, word = m.group(1), m.group(2), m.group(3), m.group(4)
    an = word[:1].lower() in "aeiou" or bool(_AN_INITIAL.match(word))
    new = ("an" if an else "a")
    if art[:1].isupper():
        new = new.capitalize()
    return new + sp + _OPEN + lead + word


def _once(m):
    """The replacement's last word, repeated right after it: once ("export export"); before its own plural, the
    plural alone ("index CFD CFDs" -> "index CFDs")."""
    last, nxt = m.group(1), m.group(3)
    if nxt.lower() == last.lower():
        return last + _CLOSE
    if nxt.lower() == last.lower() + "s":
        return _CLOSE + nxt
    return m.group(0)


def _tidy(seg):
    """Fix what the replacements did to their neighbours, only next to a replacement (see the marks above)."""
    # an article right before a replacement that starts with its own: keep the writer's article, drop ours
    seg = re.sub(r"(?<![A-Za-z])(the|an?|The|An?)(\s+)" + _OPEN + r"(?:the|an?)\s+",
                 lambda m: m.group(1) + m.group(2) + _OPEN, seg)
    # 'a' / 'an' before a replacement: agree with its first word
    seg = re.sub(r"(?<![A-Za-z])(an?|An?)(\s+)" + _OPEN + r"(\W*)(\w[\w/-]*)", _agree, seg)
    # a word the replacement ends with, repeated right after it (or its plural): once
    seg = re.sub(r"(\w+)" + _CLOSE + r"(\s+)(\w+)(?!\w)", _once, seg)
    return seg.replace(_OPEN, "").replace(_CLOSE, "")


_HIDE = re.compile(r"&(?:#\d{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});|" + _INVIS_CLASS)
_TOKEN = re.compile(r"[^\s<>\"'&;]+")


def _unhide(seg, T):
    """A term split by an HTML entity or an invisible character (a soft hyphen, a numeric entity, a zero-width space,
    a bidi control, an nbsp entity next to a space) -> written plainly, so the rules below rewrite it. Only the span
    of such a term changes; every other entity stays as it is. A long term is written plainly only when it then
    reads as the brand's own spelling (the scrub rewrites no other spelling; review fix round 4)."""
    if "&" not in seg and not _INVIS_RE.search(seg):
        return seg
    pieces, pos = [], 0                  # (start, end in seg, the text a browser shows for it)
    for m in _HIDE.finditer(seg):
        if m.start() > pos:
            pieces.append((pos, m.start(), seg[pos:m.start()]))
        pieces.append((m.start(), m.end(), _INVIS_RE.sub("", html.unescape(m.group(0)))))
        pos = m.end()
    pieces.append((pos, len(seg), seg[pos:]))
    offs, n = [], 0
    for _s, _e, txt in pieces:
        offs.append(n)
        n += len(txt)
    plain = "".join(p[2] for p in pieces)

    def orig(i, at_end):
        """The position in seg of plain position i (a decoded entity maps to the whole entity)."""
        for (s, e, txt), o in zip(pieces, offs):
            if o <= i < o + len(txt) or (at_end and o < i <= o + len(txt)):
                if e - s == len(txt) and seg[s:e] == txt:
                    return s + (i - o)
                return e if at_end else s
        return len(seg)
    reps = []
    for m in T.deny.finditer(plain):
        if m.lastgroup in _LONG and not T.own_any.fullmatch(m.group(0)):
            continue
        a, b = orig(m.start(), False), orig(m.end(), True)
        if seg[a:b] != m.group(0):
            reps.append((a, b, html.escape(m.group(0), quote=False)))
    for a, b, new in reversed(reps):
        seg = seg[:a] + new + seg[b:]
    return seg


def _unfold(seg, T):
    """A term written with look-alike or compatibility letters (fullwidth, Cyrillic / Greek look-alikes) -> plain
    letters, so the rules below rewrite it. Only the words that make up such a term are touched."""
    if seg.isascii():
        return seg
    parts, marks, pos, n = [], [], 0, 0
    for m in _TOKEN.finditer(seg):
        gap, tok = seg[pos:m.start()], m.group(0)
        parts.append(gap)
        n += len(gap)
        f = tok if tok.isascii() else _fold(tok)
        if f != tok:
            marks.append((n, n + len(f), tok, len(parts)))
        parts.append(f)
        n += len(f)
        pos = m.end()
    parts.append(seg[pos:])
    if not marks:
        return seg
    spans = [(x.start(), x.end()) for x in T.deny.finditer("".join(parts))]
    for s, e, tok, i in marks:
        if not any(s < xe and xs < e for xs, xe in spans):
            parts[i] = tok
    return "".join(parts)


def scrub(text):
    """`text` with every term of the private list in neutral, true words. Base64 payloads are left as they are."""
    if not text:
        return text
    T = _t()
    if not T.deny.search(text) and not hits(text):
        return text
    marks = _OPEN not in text and _CLOSE not in text
    parts, last = [], 0
    for m in PROTECT.finditer(text):
        parts.append((False, text[last:m.start()]))
        parts.append((True, m.group(0)))
        last = m.end()
    parts.append((False, text[last:]))
    out = []
    for protected, seg in parts:
        if not protected:
            seg = _unfold(_unhide(seg, T), T)
            if T.deny.search(seg):
                for rx, repl, wrap in T.rules:
                    seg = _apply(rx, repl, wrap and marks, seg)
                if marks:
                    seg = _tidy(seg)
        out.append(seg)
    return "".join(out)


def scrub_obj(obj):
    """scrub() on every string value of a JSON-like object (dict keys are not changed)."""
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, list):
        return [scrub_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------------------------------------------
# The file readers.
TEXT_EXT = {".html", ".htm", ".txt", ".css", ".js", ".mjs", ".json", ".xml", ".svg", ".md", ".csv", ".tsv",
            ".yaml", ".yml", ".webmanifest", ".map", ".ics", ""}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".avif", ".bmp"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
OFFICE_EXT = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
ZIP_EXT = OFFICE_EXT | {".zip"}
# a binary file someone read by hand and cleared: md5 -> reason. Empty: nothing like that is published.
DOC_ALLOW = {}
# A public file that carries a term ON PURPOSE: path -> (the line that may carry it, the kinds allowed there, why).
# Any other kind on that line, or a term on any other line of the file, still fails; every scan prints the file as
# KNOWN so it stays in sight. When the file is not public (wave r3s with -UnpublishFxMonthly moves it out of the
# repo and .gitignore keeps it out), the entry matches nothing.
KNOWN = {
    "data/fx_monthly.csv": (1, {BARE_SYMBOL},
                            "its header line; an input of 14_longhistory_regimes.py (13_fx_ingest.py wrote it, "
                            "committed once, 2026-05-19). Allowed while the file is public (wave r3s question)"),
}


def _text_views(b):
    """The text of a file's bytes: UTF-8; UTF-16 or UTF-32 when it has a BOM; both UTF-16 byte orders too when it has
    NULs (the UTF-8 view then reads with the NULs dropped, see _decoded)."""
    if b[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):     # UTF-32 (review fix round 5)
        return [b.decode("utf-32", "replace")]
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return [b.decode("utf-16", "replace")]
    if b[:3] == b"\xef\xbb\xbf":
        b = b[3:]
    views = [b.decode("utf-8", "replace")]
    if b"\x00" in b:
        views += [b.decode("utf-16-le", "replace"), b.decode("utf-16-be", "replace")]
    return views


def _png_meta(b):
    if not b.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    txt, binx, i = [], [], 8
    while i + 8 <= len(b):
        n, typ = struct.unpack(">I4s", b[i:i + 8])
        data = b[i + 8:i + 8 + n]
        if len(data) != n:
            return None
        if typ == b"tEXt":
            txt.append(data.decode("latin-1"))
        elif typ == b"zTXt":
            key, _, rest = data.partition(b"\x00")
            txt.append(key.decode("latin-1") + "\n" + zlib.decompress(rest[1:]).decode("latin-1"))
        elif typ == b"iTXt":
            key, _, rest = data.partition(b"\x00")
            flag, rest = rest[:1], rest[2:]
            lang, _, rest = rest.partition(b"\x00")
            tkey, _, val = rest.partition(b"\x00")
            if flag == b"\x01":
                val = zlib.decompress(val)
            txt.append("\n".join(x.decode("utf-8", "replace") for x in (key, lang, tkey, val)))
        elif typ == b"iCCP":
            name, _, rest = data.partition(b"\x00")
            txt.append(name.decode("latin-1"))
            binx.append(zlib.decompress(rest[1:]))
        elif typ not in (b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"pHYs", b"bKGD",
                         b"sBIT", b"hIST", b"sPLT", b"tIME", b"acTL", b"fcTL", b"fdAT"):
            binx.append(data)
        i += 12 + n
        if typ == b"IEND":
            break
    binx.append(b[i:])
    return "\n".join(txt), b"".join(binx)


def _jpeg_meta(b):
    if not b.startswith(b"\xff\xd8"):
        return None
    txt, binx, i, n = [], [], 2, len(b)
    while i < n:
        j = b.find(b"\xff", i)
        if j < 0 or j + 1 >= n:
            break
        mk = b[j + 1]
        if mk == 0xFF:
            i = j + 1
            continue
        if mk == 0x00 or mk == 0x01 or 0xD0 <= mk <= 0xD7:
            i = j + 2
            continue
        if mk == 0xD9:
            binx.append(b[j + 2:])
            break
        if j + 4 > n:
            return None
        seg = b[j + 4:j + 2 + struct.unpack(">H", b[j + 2:j + 4])[0]]
        if mk == 0xFE or (mk == 0xE1 and seg.startswith(b"http://ns.adobe.com/")):
            txt.append(seg.decode("utf-8", "replace"))
        elif 0xE0 <= mk <= 0xEF:
            binx.append(seg)
        i = j + 4 + len(seg)
    return "\n".join(txt), b"".join(binx)


def _webp_meta(b):
    if not (b[:4] == b"RIFF" and b[8:12] == b"WEBP"):
        return None
    txt, binx, i = [], [], 12
    while i + 8 <= len(b):
        fourcc = b[i:i + 4]
        n = struct.unpack("<I", b[i + 4:i + 8])[0]
        data = b[i + 8:i + 8 + n]
        if len(data) != n:
            return None
        if fourcc == b"XMP ":
            txt.append(data.decode("utf-8", "replace"))
        elif fourcc not in (b"VP8 ", b"VP8L", b"VP8X", b"ALPH", b"ANIM", b"ANMF"):
            binx.append(data)
        i += 8 + n + (n & 1)
    binx.append(b[i:])
    return "\n".join(txt), b"".join(binx)


def _image_found(b):
    """Kinds of term in an image's metadata (text: every term; binary: the long ones). A file that is not a
    well-formed PNG / JPEG / WebP: the long terms in its raw bytes."""
    T = _t()
    long_rx = T.deny_long
    for reader in (_png_meta, _jpeg_meta, _webp_meta):
        try:
            meta = reader(b)
        except (struct.error, zlib.error, ValueError, IndexError):
            meta = None
        if meta is not None:
            txt, binx = meta
            lat = binx.decode("latin-1")
            return set(hits(txt)) | _found(long_rx, lat) | T.joined(lat, long_only=True)
    lat = b.decode("latin-1")
    return _found(long_rx, lat) | T.joined(lat, long_only=True)


def _xls_text(b):
    """The text of every cell and sheet name of an .xls (xlrd), or None when xlrd is not there or cannot read it."""
    try:
        import xlrd
    except ImportError:
        return None
    try:
        book = xlrd.open_workbook(file_contents=b, logfile=io.StringIO(), on_demand=True)
    except Exception:  # noqa: BLE001 -- any reader error: the raw bytes are still read for the long terms
        return None
    parts = [getattr(book, "user_name", "") or ""]
    for k in range(book.nsheets):
        sh = book.sheet_by_index(k)
        parts.append(sh.name)
        for r in range(sh.nrows):
            parts.extend(v for v in sh.row_values(r) if isinstance(v, str) and v)
    return "\n".join(parts)


def _md5(b):
    return hashlib.md5(b).hexdigest()


def _check_bytes(name, b, depth=0):
    """(kind, kinds of term found, problem) for one file's bytes; `name` gives its type. kind: text / office / zip /
    xls / image / skipped / unreadable. problem: None, or why the file cannot be read."""
    long_rx = _t().deny_long
    low = name.lower()
    ext = os.path.splitext(low)[1]
    if ext in FONT_EXT:
        return "skipped", set(), None
    if ext in IMAGE_EXT:
        return "image", _image_found(b), None
    if ext in ZIP_EXT or (ext not in TEXT_EXT and b[:4] == b"PK\x03\x04"):
        if depth > 3:
            return "unreadable", set(), "an archive nested too deep to read"
        try:
            found = set()
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    found |= set(hits(info.filename))
                    data = z.read(info)
                    if info.filename.lower().endswith((".xml", ".rels")):
                        found |= set(hits(re.sub(r"<[^>]+>", " ", data.decode("utf-8", "replace"))))
                    else:
                        k, f, why = _check_bytes(info.filename, data, depth + 1)
                        if why:
                            return "unreadable", set(), f"member {info.filename}: {why}"
                        found |= f
            return ("office" if ext in OFFICE_EXT else "zip"), found, None
        except (zipfile.BadZipFile, zlib.error, OSError, RuntimeError, NotImplementedError) as e:
            return "unreadable", set(), f"a damaged or encrypted archive ({type(e).__name__})"
    if ext == ".gz" or (ext not in TEXT_EXT and b[:2] == b"\x1f\x8b"):
        if depth > 3:
            return "unreadable", set(), "an archive nested too deep to read"
        try:
            inner = gzip.decompress(b)
        except (OSError, EOFError, zlib.error) as e:
            return "unreadable", set(), f"a damaged gzip file ({type(e).__name__})"
        return _check_bytes(name[:-3] if low.endswith(".gz") else name + ".bin", inner, depth + 1)
    if ext == ".xls":
        found = set()
        for raw_view in (b.decode("latin-1"), b.decode("utf-16-le", "replace")):
            found |= _found(long_rx, raw_view) | _t().joined(raw_view, long_only=True)
        cells = _xls_text(b)
        if cells is not None:
            found |= set(hits(cells))
        return "xls", found, None
    if ext not in TEXT_EXT and (ext == ".pdf" or b"\x00" in b[:8192]):
        if _md5(b) in DOC_ALLOW:
            return "skipped", set(), None
        return "unreadable", set(), ("a PDF or binary file the gate cannot read: publish none, or read it by hand "
                                     "and list its md5 in vendor_names.DOC_ALLOW with the reason")
    found = set()
    for view in _text_views(b):
        found |= set(hits(view))
    return "text", found, None


def _where(b, skip=0):
    """The first line numbers of a text file that carry a term (a finding's pointer; never the spelling)."""
    out = []
    for i, line in enumerate(b.decode("utf-8", "replace").split("\n"), 1):
        if i != skip and hits(line):
            out.append(i)
            if len(out) == 5:
                break
    return out


def check_file(path, rel=None):
    """(kind, problem) for one file: kind is text / office / zip / xls / image / skipped / unreadable / known;
    problem is None or a line. `rel` = its path inside the repo (the KNOWN table and the path check use it)."""
    rel = (rel or os.path.basename(path)).replace(os.sep, "/")
    try:
        with open(path, "rb") as fh:
            b = fh.read()
    except OSError as e:
        return "unreadable", f"could not be read ({type(e).__name__}: {e})"
    kind, found, why = _check_bytes(rel, b)
    if why:
        return kind, why
    in_path = set(hits(rel))
    skip = 0                             # a KNOWN line that carries only what it may: not pointed at in a finding
    if rel in KNOWN and kind == "text" and not in_path:
        line_no, allowed, _why = KNOWN[rel]
        lines = b.decode("utf-8", "replace").split("\n")
        here = set(hits(lines[line_no - 1])) if len(lines) >= line_no else set()
        rest = set(hits("\n".join(lines[:line_no - 1] + lines[line_no:])))
        if not rest and here <= allowed:
            return ("known" if here else "text"), None
        found = rest | (here - allowed)
        skip = line_no if here <= allowed else 0
    if in_path:
        return kind, f"its path carries {sorted(in_path)} -- rename it in the generator (scripts/vendor_names.py)"
    if found:
        where = ""
        if kind == "text":
            lines = _where(b, skip)
            where = f" (line {', '.join(map(str, lines))})" if lines else ""
        return kind, f"carries {sorted(found)}{where} -- scrub it in the generator (scripts/vendor_names.py)"
    return kind, None


def public_files(repo, dirs=PUBLIC_DIRS):
    """([relpath], how): what `git add <dirs>` would commit when <repo> is a git work tree (tracked + untracked
    files, minus what .gitignore keeps out: those are never published), else every file under <dirs>."""
    if os.path.exists(os.path.join(repo, ".git")):
        try:
            r = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                                "--", *dirs], capture_output=True, timeout=120)
            if r.returncode == 0:
                rels = sorted({x.decode("utf-8", "surrogateescape") for x in r.stdout.split(b"\x00") if x})
                return [x for x in rels if os.path.isfile(os.path.join(repo, x))], "git-listed"
        except (OSError, subprocess.SubprocessError):
            pass
    rels = []
    for d in dirs:
        for dp, dn, fns in os.walk(os.path.join(repo, d)):
            dn.sort()
            for fn in sorted(fns):
                rels.append(os.path.relpath(os.path.join(dp, fn), repo).replace(os.sep, "/"))
    return rels, "walked"


def scan(repo=None, dirs=PUBLIC_DIRS, notes=None, info=None):
    """[(relpath, problem)] over every public file of <repo> (public_files), plus the counts by kind (numbers only).
    `notes`, when a list, receives (relpath, why) for each KNOWN file; `info`, when a dict, gets "how" (git-listed /
    walked). TermsMissing when the private term list cannot be used."""
    _t()
    repo = repo or ROOT
    out, counts = [], {}
    rels, how = public_files(repo, dirs)
    for rel in rels:
        kind, problem = check_file(os.path.join(repo, rel), rel)
        counts[kind] = counts.get(kind, 0) + 1
        if problem:
            out.append((rel, problem))
        elif kind == "known" and notes is not None:
            notes.append((rel, KNOWN[rel][2]))
    if info is not None:
        info["how"] = how
    return out, counts


def gate_lines(repo=None):
    """The failure lines ds_gate R2 prints (empty = clean)."""
    try:
        bad, _counts = scan(repo)
    except TermsMissing as e:
        return [f"R2 vendor names: {e}"]
    return [f"R2 {rel}: {why}" for rel, why in bad]


# ---------------------------------------------------------------------------------------------------------------
# Self-test. This file spells no term and holds no test text (review fix round 3): the scrub and detector
# cases are the PRIVATE list's "test" lines, written with placeholders ({B}, {P}, ... and their written forms)
# that _placeholders builds from the same list. The other checks below build their cases from the list too.


def _placeholders(T):
    """The test placeholders, filled from the private list (built here, never written in this file)."""
    def one(role, hashed=None):
        ts = [t for t in T.by.get(role, []) if hashed is None or t.hash == hashed]
        if not ts:
            raise TermsMissing(f"vendor_names --selftest: the private term list has no '{role}' term "
                               f"{'(hash=' + hashed + ') ' if hashed else ''}to test with")
        return ts

    def fw(s):
        return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)
    back = {}
    for k, v in _HOMO.items():
        back.setdefault(v, k)

    def cyr(s):
        for i, c in enumerate(s):
            if c in back:
                return s[:i] + back[c] + s[i + 1:]
        return s
    ph = {}
    br = one("broker")[0]
    b = br.plain
    k = max(1, len(br.parts) // 2)
    b1, b2 = "".join(br.parts[:k]), "".join(br.parts[k:])
    co_b = T.company.get("broker", "Holdings Ltd.")
    co_q = T.company.get("vendor", "Holdings Ltd.")
    ph.update({"{B}": b, "{b}": b.lower(), "{B2}": b1 + " " + b2, "{Bx}": " ".join(br.parts),
               "{Bdash}": "-".join(br.parts), "{Bshy}": b1 + "&shy;" + b2,
               "{Bent}": b1 + "&#%d;" % ord(b2[0]) + b2[1:], "{Bzw}": b1 + "\u200b" + b2, "{Bnb}": b1 + "&nbsp;" + b2,
               "{Burl}": "".join("%%%02X" % ord(c) for c in b), "{Bjs}": "\\u%04x" % ord(b[0]) + b[1:],
               "{Bsp2}": b1 + "  " + b2, "{Bnl}": b1 + " \n " + b2, "{Bnbsp}": b1 + "&nbsp; " + b2,
               "{Bndash}": b1 + "\u2013" + b2, "{Bnbh}": b1 + "\u2011" + b2, "{Bslash}": b1 + "/" + b2,
               "{Bmid}": b1 + "\xb7" + b2, "{Bfw}": fw(b), "{Bcyr}": cyr(b), "{Bpl}": b + "s",
               "{Bco}": b + " " + co_b, "{BcoNL}": b + " " + co_b.replace(" ", "\n", 1)})
    # review fix round 5: a control character, a blank-drawn character, two line breaks, a doubled dash, a wide mark
    ph.update({"{Bnul}": b1 + "\x00" + b2, "{Bdel}": b1 + "\x7f" + b2, "{Bc1}": b1 + "\x9b" + b2,
               "{Bbr}": b1 + "\u2800" + b2, "{Bobj}": b1 + "\ufffc" + b2, "{Bnn}": b1 + "\n\n" + b2,
               "{Bdd}": b1 + "--" + b2, "{Bdots}": b1 + ".." + b2, "{Bmix}": b1 + "\u2014\u2013" + b2,
               "{Bcomma}": b1 + ", " + b2, "{Bcolon}": b1 + ":" + b2, "{Bell}": b1 + "\u2026" + b2,
               "{bcomma}": (b1 + ", " + b2).lower(), "{BCOLON}": (b1 + ": " + b2).upper(),
               "{B4d}": b1 + " ---- " + b2})
    pl = one("platform")[0]
    p = pl.plain
    pv = pl.versions[-1] if pl.versions else ""
    ph.update({"{P}": p, "{P2}": " ".join(pl.parts), "{Pcomma}": ", ".join(pl.parts), "{Pdot}": ".".join(pl.parts), "{Pndash}": "\u2013".join(pl.parts),
               "{Pv}": (p + " " + pv).strip(), "{Ppl}": p + "s"})
    q = one("vendor")[0]
    ph.update({"{Q}": q.plain, "{Qdot}": ".".join(q.parts), "{Qco}": q.plain + " " + co_q})
    e = (T.by.get("editor") or [None])[0]
    ph.update({"{E}": e.plain if e else "", "{Epl}": (e.plain + "s") if e else ""})
    sh = one("short")[0]
    m = sh.plain
    v1, v0 = (sh.versions[-1], sh.versions[0]) if sh.versions else ("", "")
    ph.update({"{M}": m, "{m}": m.lower(), "{Mv}": m + v1, "{Mw}": m + v0, "{mv}": (m + v1).lower(),
               "{mw}": (m + v0).lower(), "{Mvsp}": m + " " + v1, "{Mvdash}": m + "-" + v1,
               "{Mvndash}": m + "\u2013" + v1, "{Mvdot}": m + "." + v1, "{mw_}": m.lower() + "_" + v0,
               "{Mwpl}": m + v0 + "s"})
    la = one("language")[0]
    lv1 = la.versions[-1] if la.versions else ""
    lv0 = la.versions[0] if la.versions else ""
    ph.update({"{L}": la.plain, "{l}": la.plain.lower(), "{Lv}": la.plain + lv1, "{Lw}": la.plain + lv0, "{lv}": (la.plain + lv1).lower(),
               "{Lvsp}": la.plain + " " + lv1})
    if T.files:
        ph.update({"{X1}": T.files[0], "{X2}": T.files[-1]})
    for i, t in enumerate(one("symbol", "optional")[:2], 1):
        ph.update({f"{{S{i}}}": "#" + t.plain, f"{{S{i}b}}": t.plain, f"{{S{i}say}}": t.say,
                   f"{{S{i}Say}}": t.say[:1].upper() + t.say[1:]})
    for i, t in enumerate(one("symbol", "required")[:2], 1):
        ph.update({f"{{H{i}}}": "#" + t.plain, f"{{H{i}b}}": t.plain, f"{{H{i}say}}": t.say})
    return ph


def _generated(T):
    """(positives, negatives) built from every term of the private list: each term in many forms, glued to other
    letters or digits where the second pass reads it (review fix round 3), and the near misses that must NOT
    count (a split plural, a term without the version or the '#' it needs, another number, other capitals, an
    allow word)."""
    pos, neg = [], []
    seps = [" ", "  ", "-", "\u2013", "\u2011", ".", "/", "\xb7", "_", "\n", " \u2014 "]
    for t in T.terms:
        if t.role == "company":
            continue
        head = "#" if t.hash else ""
        v = (t.versions[-1] if t.versions else "")
        full = head + t.plain + (v if t.required else "")
        pos += [full, full.lower(), full.upper(), "(" + full + ")", "x " + full + ".", full + "_x",
                "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in full)]
        if len(t.parts) > 1:
            for s in seps:
                pos.append(head + s.join(t.parts) + (s + v if t.required else ""))
            if t.role != "symbol":
                neg.append(" ".join(t.parts) + "s")
        if t.versions:
            for s in (" ", "-", "\u2013", "  "):
                pos.append(head + t.plain + s + v)
        if t.required:
            neg += [head + t.plain, head + t.plain + "".join(t.versions) + "x", head + t.plain + " " + v + "0",
                    head + t.plain + "-" + v + v]
        if t.role in ("broker", "platform", "vendor", "editor", "short", "language"):
            pos.append(full + "s")
        if t.role in _LONG:                       # joined anywhere (unless inside an allow word)
            pos += ["a" + full, full + "ax", full + "0", "2016" + full, "x" + full.lower() + "y",
                    full.upper() + "Z"]
        elif t.role == "symbol":
            pos.append(full + "ax")
            neg.append(full + "0")
            if t.hash == "optional":
                pos += ["a" + t.plain, t.plain + "x"]
                neg += ["A" + t.plain, "a" + t.plain.lower()]
            else:
                pos.append("a" + full)
                neg += [t.plain, t.plain + "Y"]
            neg.append(t.plain[2:])
        else:                                     # glued only with a version, in the list's own capitals
            if t.versions:
                fv = t.plain + v
                pos += ["a" + fv, fv + "Ab", fv + "ax", "9" + fv]
                neg += ["A" + fv, ("a" + fv).lower(), fv + "0"]
            if not t.required:
                neg += ["a" + full, full + "ax", full + "0"]
        # review fix round 4: a character a browser does not draw, or a combining mark, inside the term
        for c in ("\u202a", "\u202e", "\u2066", "\u2069", "\ufe0f", "\ufe00", "\U000e0020", "\U000e0001",
                  "\u180b", "\u17b4", "\U0001d173", "\u206a", "\u3164", "\u115f", "\u0301", "\u0332", "\u0336"):
            pos.append(full[:2] + c + full[2:])
        # review fix round 5: a C0 / C1 control character inside the term (a browser draws nothing or a blank)
        for c in ("\x00", "\x01", "\x08", "\x0e", "\x1b", "\x7f", "\x80", "\x9f"):
            pos.append(full[:2] + c + full[2:])
        # review fix round 5: the Braille blank, the object replacement character, two line breaks, up to three
        # marks; in its own capitals also the wide marks
        if len(t.parts) > 1:
            for s in ("\u2800", "\ufffc", "\ufffd", "\n\n", " \n\n ", "--", "..", " - - ", "/ /", "\xb7-",
                      "\u2014\u2013", " -.- ", "\n--"):
                pos.append(head + s.join(t.parts) + (s + v if t.required else ""))
            if t.role in _LONG:
                k2 = max(1, len(t.parts) // 2)
                q1, q2 = "".join(t.parts[:k2]), "".join(t.parts[k2:])
                neg += [(q1 + ", " + q2).lower(), (q1 + ": " + q2).upper(), q1 + " ---- " + q2]
                if t.role == "broker":
                    for s in (",", ", ", ":", " : ", ";", "+", "|", "~", "'", "*", '"', "=", "!", "@", "#",
                              "\u2026", ",,", ", -"):
                        pos.append(s.join(t.parts))
                else:
                    neg += [", ".join(t.parts), ": ".join(t.parts) + " note", ", ".join(t.parts) + " Joe"]
        # review fix round 4: written with a separator inside and glued on one side
        if t.role in _LONG and len(t.parts) > 1:
            k = max(1, len(t.parts) // 2)
            p1, p2 = "".join(t.parts[:k]), "".join(t.parts[k:])
            for s in (" ", "-", "_", ".", "\u2013"):
                sp = p1 + s + p2
                pos += [sp + "2016", "2016" + sp, sp + "2016 data"]
                if sp[:1].isupper():
                    pos += ["my" + sp, "x" + sp + " data"]
                if sp[-1:].islower():
                    pos.append(sp + "X")
            neg += [(p1 + " " + p2 + "s").lower(), (p1 + " " + p2).upper() + "X", (p1 + " " + p2).lower() + "ing"]
        elif t.role != "symbol" and t.versions:
            for s in (" ", "-"):
                pos.append("aOn" + t.plain + s + v)
            neg.append("A" + t.plain + " " + v)
        elif t.role == "symbol" and t.hash == "optional" and len(t.parts) > 1:
            pos += ["x" + "-".join(t.parts), " ".join(t.parts) + "x"]
            neg.append("A" + " ".join(t.parts))
    for ph in T.ordinary:
        neg += [ph, ph.upper(), ph.replace(" ", "-"), "allocated " + ph + " to each"]
    for x in T.files:
        pos += ["a" + x, "strategy_v2" + x, "the " + x + " file", x.upper()]
        neg += [x[1:], x + "x", "a" + x + "0"]
    for w in T.allow:
        neg += [w, w.upper(), w.capitalize(), "my" + w, w + "s", "(" + w + ")"]
    return pos, neg


def _png(chunks):
    out = b"\x89PNG\r\n\x1a\n"
    for typ, data in [(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00")] + chunks + [(b"IEND", b"")]:
        out += struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def _zip(members):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        for n, d in members:
            z.writestr(n, d)
    return bio.getvalue()


def _file_cases(ph):
    """(label, file name, bytes, expect a term?) for the file readers (in memory)."""
    B, Mv, Pv, P = ph["{B}"], ph["{Mv}"], ph["{Pv}"], ph["{P}"]
    jpeg_com = b"\xff\xd8\xff\xfe" + struct.pack(">H", len(Pv) + 2) + Pv.encode() + b"\xff\xd9"
    jpeg_exif_short = (b"\xff\xd8\xff\xe1" + struct.pack(">H", 2 + 10) + b"Exif\x00\x00" + (" " + Mv.lower())[:4].encode()
                       + b"\xff\xd9")
    xmp = B.encode() + b"   "
    webp = b"RIFF" + struct.pack("<I", 4 + 8 + len(xmp)) + b"WEBP" + b"XMP " + struct.pack("<I", len(xmp)) + xmp
    svg_uri = base64.b64encode(f"<svg><text>{B}</text></svg>".encode()).decode()
    return [
        ("a UTF-16 text file (BOM)", "docs/n.txt", ("\ufeff" + B).encode("utf-16-le"), True),
        ("a UTF-16 text file (no BOM)", "docs/n.txt", B.encode("utf-16-le"), True),
        ("a file whose NAME carries it", f"docs/{B.lower()}_report.html", b"<p>clean</p>", True),
        ("an SVG data: URI with the term in its text", "docs/i.html", f'<img src="data:image/svg+xml;base64,{svg_uri}">'.encode(), True),
        ("a PNG tEXt chunk", "docs/a.png", _png([(b"tEXt", b"Software\x00" + Pv.encode())]), True),
        ("a PNG zTXt chunk", "docs/a.png", _png([(b"zTXt", b"Comment\x00\x00" + zlib.compress(B.encode()))]), True),
        ("a PNG iTXt chunk", "docs/a.png", _png([(b"iTXt", b"Comment\x00\x00\x00en\x00\x00" + B.encode())]), True),
        ("a clean PNG (matplotlib's Software chunk)", "docs/a.png", _png([(b"tEXt", b"Software\x00matplotlib version3.9")]), False),
        ("a JPEG COM segment", "docs/a.jpg", jpeg_com, True),
        ("a JPEG EXIF segment with a short term only (binary: long terms only)", "docs/a.jpg", jpeg_exif_short, False),
        ("a WebP XMP chunk", "docs/a.webp", webp, True),
        ("an .xls whose raw bytes carry the broker", "data/x.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 16 + B.encode() + b"\x00", True),
        ("an .xls whose raw bytes carry a short term by chance (not read as words)", "data/x.xls",
         b"\xd0\xcf\x11\xe0\x00\x07" + Mv.lower().encode() + b"\x00\x09", False),
        ("a .zip with a CSV member naming it", "data/z.zip", _zip([("a.csv", f"x,{B}\n")]), True),
        ("a clean .zip (CSV members)", "data/z.zip", _zip([("a.csv", "x,1\n"), ("b.txt", "ok")]), False),
        ("a .gz naming it", "data/z.csv.gz", gzip.compress(f"{Mv}\n".encode()), True),
        ("a .docx naming it", "data/m.docx", _zip([("word/document.xml", f"<w:t>{P}</w:t>")]), True),
        # review fix round 5: a UTF-8 page with a NUL inside the term; a UTF-32 page (BOM)
        ("a UTF-8 page with a NUL inside the term", "docs/z.html", f"<p>{B[:2]}\x00{B[2:]}</p>".encode(), True),
        ("a UTF-32 page (BOM)", "docs/z.html", ("\ufeff<p>" + B + "</p>").encode("utf-32-le"), True),
        ("a clean UTF-32 page (BOM)", "docs/z.html", "\ufeff<p>clean</p>".encode("utf-32-le"), False),
    ]


def selftest():
    T = _t()
    ph = _placeholders(T)

    def fill(s):
        for k in sorted(ph, key=len, reverse=True):
            s = s.replace(k, ph[k])
        if re.search(r"\{[A-Za-z0-9_]+\}", s):
            raise AssertionError(f"an unfilled placeholder in a test string: {s[:60]!r}")
        return s
    def mask(s):                         # a failure line never shows a spelling: each term becomes <its kind>
        return T.deny.sub(lambda m: "<" + KINDS[m.lastgroup] + ">", _fold(_decoded(s)))
    bad, n = [], 0
    by_kind = {k: [c[1:] for c in T.tests if c[0] == k] for k in _TEST_KINDS}
    for k in _TEST_KINDS:
        n += 1
        if not by_kind[k]:
            bad.append(f"the private term list has no '{k}' test line (the self-test needs them)")
    for i, (src, want) in enumerate(by_kind["scrub"], 1):
        src, want = fill(src), fill(want)
        got = scrub(src)
        n += 4
        if got != want:
            bad.append(f"scrub case {i}: got {mask(got)!r}, want {mask(want)!r}")
        if scrub(got) != got:
            bad.append(f"scrub case {i}: not idempotent")
        if hits(got) or _OPEN in got or _CLOSE in got:
            bad.append(f"scrub case {i}: left {hits(got)} (or a mark) in {mask(got)!r}")
        if got.count("'") > src.count("'") or got.count('"') > src.count('"'):
            bad.append(f"scrub case {i}: wrote a quote mark: {mask(got)!r}")
    gpos, gneg = _generated(T)
    for i, s in enumerate([fill(x) for (x,) in by_kind["pos"]] + gpos):
        n += 1
        if not hits(s):
            bad.append(f"detector missed positive #{i} ({len(s)} characters)")
    for i, s in enumerate([fill(x) for (x,) in by_kind["neg"]] + gneg):
        n += 1
        if hits(s):
            bad.append(f"detector false positive on negative #{i}: {hits(s)}")
    # a joined form: found, and the scrub leaves it found (it does not rewrite it), so the gate fails closed
    for i, (x,) in enumerate(by_kind["closed"], 1):
        s = fill(x)
        n += 1
        got = scrub(s)
        if not hits(s) or not hits(got) or scrub(got) != got:
            bad.append(f"joined form {i}: not found ({hits(s)}), or the scrub hid it from the gate ({hits(got)})")
    n += 1
    pay = fill('x "bdata":"AAA+{Mv}/BBB" y {Lv} z data:image/png;base64,QQ+{Mv}/Rr== w')
    if scrub(pay) != fill('x "bdata":"AAA+{Mv}/BBB" y trading-platform scripting z data:image/png;base64,QQ+{Mv}/Rr== w'):
        bad.append("scrub touched a payload or missed the text")
    n += 1
    k = fill("{B} key")
    obj = {k: [fill("{B} M5"), {"n": 1, "s": fill("{Lv}")}]}
    if scrub_obj(obj) != {k: ["Retail-broker M5", {"n": 1, "s": "Trading-platform scripting"}]}:
        bad.append("scrub_obj: wrong result")
    n += 1
    if any("'" in r or '"' in r for _p, r, _w in RULES if isinstance(r, str)):
        bad.append("a replacement carries a quote mark")
    for label, name, data, expect in _file_cases(ph):
        n += 1
        kind, found, why = _check_bytes(name, data)
        found = found | set(hits(name))
        if why or bool(found) != expect:
            bad.append(f"file reader: {label}: kind {kind}, kinds {sorted(found)}, problem {why}")
    # KNOWN: the allowed kind on the allowed line passes; anywhere else, or another kind there, fails
    import tempfile
    rel = next(iter(KNOWN))
    s1, s2 = ph["{S1b}"].upper(), ph["{S2b}"].upper()
    with tempfile.TemporaryDirectory() as td:
        for label, body, want_kind, want_bad in [
                ("KNOWN header", f"Date,{s1},{s2}_ret\n2020-01-31,1,2\n", "known", False),
                ("KNOWN body", f"Date,{s1}\n2020-01-31,{s2}\n", "text", True),
                ("KNOWN header, another kind", fill("Date,{B}\n2020-01-31,1\n"), "text", True),
                ("KNOWN header, a symbol with its #", f"Date,#{s1}\n2020-01-31,1\n", "text", True),
                ("KNOWN rule on another path", f"Date,{s1}\n", "text", True)]:
            n += 1
            p = os.path.join(td, "f.csv")
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
            kind, why = check_file(p, rel if "another path" not in label else "data/other.csv")
            if bool(why) != want_bad or (not want_bad and kind != want_kind):
                bad.append(f"{label}: kind {kind}, problem {why}")
            # the finding points at the offending line only, never at the allowed header line
            if label == "KNOWN body" and "(line 2)" not in (why or ""):
                bad.append(f"{label}: the finding should point at line 2 only: {why}")
    # every Unicode dash this Python knows is a separator
    n += 1
    pd = [c for c in map(chr, range(0x110000)) if unicodedata.category(c) == "Pd"]
    missing = [f"U+{ord(c):04X}" for c in pd if c not in _DASHES]
    if missing:
        bad.append(f"Unicode dashes not in _DASHES: {missing}")
    # every Unicode format character this Python knows is dropped as invisible (review fix round 4)
    n += 1
    cf = [f"U+{ord(c):04X}" for c in map(chr, range(0x110000))
          if (unicodedata.category(c) == "Cf" or (unicodedata.category(c) == "Cc" and not c.isspace()))
          and not _INVIS_RE.match(c)]
    cf += [f"U+{ord(c):04X} (whitespace)" for c in map(chr, range(0x110000))
           if unicodedata.category(c) == "Cc" and c.isspace() and _INVIS_RE.match(c)]
    if cf:
        bad.append(f"format / control characters not in _IGNORABLE (or whitespace in it): {cf[:20]}")
    # fail closed: no term list -> TermsMissing with a clear message (another folder, read through the same path)
    n += 1
    old = os.environ.get(PRIVATE_ENV)
    with tempfile.TemporaryDirectory() as td:
        os.environ[PRIVATE_ENV] = td
        try:
            hits("x")
            bad.append("no term list: hits() did not stop")
        except TermsMissing as e:
            if "is missing" not in str(e) or "fail closed" not in str(e):
                bad.append(f"no term list: unclear message: {e}")
        finally:
            if old is None:
                os.environ.pop(PRIVATE_ENV, None)
            else:
                os.environ[PRIVATE_ENV] = old
            _CACHE.pop(os.path.abspath(os.path.join(td, TERMS_FILE)), None)
    n += 1
    if not _inside(os.path.join(ROOT, "docs", TERMS_FILE), ROOT) or _inside(T.path, ROOT):
        bad.append("the term list must live outside this repo (it does not, or the check is broken)")
    # this file spells no term: as written, decoded, in plain letters, and with quotes / brackets / '+' removed
    n += 1
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        own = fh.read()
    glued = re.sub(r"[\"'+\[\]()\s\\]", "", own)
    squash = re.sub(r"[^A-Za-z0-9]", "", own).lower()
    long_plain = [t.plain.lower() for t in T.terms if len(t.plain) >= 5]
    own_bad = set(hits(own)) | set(_found(T.deny, glued)) | {"long term in the squashed text" for x in long_plain
                                                               if x in squash}
    if own_bad:
        bad.append(f"this file spells a term: {sorted(own_bad)}")
    for b in bad:
        print("  FAIL", b)
    print(f"VENDOR NAMES SELFTEST: {'PASS' if not bad else 'FAIL'} ({n - len(bad)}/{n}; private term list md5 "
          f"{T.md5[:8]}...)")
    return 1 if bad else 0


def main(argv):
    try:
        if argv[:1] == ["--selftest"]:
            return selftest()
        if argv[:1] == ["--terms"]:
            T = _t()
            c = T.counts()
            print(f"VENDOR TERMS: OK ({T.path}; md5 {T.md5}; " +
                  ", ".join(f"{c.get(r, 0)} {r}" for r in _ROLES if r != "company") +
                  f"; {len(T.tests)} test lines)")
            return 0
        if argv[:1] == ["--scan"]:
            repo = argv[1] if len(argv) > 1 else ROOT
            notes, info = [], {}
            bad, counts = scan(repo, notes=notes, info=info)
            for rel, why in bad:
                print(f"  FAIL {rel}: {why}")
            for rel, why in notes:
                print(f"  KNOWN {rel}: {why}")
            tally = ", ".join(f"{counts.get(k, 0)} {k}" for k in ("text", "office", "zip", "xls", "image", "skipped",
                                                                    "unreadable", "known"))
            print(f"VENDOR NAMES (docs/ + data/, {info.get('how', '?')}: {tally}): "
                  f"{'PASS' if not bad else f'FAIL ({len(bad)})'}")
            return 1 if bad else 0
    except TermsMissing as e:
        print(f"VENDOR NAMES: CANNOT RUN -- {e}")
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
