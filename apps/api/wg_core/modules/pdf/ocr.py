"""Scanned filings without a text layer, read on this machine (RapidOCR, Apache-2.0, ONNX models inside the package —
nothing is sent to any outside service).

The reading process (owner's rules, 2026-10-19):
1. every page is rendered and OCR'd; a page lying sideways or upside down is turned until the text reads best;
2. the form, its state and its printed version are identified BEFORE any box is read; each version has its own reader,
   anchored on the printed labels of that version (no fixed positions shared between versions of the same name);
3. every value keeps its page and region (shown to the owner next to the cell), its confidence and its source;
4. important cells are read a second time from a zoomed crop; a different second reading, a character pair OCR often
   confuses (rn/m, nu/tu, 0/O…) or odd punctuation is flagged for checking — never silently corrected;
5. addresses carry their role on the form. Only the company's own principal office / mailing address fills F–I; a
   registered agent's or "Return to" address is offered as a suggestion for the owner to confirm, never used by itself.
"""
import io
import unicodedata
import re
from dataclasses import dataclass, field as dfield

from .doc_rules import RULES, compare_sources, problems, rule_key
from .fields import field, short_name

DPI = 300  # at 200 dpi the words of the LLC-5 run together ("HOMEAMERICAHOLDINGS"); ~15 s per page on this PC
ZOOM_DPI = 450  # second reading of a single cell
MAX_PAGES = 15
_engine = None


@dataclass
class Box:
    x: float
    y: float
    x2: float
    y2: float
    text: str
    conf: float
    page: int = 0

    @property
    def key(self) -> str:
        return re.sub(r"[^A-Z0-9]", "", self.text.upper())


@dataclass
class Page:
    index: int
    boxes: list[Box]
    w: float
    h: float
    rotation: int = 0  # degrees the rendered page was turned (counter-clockwise) to read upright
    words: str = dfield(default="")

    def region(self, boxes: list[Box]) -> dict | None:
        """Normalised box (0–1) around these boxes on this page, as used by the crop shown to the owner."""
        if not boxes:
            return None
        return {"page": self.index + 1, "rotation": self.rotation,
                "box": [round(min(b.x for b in boxes) / self.w, 4), round(min(b.y for b in boxes) / self.h, 4),
                        round(max(b.x2 for b in boxes) / self.w, 4), round(max(b.y2 for b in boxes) / self.h, 4)]}


PERF_MODES = ("NORMAL", "FAST")  # owner, 2026-10-20: the PC must stay usable (Chrome, Cursor) while OCR runs


def perf_mode() -> str:
    from ...runtime_config import get

    mode = (get("OCR_PERFORMANCE_MODE", "NORMAL") or "NORMAL").strip().upper()
    return mode if mode in PERF_MODES else "NORMAL"


def ocr_workers() -> int:
    """OCR jobs at the same time: 1 (NORMAL), 2 (FAST, only on a PC with 8+ logical cores)."""
    import os

    return 2 if perf_mode() == "FAST" and (os.cpu_count() or 1) >= 8 else 1


def ocr_threads() -> int:
    """CPU threads one OCR run may use: a quarter of the logical cores (1–4) — never all of them."""
    import os

    return max(1, min(4, (os.cpu_count() or 4) // 4))


def _lower_priority():
    """OCR runs below normal priority, so the owner's other programs keep the CPU first (Windows only)."""
    import sys

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL
        except Exception:  # noqa: BLE001 — only a courtesy to the other programs
            pass


_engine_lock = __import__("threading").Lock()


def _ocr():
    global _engine
    with _engine_lock:
        if _engine is None:
            import cv2
            from rapidocr_onnxruntime import RapidOCR

            n = ocr_threads()
            cv2.setNumThreads(n)
            _lower_priority()
            _engine = RapidOCR(intra_op_num_threads=n, inter_op_num_threads=1)
    return _engine


def _read_image(img, page: int) -> list[Box]:
    import numpy as np

    res, _ = _ocr()(np.array(img))
    out = []
    for quad, text, conf in res or []:
        xs, ys = [p[0] for p in quad], [p[1] for p in quad]
        text = unicodedata.normalize("NFKC", text).strip()  # full-width "，" "：" from the CJK-trained model → , :
        if text:
            out.append(Box(min(xs), min(ys), max(xs), max(ys), text, float(conf), page))
    return sorted(out, key=lambda b: (b.y, b.x))


ITEM = re.compile(r"^(\d)(NAME|ADDRESS|IFAN|IFIN|THE|THIS|IDECLARE|ADDITIONAL|INTHE|PURPOSE)")
TOP_WORDS = ("STATEOFCALIFORNIA", "SECRETARYOFSTATE", "ENTITYNAME", "LIMITEDLIABILITYCOMPANY", "FILEDSECRETARYOFSTATE")
FOOT_WORDS = ("APPROVEDBYSECRETARYOFSTATE", "EXECUTION", "TYPEORPRINTNAME", "SIGNATUREOF", "THISDOCUMENTISAPUBLICRECORD")


def _items_upside_down(boxes: list[Box]) -> bool:
    """The numbered items of a form (1. NAME…, 2. …, 3. …) run from top to bottom. The text-line classifier turns
    each line of an upside-down page right way up, so the words read well — but the items then run bottom to top."""
    # what a form prints at its head must sit above what it prints at its foot
    heads = [b.y for b in boxes if b.key.startswith(TOP_WORDS)]
    feet = [b.y for b in boxes if b.key.startswith(FOOT_WORDS)]
    if heads and feet:
        return sorted(heads)[len(heads) // 2] > sorted(feet)[len(feet) // 2]
    items = sorted((int(m.group(1)), b.y) for b in boxes if (m := ITEM.match(b.key)) and len(b.key) >= 12)
    if len(items) < 3:
        return False
    pairs = [(a, b) for i, a in enumerate(items) for b in items[i + 1:] if a[0] != b[0]]
    down = sum(1 for (n1, y1), (n2, y2) in pairs if (n2 > n1) == (y2 > y1))
    return down < len(pairs) / 2


def _score(boxes: list[Box]) -> float:
    return sum(b.conf * len(b.text) for b in boxes if b.conf >= 0.6)


def _upright(img, page: int) -> tuple[list[Box], int, object]:
    """OCR the page; when the text looks sideways (tall boxes) or reads poorly, try the other three orientations."""
    boxes = _read_image(img, page)
    longish = [b for b in boxes if len(b.text) >= 4]
    tall = sum(1 for b in longish if (b.y2 - b.y) > 1.3 * (b.x2 - b.x))
    mean = sum(b.conf for b in longish) / len(longish) if longish else 0
    # upright unless the text lies sideways (tall boxes) or reads as garbage (upside down): trying the other three
    # orientations costs three more OCR passes, so only when there is a sign of it
    if longish and tall <= len(longish) / 2 and mean >= 0.65 and len(longish) >= 5:
        best = (boxes, 0, img)
    else:
        best = (boxes, 0, img)
        for rot in (90, 270, 180):
            turned = img.rotate(rot, expand=True)
            cand = _read_image(turned, page)
            if _score(cand) > _score(best[0]) * 1.15:
                best = (cand, rot, turned)
    if _items_upside_down(best[0]):
        rot = (best[1] + 180) % 360
        turned = img.rotate(rot, expand=True) if rot else img
        best = (_read_image(turned, page), rot, turned)
    return best


def render(data: bytes, page: int, dpi: int, rotation: int = 0):
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        img = pdf.pages[page].to_image(resolution=dpi).original.convert("RGB")
    return img.rotate(rotation, expand=True) if rotation else img


# ───────────────────────── image variants + OCR cache ─────────────────────────

OCR_VERSION = "rapidocr_onnxruntime-1.4.4"
PREPROCESS_VERSION = "pp2"
VARIANTS = ("original", "gray_contrast", "sharpen", "threshold")


def _deskew(g):
    """Small scan tilt (±3°): the angle at which the text rows line up best (row-sum variance of dark pixels)."""
    import numpy as np

    small = g.resize((1000, int(g.height * 1000 / g.width)))
    best, best_score = 0.0, -1.0
    for angle in [a / 4 for a in range(-12, 13)]:
        arr = np.asarray(small.rotate(angle, fillcolor=255)) < 128
        score = float(arr.sum(axis=1).var())
        if score > best_score:
            best, best_score = angle, score
    return g.rotate(best, fillcolor=255, resample=3) if abs(best) >= 0.3 else g


def preprocess(img, variant: str):
    """original | gray_contrast (grayscale, autocontrast, light denoise, deskew) | sharpen (+ light unsharp mask) |
    threshold (+ Otsu binarisation). Never a single hard threshold for every page: each is one candidate among others."""
    if variant == "original":
        return img
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1).filter(ImageFilter.MedianFilter(3))
    g = _deskew(g)
    if variant == "sharpen":
        g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
    elif variant == "threshold":
        arr = np.asarray(g)
        hist = np.bincount(arr.ravel(), minlength=256).astype(float)
        p = hist / hist.sum()
        omega, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
        sigma = (mu[-1] * omega - mu) ** 2 / np.maximum(omega * (1 - omega), 1e-9)
        g = Image.fromarray(np.where(arr > int(np.argmax(sigma)), 255, 0).astype("uint8"))
    return g.convert("RGB")


def _cache_file(sha: str, page: int, variant: str):
    from ...config import settings

    d = settings().data_dir / "ocr_cache" / sha[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sha}-p{page + 1}-{variant}-{OCR_VERSION}-{PREPROCESS_VERSION}-{DPI}dpi.json"


def _page_to_json(p: "Page") -> dict:
    return {"index": p.index, "w": p.w, "h": p.h, "rotation": p.rotation,
            "boxes": [[b.x, b.y, b.x2, b.y2, b.text, b.conf] for b in p.boxes]}


def _page_from_json(d: dict) -> "Page":
    boxes = [Box(x, y, x2, y2, t, c, d["index"]) for x, y, x2, y2, t, c in d["boxes"]]
    return Page(d["index"], boxes, d["w"], d["h"], d["rotation"], " ".join(b.key for b in boxes))


CACHE_STATS = {"hit": 0, "miss": 0}  # pages read from the cache / OCR'd, in this process


def ocr_document(data: bytes, max_pages: int = MAX_PAGES, variant: str = "original", force: bool = False) -> list[Page]:
    """Every page OCR'd at 300 dpi (cached by SHA-256 of the file + page + OCR / preprocessing version + variant;
    force=True re-reads, for debugging). A cached page is never rendered or OCR'd again; a page image is freed as soon
    as its boxes are stored."""
    import gc
    import hashlib
    import json

    import pdfplumber

    sha = hashlib.sha256(data).hexdigest()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        n = min(len(pdf.pages), max_pages)
    pages = []
    for i in range(n):
        cache = _cache_file(sha, i, variant)
        if cache.exists() and not force:
            try:
                pages.append(_page_from_json(json.loads(cache.read_text(encoding="utf-8"))))
                CACHE_STATS["hit"] += 1
                continue
            except (ValueError, KeyError, TypeError):
                pass  # a broken cache file is simply read again
        CACHE_STATS["miss"] += 1
        img = preprocess(render(data, i, DPI), variant)
        boxes, rot, used = _upright(img, i)
        page = Page(i, boxes, used.width, used.height, rot, " ".join(b.key for b in boxes))
        cache.write_text(json.dumps(_page_to_json(page), ensure_ascii=False), encoding="utf-8")
        pages.append(page)
        del img, used, boxes
        gc.collect()
    return pages


def _crop(data: bytes, region: dict, dpi: int):
    """Only the region, rendered at `dpi` (a turned page: the matching part of the unturned page is cut, then turned —
    the whole page is never rendered at 450/600 dpi). Returns (image, full-page height in px, vertical pad)."""
    import pdfplumber

    x0, y0, x1, y1 = region["box"]
    pad_x, pad_y = 0.01, 0.002
    u0, v0, u1, v1 = max(0, x0 - pad_x), max(0, y0 - pad_y), min(1, x1 + pad_x), min(1, y1 + pad_y)
    rot = region.get("rotation", 0) % 360
    # PIL rotate(rot) turns counter-clockwise: map the box on the turned page back to the page as stored
    box = {90: (1 - v1, u0, 1 - v0, u1), 180: (1 - u1, 1 - v1, 1 - u0, 1 - v0), 270: (v0, 1 - u1, v1, 1 - u0)}.get(rot, (u0, v0, u1, v1))
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[region["page"] - 1]
        bx, by = float(page.bbox[0]), float(page.bbox[1])
        w, h = float(page.width), float(page.height)
        crop = page.crop((bx + box[0] * w, by + box[1] * h, bx + box[2] * w, by + box[3] * h)).to_image(resolution=dpi) \
            .original.convert("RGB")
        full_h = (w if rot in (90, 270) else h) * dpi / 72
    if rot:
        crop = crop.rotate(rot, expand=True)
    return crop, full_h, pad_y


def reread_many(data: bytes, region: dict, dpi: int = ZOOM_DPI, variants: tuple = ("original",)) -> list[tuple[str, float]]:
    """Independent readings of one cell: the region rendered once at `dpi`, then each image variant of that small crop
    OCR'd on its own (and freed)."""
    crop, full_h, pad_y = _crop(data, region, dpi)
    out = []
    for v in variants:
        im = preprocess(crop, v)
        boxes = _read_image(im, region["page"] - 1)
        del im
        span_top, span_bot = pad_y * full_h, crop.height - pad_y * full_h
        keep = [b for b in boxes if span_top <= (b.y + b.y2) / 2 <= span_bot]  # not the printed label just above/below
        if not keep:
            out.append(("", 0.0))
            continue
        lines: list[list[Box]] = []
        for b in sorted(keep, key=lambda b: (b.y + b.y2) / 2):
            if lines and abs((lines[-1][0].y + lines[-1][0].y2) / 2 - (b.y + b.y2) / 2) < (b.y2 - b.y) * 0.6:
                lines[-1].append(b)
            else:
                lines.append([b])
        text = " ".join(" ".join(x.text for x in sorted(line, key=lambda b: b.x)) for line in lines)
        # the box rules around a cell come out as lone "I", "1", "|" — not part of the value
        text = " ".join(t for t in text.split() if t not in ("I", "1", "|", "l", "[", "]"))
        out.append((text.strip(), min(b.conf for b in keep)))
    del crop
    return out


def reread(data: bytes, region: dict, dpi: int = ZOOM_DPI, variant: str = "original") -> tuple[str, float]:
    """Second, independent reading of one cell: its region cut out at a higher resolution and OCR'd on its own."""
    return reread_many(data, region, dpi, (variant,))[0]



# ───────────────────────── suspicious readings ─────────────────────────
# Character groups OCR is known to confuse on these scans (seen: "Westboume" for Westbourne, "Fixnure" for Fixture,
# "B0x" for Box, "Group. LLC" for "Group, LLC"). A suspicion is shown to the owner with a suggestion; nothing is changed.

CONFUSIONS = [("m", "rn"), ("rn", "m"), ("nu", "tu"), ("tu", "nu"), ("cl", "d"), ("d", "cl"), ("li", "h"), ("vv", "w"),
              ("rn", "rm"), ("ii", "u"), ("c", "e"), ("e", "c")]  # "Hotcl" for Hotel
# Common words / word endings of US street and company names: a variant that produces one of them, while the reading
# itself does not, is suspicious.
LEXICON = set("""street avenue boulevard road drive lane way court place circle parkway highway suite floor unit building
terrace trail square plaza center centre north south east west holdings holding group house hotel hotels fixture fixtures
films film studio studios media services service consulting partners capital properties property management investments
development construction design international global america american pacific western eastern northern southern
mountain valley ocean bay river lake park garden gardens company corporation limited liability enterprises industries
solutions systems technologies technology products supply trading imports exports foods restaurant market markets realty
estate estates homes home health medical dental care clinic beauty salon auto motors transport logistics energy
""".split())
ENDINGS = ("bourne", "bourn", "burne", "borne", "ture", "tures", "stern", "thorn", "horne", "burn", "corner", "turner",
           "ourne", "ment", "tion", "ston", "field", "wood", "land", "ford", "ville", "ridge", "brook", "burg")


def _confusion(tok: str, low: str) -> dict | None:
    """One swap of a confusable group that turns the word into a common word / word ending."""
    for a, b in CONFUSIONS:
        i = low.find(a)
        while i >= 0:
            variant = low[:i] + b + low[i + len(a):]
            if variant in LEXICON or (variant.endswith(ENDINGS) and not low.endswith(ENDINGS)):
                fixed = tok[:i] + (b.upper() if tok[i:i + len(a)].isupper() else b) + tok[i + len(a):]
                return {"message": f"“{tok}”: OCR hay nhầm “{a}” với “{b}” — có thể là “{fixed}”", "suggestion": fixed}
            i = low.find(a, i + 1)
    return None


def suspects(text: str) -> list[dict]:
    out = []
    for tok in re.findall(r"[A-Za-z0-9.]+", text):
        low = tok.lower().strip(".")
        # a zero among letters / a letter O among digits ("B0x", "P.0.", "2O10")
        whole = lambda fixed: text.replace(tok, fixed, 1)  # noqa: E731  — a suggestion is always the whole cell
        if re.search(r"[a-z]0|0[a-z]|^p\.?0\.?$", low) and not re.fullmatch(r"\d+(st|nd|rd|th)", low):
            out.append({"message": f"“{tok}”: số 0 giữa chữ cái — có thể là chữ O", "suggestion": whole(tok.replace("0", "O"))})
            continue
        if re.search(r"\d[oO]\d|\d[oO]$|^[oO]\d", tok) and re.search(r"\d", tok):
            out.append({"message": f"“{tok}”: chữ O giữa chữ số — có thể là số 0", "suggestion": whole(re.sub(r"[oO]", "0", tok))})
            continue
        if not tok.isalpha() or len(low) < 4 or low in LEXICON:
            continue
        hit = _confusion(tok, low)
        if hit:
            out.append({**hit, "suggestion": whole(hit["suggestion"])})
    for m in re.finditer(r"\b([NSEW])\.(\d)", text):
        out.append({"message": f"“{m.group(0)}”: có thể thiếu khoảng trắng sau “{m.group(1)}.”",
                    "suggestion": text[:m.start()] + f"{m.group(1)}. {m.group(2)}" + text[m.end():]})
    if re.search(r"\w\.\s+(LLC|L\.L\.C|INC|LTD)\b", text, re.I):
        out.append({"message": "Dấu chấm ngay trước hậu tố (LLC/Inc.) — có thể là dấu phẩy",
                    "suggestion": re.sub(r"(\w)\.(\s+(?:LLC|L\.L\.C|INC|LTD)\b)", r"\1,\2", text, flags=re.I)})
    return out


def _same(a: str, b: str) -> bool:
    return re.sub(r"[^A-Za-z0-9]", "", a).lower() == re.sub(r"[^A-Za-z0-9]", "", b).lower()


def _plausible(a: str, b: str) -> bool:
    """A second reading worth comparing: close to the first (a crop that caught the label below is not)."""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.7


def _respace(orig: str, other: str) -> str:
    """orig's own characters and punctuation, with a space wherever `other` (same letters and digits) has one —
    "1000 EastWilliamStreet Suite204" + "1000 East William Street Suite 204"."""
    gaps, n = set(), 0
    for ch in other:
        if ch.isalnum():
            n += 1
        elif ch.isspace():
            gaps.add(n)
    out, n = [], 0
    for ch in orig:
        if ch.isalnum():
            if n in gaps and out and out[-1] != " ":
                out.append(" ")
            n += 1
        out.append(ch)
    return "".join(out)


# ───────────────────────── California ─────────────────────────

SECTIONS = ("MANAGEMENT", "APPOINTMENT", "OFFICEADDRESSES", "ADDITIONALINFORMATION", "EXECUTION", "PURPOSE", "RETURNTO")
PO_BOX = re.compile(r"^P\.?\s*[O0]\.?\s*B[O0]X\b", re.I)
US_STATE_NAMES = {"CALIFORNIA": "CA", "NEVADA": "NV", "DELAWARE": "DE", "WASHINGTON": "WA", "OREGON": "OR", "ARIZONA": "AZ",
                  "TEXAS": "TX", "NEW YORK": "NY", "FLORIDA": "FL", "WYOMING": "WY"}
# Versions whose layout was checked on real scans; anything else is read by its labels but flagged.
VERIFIED = {"LLC-1 REV 03/2005", "LLC-1 REV 04/2007", "LLC-5 REV 04/2007", "LLC-1 REV 01/2013", "LP-1 REV 03/2005",
            "LP-1 REV 01/2008", "LP-1 REV 01/2010", "LP-5 REV 01/2010"}


def _s() -> float:
    """Pixel distances below are measured at 200 dpi."""
    return DPI / 200


def identify(pages: list[Page]) -> dict | None:
    """State, form and printed version, from the words on the page (before any cell is read)."""
    if not pages:
        return None
    p1 = pages[0]
    keys = p1.words
    if "CALIFORNIA" not in keys or "SECRETARYOFSTATE" not in keys:
        return None
    rev = None
    for b in p1.boxes:
        m = re.search(r"(?:LLC|LP)-?\s*([15])\s*[(\[]?\s*REV\.?\s*([0-9OG]{1,2})\s*/\s*(\d{4})", b.text, re.I)
        if m:
            rev = f"REV {m.group(2).upper().replace('O', '0').replace('G', '0').zfill(2)}/{m.group(3)}"
    if "FOREIGNLIMITEDPARTNERSHIP" in keys and ("APPLICATIONFORREGISTRATION" in keys or "LP5" in keys):
        form, layout = "LP-5", "2010"
    elif "CERTIFICATEOFLIMITEDPARTNERSHIP" in keys or ("GENERALPARTNERS" in keys and "PARTNERSHIP" in keys):
        # REV 01/2008 and later: item 2 is the INITIAL DESIGNATED OFFICE in California (no principal office box)
        form, layout = "LP-1", "2008" if re.search(r"INITIALDESIGNAT|DESIGNATE[DO]OFF", keys) else "2005"
    elif "PROPOSEDLLCNAME" in keys or "INITIALSTREETADDRESSOFLLC" in keys:
        form, layout = "LLC-1", "2013+"
    elif "APPLICATIONFORREGISTRATION" in keys or "LLC5" in keys:
        form, layout = "LLC-5", "2007"
    elif "ARTICLESOFORGANIZATION" in keys or "LLC1" in keys:
        form, layout = "LLC-1", "2007"
    else:
        return None
    version = f"{form} {rev}" if rev else f"{form} {layout}"
    return {"state": "CA", "form": form, "layout": layout, "version": version, "verified": version in VERIFIED}


def _label(boxes: list[Box], *keys: str) -> Box | None:
    return next((b for b in boxes if any(k in b.key for k in keys)), None)


def _same_line(boxes: list[Box], ref: Box, *keys: str) -> Box | None:
    return next((b for b in boxes if abs(b.y - ref.y) < 18 * _s() and any(b.key.startswith(k) for k in keys)), None)


HEADERS = ("CITY", "STATE", "ZIPCODE", "ZIP")


def _is_label(b: Box) -> bool:
    """A printed item label ("8 ADDRESS OF THE PRINCIPAL OFFICE…", "5.IF AN INDIVIDUAL…") or a column header."""
    # "35 Corte Madera Avenue" also starts with digits + letters: an item label is long and starts with label words
    item = re.match(r"^\d{1,2}(NAME|ADDRESS|IFAN|IFIN|THE|THIS|IDECLARE|ADDITIONAL|INTHE|PURPOSE)", b.key) and len(b.key) >= 15
    return bool(item) or b.key in HEADERS or b.key.startswith(("CITYANDSTATE", "ZIPCODE")) or b.key.startswith(SECTIONS)


def _below(boxes: list[Box], label: Box, depth: float = 75) -> list[Box]:
    """Values typed under a label line: below it, above the next printed label (never into the next item)."""
    stop = min((b.y for b in boxes if b.y > label.y2 - 4 and b is not label and _is_label(b)
                and abs(b.y - label.y) > 18 * _s()), default=label.y2 + depth * _s())
    end = min(stop, label.y2 + depth * _s())
    # by the middle of the box too: a typed line can overlap the bottom of the header line (a state + ZIP box sitting low)
    return [b for b in boxes if (label.y2 - 4 < b.y or (b.y + b.y2) / 2 > label.y2 + 4) and b.y < end
            and b is not label and not _is_label(b)]


def _above(boxes: list[Box], label: Box, height: float = 70) -> list[Box]:
    """2013+ LLC-1: the typed value sits on the line ABOVE its printed label."""
    return [b for b in boxes if label.y - height * _s() < b.y < label.y - 4 and b.conf >= 0.8]


def _file_number(boxes: list[Box], top: bool = True) -> Box | None:
    """The 12-digit filing number stamped at the top right (or at the bottom of attachment pages)."""
    cands = [b for b in boxes if 11 <= len(re.sub(r"\D", "", b.text)) <= 13 and not re.search(r"[/:]", b.text)]
    if not cands:
        return None
    return min(cands, key=lambda c: c.y) if top else max(cands, key=lambda c: c.y)


def _split_city_state(text: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)[,\s]+([A-Z]{2})[.,!]*$", text.strip())
    return (m.group(1).strip(" ,"), m.group(2)) if m else (text.strip(" ,.!"), "")


def _city_state_zip(text: str) -> tuple[str, str, str]:
    m = re.match(r"^\W*(.*?)[,\s]+([A-Za-z .]+?)\.?,?\s+(\d{5}(?:-\d{4})?)\W*$", text.strip())
    if not m:
        return text.strip(), "", ""
    city, state, zipc = m.group(1).strip(" ,"), m.group(2).strip(" .").upper(), m.group(3)
    return city, US_STATE_NAMES.get(state, state), zipc


@dataclass
class Addr:
    role: str  # principal | mailing | agent | return_to
    label: str  # where on the form, for the owner
    street: str
    city: str
    state: str
    zip: str
    boxes: dict  # part → [Box]
    conf: float


def _address_row(p: Page, head: Box, role: str, label: str, depth: float = 75) -> Addr | None:
    """A row under the CITY / STATE / ZIP CODE headers: street on the left, then the columns of the header line."""
    boxes = p.boxes
    city_h = _same_line(boxes, head, "CITY")
    state_h = _same_line(boxes, head, "STATE")
    zip_h = _same_line(boxes, head, "ZIPCODE", "ZIP")
    vals = _below(boxes, head, depth)
    if not vals:
        return None
    # a typed city can start well left of its header (seen on real scans); the CITY header is sometimes not read
    city_x = city_h.x - 200 * _s() if city_h else p.w * 0.55
    parts: dict[str, list[Box]] = {"street": [], "city": [], "state": [], "zip": []}
    for b in sorted(vals, key=lambda v: v.x):
        if zip_h and b.x >= zip_h.x - 40 * _s():
            parts["zip"].append(b)
        elif state_h and b.x >= state_h.x - 40 * _s() and city_h and not city_h.key.startswith("CITYANDSTATE"):
            parts["state"].append(b)
        elif b.x >= city_x:
            parts["city"].append(b)
        else:
            parts["street"].append(b)
    txt = {k: " ".join(b.text for b in v).strip() for k, v in parts.items()}
    street, city, state, zipc = txt["street"], txt["city"], txt["state"], txt["zip"]
    # "Washington," | "DC 20005" or "Carson City, NV 89701" in one box: read city + state + ZIP together, from the right
    tail = re.sub(r"[!|]", "", " ".join(x for x in (city, state, zipc) if x)).strip()
    m = re.match(r"^(.*?)[,.\s]+([A-Za-z]{2})[.,]?\s+(\d{5}(?:-\d{4})?)$", tail)
    if m and m.group(1).strip(" ,."):
        city, state, zipc = m.group(1).strip(" ,."), m.group(2).upper(), m.group(3)
        parts["state"] = parts["state"] or parts["zip"] or parts["city"]
    elif re.fullmatch(r"[A-Z]{2}", city) and not state:  # the STATE header not read: "CA" landed in the city column
        city, state = "", city
    elif city and not state:
        city, state = _split_city_state(city)
    if not city and "," in street:  # "2340 W 230th Street , Torrance": the city typed in the street box
        street, city = (x.strip() for x in street.rsplit(",", 1))
        parts["city"] = parts["street"]
    if not street.strip(" ,"):
        return None  # left blank on the form (e.g. the agent is a corporation)
    confs = [b.conf for v in parts.values() for b in v]
    return Addr(role, label, street.strip(" ,"), city.strip(" ,.!"), re.sub(r"[^A-Z]", "", state.upper()),
                re.sub(r"[^\d-]", "", zipc), parts, min(confs) if confs else 0.0)


def _return_to(p: Page, label: str = "Mục 8 — Return to") -> tuple[Addr | None, str]:
    """LLC-1 item 8 / LP-1 item 10 "RETURN TO": FIRM … / ADDRESS … / CITY/STATE/ZIP …"""
    boxes = p.boxes
    csz_l = next((b for b in boxes if b.key.startswith("CITYSTATEZIP")), None)
    if not csz_l:
        return None, ""
    # the "ADDRESS" printed just above CITY/STATE/ZIP, in the same column (LP-1 also prints ADDRESS over general partners)
    addr_l = min((b for b in boxes if b.key == "ADDRESS" and b.y < csz_l.y and abs(b.x - csz_l.x) < 60 * _s()),
                 key=lambda b: csz_l.y - b.y, default=None)
    firm_l = next((b for b in boxes if b.key == "FIRM"), None)
    if not addr_l:
        return None, ""
    right = lambda lab: [b for b in boxes if abs(b.y - lab.y) < 18 * _s() and b.x > lab.x2]  # noqa: E731
    sb, cb = right(addr_l), right(csz_l)
    street = " ".join(b.text for b in sb).strip(" [|]")
    glued = re.split(r"ZIP", csz_l.text, maxsplit=1, flags=re.I)[-1] if re.search(r"\d", csz_l.text) else ""
    # a box rule read as "[" / "|" / "L" at either end — never the first letter of the city ("[Los Angeles" → "Los Angeles")
    csz = re.sub(r"^[\s\[|\]]+|[\s\[|\]]+$|(?<=\d)L$", "", glued + " " + " ".join(b.text for b in cb))
    m = re.match(r"^\W*(.*?),?\s+([A-Z]{2})\.?\s+(\d{5}(?:-\d{4})?)\W*$", csz.strip())
    if not street or not m:
        return None, ""
    firm = " ".join(b.text for b in right(firm_l)).strip(" [|]") if firm_l else ""
    cb = cb or [csz_l]
    return Addr("return_to", label, street, m.group(1).strip(" ,"), m.group(2), m.group(3),
                {"street": sb, "city": cb, "state": cb, "zip": cb}, min(b.conf for b in sb + cb)), firm


NAME_TOPS = ("ENTITYNAME", "1NAME", "NAMEOFLIMITE", "NAMEOFUMITE", "NAMEOFTHELIMITED", "NAMEUNDERWHICH", "NANEUNDERWHICH",
             "NAMEOFFOREIGN", "THISSPACEFORFILING")
# the first printed line after item 1 — the name never runs past it
NAME_END = ("2NAMEOFTHEFOREIGN", "NAMEOFTHEFOREIGN", "IFDIFFERENTFROM", "ALTERNATENAME", "PURPOSE", "PLRPOSE", "THEPURPOSEOF",
            "PRINCIPALEXECUTIVEOFFICE", "INITIALDESIGNATED", "DATEANDPLACE", "INITIALAGENT", "AGENTFORSERVICE",
            "OFFICEADDRESSES", "MANAGEMENT")
# printed form text (instructions, section titles) — never a company name, whatever the OCR confidence
BOILERPLATE = (("STATUTE", "PURPOSE"), ("STATEMENTIS", "PURPOSE"), ("THEPURPOSEOF", "PURPOSE"), ("ISTOENGAGE", "PURPOSE"),
               ("LAWFULACT", "PURPOSE"), ("AGENTFORSERVICE", "AGENT"), ("SERVICEOFPROCESS", "AGENT"),
               ("CHECKONLYONE", "MANAGEMENT"), ("EXECUTEDTHISINSTRUMENT", "EXECUTION"), ("ADDITIONALINFORMATION", "ADDITIONAL INFORMATION"),
               ("SIGNATUREOF", "SIGNATURE"), ("RETURNTOENTER", "RETURN TO"), ("ENTERTHENAMESANDADDRESSES", "GENERAL PARTNERS"),
               ("NAMEOF", "nhãn NAME OF"), ("NAMEUNDER", "nhãn NAME UNDER"), ("ABBREVIAT", "hướng dẫn ENTITY NAME"),
               ("RESPECTIVELY", "hướng dẫn ENTITY NAME"), ("PROPOSESTOREGISTER", "nhãn NAME UNDER"),
               ("ENDTHENAME", "hướng dẫn ENTITY NAME"), ("FILINGUSE", "ô dành cho Secretary of State"),
               ("READINSTRUCTIONS", "hướng dẫn"), ("FILINGFEE", "hướng dẫn"), ("IFDIFFERENT", "mục 2"))
SECTION_START = ("PURPOSE", "PLRPOSE", "MANAGEMENT", "EXECUTION", "RETURNTO", "GENERALPARTNERS")


def _boilerplate(b: Box) -> str:
    """Why this box is printed form text and not the company's name ("" = it may be the name)."""
    hit = next((why for k, why in BOILERPLATE if k in b.key), "")
    if not hit and b.key.startswith(SECTION_START) and len(b.key) > 20:
        hit = next(s for s in SECTION_START if b.key.startswith(s)).replace("PLRPOSE", "PURPOSE")
    return hit


def _name_box(p: Page) -> tuple[Box | None, list[dict]]:
    """Item 1: the first typed line under the item-1 label (or the ENTITY NAME instructions when that label was not
    read), above the next item. Lines of printed form text are turned down, with the reason kept for the owner."""
    tops = [b for b in p.boxes if b.key.startswith(NAME_TOPS)]
    rejected: list[dict] = []
    if not tops:
        return None, rejected
    # the lowest label of the item-1 group (ENTITY NAME → 1. NAME OF …), not a later "NAME OF THE FOREIGN …"
    first = min(tops, key=lambda b: b.y)
    group = [b for b in tops if b.y - first.y < 160 * _s() and not b.key.startswith(("NAMEOFTHEFOREIGN", "2NAME"))]
    top = max(group, key=lambda b: b.y)
    end = min((b.y for b in p.boxes if b.y > top.y2 - 4 and b is not top and any(k in b.key for k in NAME_END)
               and not _name_like(b)), default=top.y2 + 160 * _s())
    end = min(end, top.y2 + 160 * _s())
    lines: list[list[Box]] = []
    for b in sorted((b for b in p.boxes if b is not top and (top.y + top.y2) / 2 < b.y < end - 4), key=lambda b: b.y):
        why = _boilerplate(b)
        if why:
            rejected.append({"value": b.text, "role": "entity_name", "reason": f"Không dùng làm tên: trùng phần in sẵn của mẫu ({why})"})
            continue
        if b.conf < 0.72 or len(re.sub(r"[^A-Za-z]", "", b.text)) < 2:
            continue  # a mark, a lone item number, or the mirror image of the instructions
        if lines and abs((lines[-1][0].y + lines[-1][0].y2) / 2 - (b.y + b.y2) / 2) < 20 * _s():
            lines[-1].append(b)
        else:
            lines.append([b])
    if not lines:
        return None, rejected
    line = sorted(lines[0], key=lambda b: b.x)
    name = Box(min(b.x for b in line), min(b.y for b in line), max(b.x2 for b in line), max(b.y2 for b in line),
               " ".join(b.text for b in line), min(b.conf for b in line), p.index)
    for other in lines[1:]:
        rejected.append({"value": " ".join(b.text for b in other), "role": "entity_name",
                         "reason": "Dòng thứ hai trong ô mục 1 — tên lấy dòng đầu ngay dưới nhãn"})
    return name, rejected


def _name_like(b: Box) -> bool:
    """A company name that happens to contain a boundary word ("… MANAGEMENT LLC") is not the next item's label."""
    return bool(re.search(r"\b(LLC|L\.L\.C|LP|L\.P)\b", b.text)) and not _boilerplate(b)


ROLE_LABELS = (  # the printed label above an address row → the role of that address (first match wins)
    # "ADDRESS OF INITIAL DESIGNATED OFFICE IN CALIFORNIA" also contains "OFFICE IN CALIFORNIA": designated comes first
    (("INITIALDESIGNAT", "DESIGNATEDOFFICE", "DESIGNATEOOFFICE"), "designated_office", "Initial Designated Office in California"),
    (("PRINCIPALOFFICEINCALIFORNIA", "OFFICEINCALIFORNIA"), "principal_ca", "văn phòng tại California"),
    (("PRINCIPALEXECUTIVEOFFICE",), "principal", "Principal Executive Office Address"),
    (("ADDRESSOFPRINCIPALOFFICE", "PRINCIPALOFFICE"), "principal", "Address of Principal Office"),
    (("REQUIREDINTHEJURISDICTION", "JURISDICTIONOFFORMATION"), "jurisdiction_office", "văn phòng ở bang thành lập"),
    (("GENERALPARTNER",), "general_partner", "General Partner"),
    (("AGENT",), "agent", "địa chỉ registered agent"),
)


def _role_above(p: Page, head: Box) -> tuple[str, str]:
    """Role of the address row under this header line: the nearest printed label on or above it that names one."""
    near = sorted((b for b in p.boxes if head.y - 260 * _s() < b.y < head.y + 18 * _s() and b.x < p.w * 0.5),
                  key=lambda b: -b.y)
    for b in near:
        for keys, role, label in ROLE_LABELS:
            if any(k in b.key for k in keys):
                item = re.match(r"^(\d{1,2}[AB]?)", b.key)
                return role, (f"Mục {item.group(1).lower()} — " if item else "") + label
    return "", ""


def _read_lp(p1: Page, form: dict) -> tuple[Box | None, list[Addr], list[dict]]:
    """LP-1 (REV 03/2005: item 2 PRINCIPAL EXECUTIVE OFFICE; REV 01/2008 and 01/2010: item 2 INITIAL DESIGNATED OFFICE
    IN CALIFORNIA, no principal office box) and LP-5 (foreign LP: item 3 PRINCIPAL OFFICE). Every row under a
    CITY / STATE / ZIP header takes the role of the label above it; general partners, agents and "Return to" are never
    the company's address."""
    name, rejected = _name_box(p1)
    addrs = []
    for h in (b for b in p1.boxes if b.key.startswith("ZIPCODE") or b.key in ("ZIP", "ZPCODE")):
        role, label = _role_above(p1, h)
        a = _address_row(p1, h, role, label, 40) if role else None
        if a and not re.match(r"see above", a.street, re.I):
            addrs.append(a)
    rt, _ = _return_to(p1, "Mục 10 — Return to")
    if rt:
        addrs.append(rt)
    return name, addrs, rejected


def _read_ca(pages: list[Page], form: dict) -> tuple[Box | None, Box | None, list[Addr], str, list[dict]]:
    """(name box, file-number box, addresses found with their role, note on the form, lines turned down as the name)"""
    p1 = pages[0]
    number = _file_number(p1.boxes)
    addrs: list[Addr] = []
    note = ""
    name_rejected: list[dict] = []
    if form["layout"] == "2013+":
        name_l = _label(p1.boxes, "PROPOSEDLLCNAME")
        name = next((b for b in reversed(_above(p1.boxes, name_l)) if b.x < name_l.x + 600 * _s()), None) if name_l else None
        for key, role, label in (("INITIALSTREETADDRESSOFLLC", "principal", "Mục 3a — Initial Street Address of LLC"),
                                 ("INITIALMAILINGADDRESS", "mailing", "Mục 3b — Initial Mailing Address of LLC"),
                                 ("AGENTSSTREETADDRESS", "agent", "Mục 5b — địa chỉ registered agent")):
            lab = _label(p1.boxes, key)
            if not lab:
                continue
            vals = _above(p1.boxes, lab)
            left = [b for b in vals if b.x < p1.w * 0.55]
            right = [b for b in vals if b.x >= p1.w * 0.55]
            street = re.sub(r"^\W*(?:[③3-5]\s*)?[ab]\.\s*", "", " ".join(b.text for b in left)).strip()
            street = re.sub(r"\s+[ab]\.$", "", street)  # the item letter of the next line read on this one
            city, state, zipc = _city_state_zip(" ".join(b.text for b in right))
            if (not city or re.fullmatch(r"[A-Z]{2}", city)) and "," in street:  # "5051 Santa Fe, Vernon" | "CA 90058"
                street, city = (x.strip() for x in street.rsplit(",", 1))
                if not state and right:
                    m = re.match(r"^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)", " ".join(b.text for b in right))
                    state, zipc = (m.group(1), m.group(2)) if m else (state, zipc)
            if street and not (role == "agent" and street.lower().startswith("b.")):
                addrs.append(Addr(role, label, street, city, state, zipc,
                                  {"street": left, "city": right, "state": right, "zip": right}, min(b.conf for b in vals)))
        return name, number, addrs, note, name_rejected
    if form["form"] in ("LP-1", "LP-5"):
        name, addrs, name_rejected = _read_lp(p1, form)
        return name, number, addrs, note, name_rejected
    heads = [b for b in p1.boxes if b.key.startswith("ZIPCODE") or b.key == "ZIP"]
    name, name_rejected = _name_box(p1)
    if form["form"] == "LLC-5":
        for h in heads:
            if _same_line(p1.boxes, h, "CITYANDSTATE"):
                a = _address_row(p1, h, "principal", "Mục 7 — Address of the principal executive office")
            elif _label([b for b in p1.boxes if abs(b.y - h.y) < 18 * _s()], "PRINCIPALOFFICEINCALIFORNIA", "OFFICEINCALIFORNIA"):
                # a second company address; item 7 stays the one used (owner: never mix items 7 and 8)
                a = _address_row(p1, h, "principal_ca", "Mục 8 — principal office in California")
            else:
                a = _address_row(p1, h, "agent", "Mục 5 — địa chỉ registered agent")
            if a and not re.match(r"see above", a.street, re.I):
                addrs.append(a)
    else:
        if heads:
            a = _address_row(p1, heads[0], "agent", "Mục 4 — địa chỉ registered agent")
            if a:
                addrs.append(a)
        rt, firm = _return_to(p1)
        if rt:
            addrs.append(rt)
            if firm and name and _same(firm, name.text):
                note = f"Mục 8 “Return to” ghi FIRM là chính công ty này ({firm})"
        if not any(a.role in ("principal", "mailing") for a in addrs):
            note = (note + "; " if note else "") + "Mẫu LLC-1 đời 2005–2007 không có ô địa chỉ doanh nghiệp"
    return name, number, addrs, note, name_rejected


MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def _filed(p: Page) -> str:
    """The FILED stamp date ("JUL 08 2010", "OCT 2 9 2009") as MM/DD/YYYY."""
    for b in p.boxes:
        m = re.fullmatch(r"([A-Z]{3})\s*(\d)\s*(\d)?\s*(\d{4})", b.text.strip().upper())
        if m and m.group(1) in MONTHS:
            day = int(m.group(2) + (m.group(3) or ""))
            return f"{MONTHS[m.group(1)]:02d}/{day:02d}/{m.group(4)}"
    return ""


def _formation(p: Page) -> dict:
    """LLC-5 item 3: "THIS FOREIGN LIMITED LIABILITY COMPANY WAS FORMED ON 09 - 14 - 2009 IN NEVADA"."""
    lab = _label(p.boxes, "WASFORMEDON", "3THISFOREIGN")
    if not lab:
        return {}
    line = sorted([b for b in p.boxes if abs((b.y + b.y2) / 2 - (lab.y + lab.y2) / 2) < 22 * _s() and b.x > lab.x2 - 5],
                  key=lambda b: b.x)
    nums = [n for b in line for n in re.findall(r"\d+", b.text)]  # "09 - 14 - 2007" may come as one box
    words = [b.text.strip(" .") for b in line if re.fullmatch(r"[A-Za-z][A-Za-z .]{2,}", b.text.strip()) and b.key not in ("IN", "N")]
    out = {}
    if len(nums) >= 3:
        y = nums[2] if len(nums[2]) == 4 else f"20{nums[2]}" if len(nums[2]) == 2 else nums[2]
        out["formation_date"] = f"{int(nums[0]):02d}/{int(nums[1]):02d}/{y}"
        out["formation_date_note"] = "năm in 2 chữ số trên phôi" if len(nums[2]) == 2 else ""
    if words:
        out["formation_state"] = words[-1]
    return out


def _zoom_between(p: Page, data: bytes | None, top: Box, bottom_y: float) -> tuple[str, float, dict | None]:
    """A line the full-page OCR missed (seen: the agent line of 38776980): read the band between a label and the next
    printed line again, zoomed."""
    if data is None or bottom_y <= top.y2:
        return "", 0.0, None
    region = {"page": p.index + 1, "rotation": p.rotation,
              "box": [round(top.x / p.w, 4), round((top.y2 + 2) / p.h, 4), 0.95, round((bottom_y - 2) / p.h, 4)]}
    text, conf = reread(data, region)
    if not text:
        text, conf = read_band(data, region)
    return text, conf, region


def read_band(data: bytes, region: dict, dpi: int = DPI) -> tuple[str, float]:
    """A wide band with one typed line somewhere in it: the text detector misses such a line among blank space and box
    rules, but reads it when given a strip one line high. Slide a one-line strip down the band, recognise each strip
    on its own, keep the clearest line."""
    import numpy as np

    img = render(data, region["page"] - 1, dpi, region.get("rotation", 0))
    x0, y0, x1, y1 = region["box"]
    band = img.crop((int(x0 * img.width), int(y0 * img.height), int(x1 * img.width), int(y1 * img.height)))
    strip = max(20, int(0.0135 * img.height))  # one typed line on these forms
    best = ("", 0.0, 0.0)
    for top in range(0, max(1, band.height - strip // 2), max(1, strip // 3)):
        piece = band.crop((0, top, band.width, min(band.height, top + strip)))
        res, _ = _ocr()(np.array(piece), use_det=False, use_cls=False)
        for item in res or []:
            text, conf = item[-2], float(item[-1])
            text = text.strip()
            if conf >= 0.9 and len(text) >= 3 and conf * len(text) > best[2]:
                best = (text, conf, conf * len(text))
    return best[0], best[1]


def _agent_name(p: Page, data: bytes | None = None) -> str:
    """Name of the agent for service of process (kept only to tell it apart from the company; never written to the
    Sheet or a website)."""
    lab = _label(p.boxes, "NAMEOFAGENTFORSERVICE", "NAMEOFINITIALAGENT")
    if not lab:
        return ""
    vals = [b for b in _below(p.boxes, lab, 60) if b.conf >= 0.8]
    if vals:
        return " ".join(b.text for b in vals[:2]).strip()
    nxt = min((b.y for b in p.boxes if b.y > lab.y2 + 5 * _s()), default=lab.y2 + 70 * _s())
    return _zoom_between(p, data, lab, nxt)[0]


# ───────────────────────── entity name: signals + independent re-readings ─────────────────────────
# Owner, 2026-10-20: a doubtful name is never "OK". Nothing is corrected from a guess (no "Hom" → "Home", "Ill" → "III"
# rule): a different value is used only when the independent zoomed readings all agree on it.

LEGAL_SUFFIX = re.compile(r"(?<![A-Za-z.])(LLC|L\.L\.C\.?|LP|L\.P\.?)(?![A-Za-z])|LIMITED LIABILITY COMPANY|LIMITED PARTNERSHIP", re.I)
ODD_SUFFIX = re.compile(r"(?<![A-Za-z])(LL\.C|L\.LC|L1C|LIC|LiC|LIc|Lic|LLG|LLO|LLD|L1|LC)(?![A-Za-z])")
GLUED_SUFFIX = re.compile(r"[A-Za-z0-9][.,](LLC|LP|L\.L\.C|L\.P)\b")
NAME_PREFIXES = re.compile(r"^(Mc|Mac|De|Di|Da|Du|La|Le|Van|Von|O)[A-Z][a-z]+$")
NAME_DPI = 600


def _odd_case(word: str) -> bool:
    """HOmA, HoMes, RoD, LiC — not UPPER, lower, Title or a McName."""
    if len(word) < 2 or word.isupper() or word.islower() or (word[0].isupper() and word[1:].islower()):
        return False
    return not NAME_PREFIXES.match(word)


def name_signals(text: str) -> list[tuple[str, str]]:
    """(kind, message) for what makes a company name doubtful. kind: suffix | casing | letters"""
    out = []
    odd = ODD_SUFFIX.search(text)
    if odd:
        out.append(("suffix", f"Hậu tố pháp lý “{odd.group(1)}” không đúng dạng LLC / L.L.C. / LP / L.P. — có thể OCR đọc sai"))
    elif GLUED_SUFFIX.search(text):
        out.append(("suffix", f"Hậu tố dính liền dấu câu “{GLUED_SUFFIX.search(text).group(0)}” — thiếu khoảng trắng hoặc dấu đọc sai"))
    elif not LEGAL_SUFFIX.search(text):
        out.append(("suffix", "Không thấy hậu tố LLC / LP mà mẫu yêu cầu ở cuối tên — có thể đọc thiếu"))
    words = re.findall(r"[A-Za-z]+", text)
    odd_case = [w for w in words if _odd_case(w)]
    if odd_case:
        out.append(("casing", f"Chữ hoa / thường bất thường: {', '.join(odd_case)}"))
    for w in re.findall(r"(?<![A-Za-z0-9])[Il1|]{2,4}(?![A-Za-z0-9])", text):
        if len(set(w)) > 1:
            out.append(("letters", f"“{w}”: I / l / 1 trông giống nhau trên bản scan (III? Ill?)"))
    for w in words:
        low = w.lower()
        if len(low) >= 3 and low not in LEXICON and any(low + c in LEXICON for c in "abcdefghijklmnopqrstuvwxyz"):
            out.append(("letters", f"“{w}”: có thể OCR đọc thiếu một chữ cuối"))
    return out


def _name_region(region: dict) -> dict:
    return {**region, "box": [region["box"][0], region["box"][1], min(0.97, region["box"][2] + 0.05), region["box"][3]]}


def _name_rereads(data: bytes, region: dict) -> list[dict]:
    """Fallback for a doubtful name: the name cell alone rendered once at 600 dpi, each image variant of that small
    crop read on its own (never the whole page)."""
    got = reread_many(data, _name_region(region), dpi=NAME_DPI, variants=VARIANTS)
    return [{"how": f"Vùng tên {NAME_DPI} dpi · ảnh {v}", "variant": v, "dpi": NAME_DPI, "text": t, "confidence": round(c * 100)}
            for v, (t, c) in zip(VARIANTS, got)]


def check_entity(cell: dict, data: bytes | None) -> None:
    """Signals + re-readings on cell A (in place). A second reading at 450 dpi first; only when it differs, the name
    is doubtful or its confidence is low, the 600 dpi readings on every image variant. Disagreeing readings, a doubtful
    legal suffix, I/l/1 or a missing letter → suspects (REVIEW_REQUIRED); odd casing alone lowers the confidence;
    casing with anything else → suspect."""
    value = cell.get("value") or ""
    if not value:
        return
    flags = list(suspects(value))
    reads = [{"how": f"Toàn trang {DPI} dpi", "variant": "original", "dpi": DPI, "text": value, "confidence": cell.get("confidence")}]
    nows = lambda s: re.sub(r"\s+", "", s)  # noqa: E731 — same characters, punctuation and case
    if data is not None and cell.get("region"):
        t450, c450 = reread(data, _name_region(cell["region"]))
        reads.append({"how": f"Vùng tên {ZOOM_DPI} dpi · ảnh original", "variant": "original", "dpi": ZOOM_DPI,
                      "text": t450, "confidence": round(c450 * 100)})
        if t450 and nows(t450) == nows(value) and t450.count(" ") > value.count(" "):
            cell["respaced_from"], value = value, t450  # spaces lost on the full page ("A&B ENTERPRISES,LLC")
        clean = (t450 and nows(t450) == nows(value) and not name_signals(value) and not suspects(value)
                 and (cell.get("confidence") or 0) >= 85)
        if not clean:
            reads += _name_rereads(data, cell["region"])
            others = [r for r in reads[2:] if r["text"] and _plausible(r["text"], value)]
            same = [r for r in reads[1:] if r["text"] and nows(r["text"]) == nows(value)]
            if same:
                spaced = max(same, key=lambda r: r["text"].count(" "))["text"]
                if spaced.count(" ") > value.count(" "):
                    cell["respaced_from"], value = cell.get("respaced_from", value), spaced
            differ = [r for r in others if nows(r["text"]) != nows(value)]
            agreed = {nows(r["text"]) for r in others}
            if differ and len(others) == len(VARIANTS) and len(agreed) == 1 and min(r["confidence"] for r in others) >= 95 \
                    and not [k for k, _ in name_signals(others[0]["text"]) if k != "casing"]:
                # every 600 dpi reading, on every image variant, says the same clearly: that reading is used
                cell["page_reading"] = value
                value = max(others, key=lambda r: r["text"].count(" "))["text"]
                cell["note"] = f"Toàn trang đọc “{cell['page_reading']}”; cả {len(others)} lần đọc phóng to {NAME_DPI} dpi đều ra “{value}”"
                flags = list(suspects(value))
            elif differ and not [r for r in others if nows(r["text"]) == nows(value)] and len(agreed) > 1 \
                    and (cell.get("confidence") or 0) < 90:
                # no zoomed reading repeats the page reading and they disagree among themselves: handwriting or a scan
                # too poor to read — the cell is left empty (never a fragment), the readings are shown as suggestions
                seen = list(dict.fromkeys([value] + [r["text"] for r in differ]))
                cell.update(value="", source="missing", reads=reads, unreadable=seen,
                            note="OCR đọc mỗi lần một khác (có thể viết tay hoặc quá mờ): " + " / ".join(f"“{t}”" for t in seen)
                                 + " — anh nhập tay")
                return
            elif differ:
                seen = list(dict.fromkeys([value] + [r["text"] for r in differ]))
                flags.insert(0, {"message": "Các lần đọc tên khác nhau: " + " / ".join(f"“{t}”" for t in seen),
                                 "suggestion": differ[0]["text"]})
            flags += [f for f in suspects(value) if f not in flags]
    cell["value"] = value
    cell["reads"] = reads
    signals = name_signals(value)
    casing = [m for k, m in signals if k == "casing"]
    flags += [{"message": m, "suggestion": ""} for k, m in signals if k != "casing"]
    if casing:  # alone: a lower confidence (LOW_CONFIDENCE); with any other doubt: a suspect (REVIEW_REQUIRED)
        read_conf = cell.get("confidence") or 0
        cell["confidence"] = max(0, read_conf - 20)
        cell["doubts"] = casing
        if flags or read_conf < 85:
            flags.append({"message": casing[0], "suggestion": ""})
    if flags:
        cell["suspects"] = flags


CITY_RX = re.compile(r"[A-Za-z][A-Za-z .'\-]*")
ZIP_RX = re.compile(r"\d{5}(-\d{4})?")


def _address_doubtful(a: Addr) -> bool:
    return not (ZIP_RX.fullmatch(a.zip or "") and CITY_RX.fullmatch(a.city or "") and re.fullmatch(r"[A-Z]{2}", a.state or ""))


def _retry_address(p: Page, data: bytes, a: Addr) -> list[dict]:
    """The business-address row read again column by column (street | city [| state] | ZIP) at 600 dpi on every image
    variant, when it came out incomplete or invalid ("94ozs", a city in the street box). A part is replaced only when
    all readings agree on a valid value — never from a list of known cities or a guess; otherwise the doubt is kept
    (REVIEW_REQUIRED). Returns the doubts for F."""
    allb = [x for v in a.boxes.values() for x in v]
    top, bot = min(b.y for b in allb), max(b.y2 for b in allb)
    heads = [b for b in p.boxes if top - 140 * _s() < b.y < top]
    city_h = next((b for b in heads if b.key.startswith("CITY")), None)
    zip_h = next((b for b in heads if b.key.startswith(("ZIPCODE", "ZPCODE")) or b.key == "ZIP"), None)
    state_h = next((b for b in heads if b.key.startswith("STATE")), None)
    if not city_h or not zip_h:
        return [{"message": "Địa chỉ đọc không đủ / không hợp lệ và không tìm được cột CITY / ZIP để đọc lại", "suggestion": ""}]
    cx, zx = (city_h.x - 200 * _s()) / p.w, (zip_h.x - 40 * _s()) / p.w
    sx = (state_h.x - 40 * _s()) / p.w if state_h and not city_h.key.startswith("CITYANDSTATE") else None
    cols = {"street": (0.04, cx), "city": (cx, sx or zx), "zip": (zx, 0.97), **({"state": (sx, zx)} if sx else {})}
    # only the parts that are wrong are read again (a city typed into the street box: the street too)
    bad = {"zip"} if not ZIP_RX.fullmatch(a.zip or "") else set()
    if not CITY_RX.fullmatch(a.city or ""):
        bad |= {"city"} | ({"street"} if re.search(r",|\d{3,}\W*$", a.street) else set())
    if not re.fullmatch(r"[A-Z]{2}", a.state or ""):
        bad.add("state" if sx else "city")
    reads: dict[str, list] = {}
    for part in (k for k in cols if k in bad):
        x0, x1 = cols[part]
        reg = {"page": p.index + 1, "rotation": p.rotation,
               "box": [round(x0, 4), round((top - 8 * _s()) / p.h, 4), round(x1, 4), round((bot + 8 * _s()) / p.h, 4)]}
        reads[part] = reread_many(data, reg, dpi=NAME_DPI, variants=VARIANTS)

    def agreed(part: str) -> str:
        got = reads.get(part) or []
        texts = {t.strip(" ,.|[]") for t, _ in got}
        return texts.pop() if len(texts) == 1 and all(t and c >= 0.9 for t, c in got) else ""

    city, state = agreed("city"), agreed("state")
    if city and not sx:  # one CITY AND STATE column
        m = re.match(r"^(.*?)[,.\s]+([A-Z]{2})$", city)
        city, state = (m.group(1).strip(" ,."), m.group(2)) if m else (city, state)
    new = {"street": agreed("street"), "city": city if city and CITY_RX.fullmatch(city) else "",
           "state": state if re.fullmatch(r"[A-Z]{2}", state) else "", "zip": agreed("zip") if ZIP_RX.fullmatch(agreed("zip")) else ""}
    before = (a.street, a.city, a.state, a.zip)
    for part, value in new.items():
        if value:
            setattr(a, part, value)
    a.retry = {part: [{"variant": v, "text": t, "confidence": round(c * 100)} for v, (t, c) in zip(VARIANTS, got)]
               for part, got in reads.items()}
    if _address_doubtful(a) or (a.street, a.city, a.state, a.zip) != before and not all(new[k] for k in reads):
        shown = " · ".join(f"{part}: " + " / ".join(dict.fromkeys(f"“{t}”" for t, _ in got)) for part, got in reads.items())
        return [{"message": f"Địa chỉ đọc lại {NAME_DPI} dpi vẫn chưa thống nhất — {shown}", "suggestion": ""}]
    a.note = f"Đọc lại từng cột {NAME_DPI} dpi trên {len(VARIANTS)} kiểu ảnh: các lần đọc trùng nhau"
    return []


def _cell(page: Page, boxes: list[Box], value: str, conf: float, note: str | None = None, **extra) -> dict:
    f = {**field(value, "ocr", note), "confidence": round(conf * 100), "checked": False}
    if value:
        f["region"] = page.region(boxes)
        f.update({k: v for k, v in extra.items() if v})
    return f


def extract_ca_scan(pages: list[Page], data: bytes | None = None) -> tuple[dict, dict] | None:
    """data (the PDF bytes) enables the zoomed second reading; tests may pass pre-read pages only."""
    form = identify(pages)
    if not form:
        return None
    p1 = pages[0]
    name, number, addrs, note, name_rejected = _read_ca(pages, form)
    name_problem = ""
    if name and len(re.sub(r"\b(LLC|L\.L\.C\.?|LP|L\.P\.?|INC\.?|LTD\.?|CO\.?|COMPANY|LIMITED|LIABILITY|PARTNERSHIP)\b|[^A-Za-z0-9]", "", name.text, flags=re.I)) < 3:
        # only the legal suffix (or a stray letter, "Y") came out: the name is handwritten or unreadable — never fill
        # it with a fragment
        name_problem = f"OCR chỉ đọc được “{name.text}” — tên trên phôi có thể viết tay hoặc quá mờ; anh nhập tay"
        name = None
    business = next((a for a in addrs if a.role == "principal"), None) or next((a for a in addrs if a.role == "mailing"), None)
    candidates = [a for a in addrs if a is not business]

    fields = {
        "A": _cell(p1, [name] if name else [], name.text if name else "", name.conf if name else 0, name_problem or None),
        "D": field("", "missing", f"Mẫu {form['form']} không có ô số điện thoại — để trống"),
        "J": _cell(p1, [number] if number else [], re.sub(r"\D", "", number.text) if number else "", number.conf if number else 0,
                   "File # góc trên bên phải"),
    }
    for a in candidates:  # suggested addresses: fix only run-together words (same characters, more spaces)
        if data is not None and a.boxes["street"]:
            text, _ = reread(data, p1.region(a.boxes["street"]))
            if text and _same(text, a.street):
                a.street = _respace(a.street, text)
    street_flags = []
    if business and data is not None and business.boxes["street"]:
        # second reading of the street from a zoomed crop: words that ran together ("EastWilliamStreet") come apart;
        # only spaces are taken from it — the characters and punctuation stay those of the first reading
        text, _ = reread(data, p1.region(business.boxes["street"]))
        if text and _same(text, business.street):
            business.street = _respace(business.street, text)
        elif text and _plausible(text, business.street):
            street_flags.append({"message": f"Hai lần đọc tên đường khác nhau: “{business.street}” / “{text}”", "suggestion": ""})
    if business and data is not None and _address_doubtful(business):
        street_flags += _retry_address(p1, data, business)
    if business:
        b = business
        fields["F"] = _cell(p1, [x for v in b.boxes.values() for x in v],
                            ", ".join(x for x in (b.street, b.city, f"{b.state} {b.zip}".strip()) if x), b.conf, b.label, role=b.role,
                            street=b.street, address_retry=getattr(b, "retry", None), retry_note=getattr(b, "note", None))
        fields["G"] = _cell(p1, b.boxes["city"], b.city, b.conf, role=b.role)
        fields["H"] = _cell(p1, b.boxes["state"] or b.boxes["city"], b.state, b.conf, role=b.role)
        fields["I"] = _cell(p1, b.boxes["zip"], b.zip, b.conf, role=b.role)
        if PO_BOX.match(b.street):
            fields["F"]["warning"] = "Địa chỉ là hộp thư P.O. Box, không phải địa chỉ nhà"
    else:
        why = "Phôi không có địa chỉ doanh nghiệp (trụ sở / nhận thư) — xem địa chỉ gợi ý, anh xác nhận"
        for k in "FGHI":
            fields[k] = field("", "missing", why)
    # zoomed second reading of the important cells + characters OCR often confuses
    for k in ("A", "J", "F", "G"):
        f = fields[k]
        if not f.get("value") or "region" not in f:
            continue
        flags = (suspects(f["value"]) if k != "J" else []) + (street_flags if k == "F" else [])
        # (J is not re-read from a crop: its widely spaced typewriter digits break apart there — it is checked by its
        # digit count and against the copy stamped on later pages instead)
        if k == "A":
            check_entity(f, data)  # signals + independent zoomed readings; sets its own suspects
            continue
        if flags:
            f["suspects"] = flags
    if fields["J"].get("value"):
        j = fields["J"]
        if len(j["value"]) != 12:
            j.setdefault("suspects", []).append({"message": f"Mã số có {len(j['value'])} chữ số (mẫu CA có 12)", "suggestion": ""})
        later = [b for b in (_file_number(p.boxes, top=False) for p in pages[1:]) if b]
        other = re.sub(r"\D", "", later[0].text) if later else ""
        j["check"] = {"other": other, "match": other == j["value"]} if other else {"other": "", "match": None}
    fields["E"] = field(short_name(fields["A"]["value"]), "auto", "Tự sinh từ A")  # after check_entity
    extra = {
        "form": form["form"], "layout": form["layout"], "version": form["version"], "state_of_form": form["state"],
        "labels_found": {k: any(w in p1.words for w in keys) for k, keys in LABEL_KEYS.items()},
        "version_verified": form["verified"], "reader": "OCR trên máy (RapidOCR, không gửi ra ngoài)",
        "pages_read": len(pages), "rotations": [p.rotation for p in pages],
        "address_source": business.label if business else "",
        "address_candidates": [{"role": a.role, "label": a.label, "street": a.street, "city": a.city, "state": a.state,
                                "zip": a.zip, "confidence": round(a.conf * 100),
                                "region": p1.region([x for v in a.boxes.values() for x in v]),
                                "suspects": suspects(f"{a.street}, {a.city}")} for a in candidates],
        "filed_date": _filed(p1),
        "agent_name": _agent_name(p1, data),  # internal only: tells the agent apart from the company
        "entity_rejected": name_rejected,
    }
    if form["form"] == "LLC-5":
        extra.update({k: v for k, v in _formation(p1).items() if v})
    for a in extra["address_candidates"]:
        if not a["suspects"]:
            del a["suspects"]
    if note:
        extra["note"] = note
    if not form["verified"]:
        extra["warning"] = f"Phiên bản biểu mẫu {form['version']} chưa được kiểm chứng trên phôi thật — đối chiếu kỹ từng ô"
        # a printed version never checked on a real scan may have another layout → never OK without a look (when only
        # the REV line was not read, the layout is the known one of that form)
        extra["unverified_version"] = "REV" in form["version"]
    # what was chosen for F–I and why; what was turned down and why (shown to the owner, never written to F–I)
    if business:
        extra["address_selected"] = {"text": fields["F"]["value"], "label": business.label, "role": business.role,
                                     "reason": f"Nằm trong ô “{business.label}”", "confidence": round(business.conf * 100)}
    for c in extra["address_candidates"]:
        c["reason"] = f"Nằm trong ô “{c['label']}” — {REJECTED.get(c['role'], 'không phải địa chỉ doanh nghiệp')}"
    extra.update(scan_status(fields, extra))
    return fields, extra


REJECTED = {
    "agent": "địa chỉ của registered agent, không phải địa chỉ doanh nghiệp",
    "return_to": "địa chỉ “Return to” (người nhận lại hồ sơ), không phải địa chỉ doanh nghiệp",
    "principal_ca": "văn phòng tại California (mục 8) — không thay địa chỉ trụ sở chính mục 7",
    "mailing": "địa chỉ nhận thư — đã có địa chỉ trụ sở chính",
    "general_partner": "địa chỉ của general partner, không phải địa chỉ doanh nghiệp",
    "designated_office": "văn phòng chỉ định tại California theo luật LP (không nhất thiết là nơi kinh doanh) — mẫu này "
                         "không có ô Principal Executive Office; anh xác nhận nếu muốn dùng",
    "jurisdiction_office": "văn phòng bắt buộc ở bang thành lập — không phải ô Principal Office",
    "organizer": "địa chỉ người lập hồ sơ, không phải địa chỉ doanh nghiệp",
}


LABEL_KEYS = {"A": ("PROPOSEDLLCNAME", "ENTITYNAME", "1NAME", "NAMEOFLIMITE", "NAMEUNDERWHICH", "NAMEOFFOREIGN"),
              "F": ("INITIALSTREETADDRESSOFLLC", "PRINCIPALEXECUTIVEOFFICE", "ADDRESSOFPRINCIPALOFFICE")}
FINAL = ("OK", "NO_BUSINESS_ADDRESS_ON_FORM")  # no other image variant is tried after these


def scan_status(fields: dict, extra: dict) -> dict:
    """status ∈ OK | NO_BUSINESS_ADDRESS_ON_FORM | LOW_CONFIDENCE | REVIEW_REQUIRED + extraction_reason, and for a
    reading that is not usable the failure_category of the dry run (internal: the Sheet columns do not change).
    What is required depends on the form (doc_rules.RULES), not a fixed list."""
    v = lambda k: (fields.get(k) or {}).get("value", "")  # noqa: E731
    key = rule_key("ca", {"form": extra.get("form"), "layout": extra.get("layout")})
    has_address = RULES.get(key, {}).get("has_address")
    labels = extra.get("labels_found") or {}

    def review(reason: str, category: str) -> dict:
        return {"status": "REVIEW_REQUIRED", "extraction_reason": reason, "failure_category": category}

    if extra.get("variant_conflicts"):
        c = extra["variant_conflicts"]
        return review("Ảnh gốc và ảnh xử lý đọc khác nhau: " + "; ".join(f"{x['field']}: “{x['original']}” / “{x['variant']}”" for x in c),
                      "các lần đọc OCR mâu thuẫn")
    if extra.get("source_conflicts"):
        c = extra["source_conflicts"]
        return review("Lớp chữ PDF và OCR đọc khác nhau: " + "; ".join(f"{x['field']}: “{x['text']}” / “{x['ocr']}”" for x in c),
                      "lớp chữ và OCR mâu thuẫn")
    probs = problems(key, fields)
    if probs:
        miss_a = not v("A")
        addr = any(p.startswith(("G ", "H ", "I ", "Địa chỉ")) for p in probs)
        cat = ("không tìm được label" if miss_a and not labels.get("A", True) else
               "đọc được label nhưng không đọc được value" if miss_a else
               "parser address thất bại" if addr else "đọc được label nhưng không đọc được value")
        return review("; ".join(probs), cat)
    if extra.get("unverified_version"):
        return review(f"Phiên bản {extra.get('version')} chưa kiểm chứng trên phôi thật — bố cục có thể khác, cần xem từng ô",
                      "phiên bản mẫu chưa kiểm chứng")
    doubts = [k for k in ("A", "J", "F", "G", "H", "I") if (fields.get(k) or {}).get("suspects") and (fields.get(k) or {}).get("source") != "manual"]
    if doubts:
        k = doubts[0]
        return review(f"Ô {k} có nhiều cách đọc: {fields[k]['suspects'][0]['message']}", "OCR đọc không chắc (cần xem)")
    sel = extra.get("address_selected") or {}
    low = [k for k in ("A", "J", "F") if (fields.get(k) or {}).get("source") in ("ocr", "ai") and (fields[k].get("confidence") or 100) < 85]
    if low:
        return {"status": "LOW_CONFIDENCE", "extraction_reason": f"Độ tin cậy OCR thấp ở {', '.join(low)} — đối chiếu ảnh",
                "failure_category": "OCR đọc không chắc (cần xem)"}
    if not v("F"):
        seen = ", ".join(sorted({c["label"] for c in extra.get("address_candidates", [])})) or "không có địa chỉ nào khác"
        if has_address:
            found = labels.get("F", True)
            return review(f"{extra.get('version')} có ô địa chỉ doanh nghiệp nhưng không đọc được (trên phôi đọc được: {seen})",
                          "đọc được label nhưng không đọc được value" if found else "không tìm được label")
        return {"status": "NO_BUSINESS_ADDRESS_ON_FORM",
                "extraction_reason": f"{extra.get('version', 'Phôi')} không có ô trụ sở / địa chỉ doanh nghiệp (trên phôi chỉ có: {seen})"}
    return {"status": "OK", "extraction_reason": f"Địa chỉ lấy từ ô “{sel.get('label', '?')}”"}


def _field_score(fields: dict) -> tuple:
    """A candidate reading is better when the cells that matter are there and look right — not by OCR confidence alone."""
    v = lambda k: (fields.get(k) or {}).get("value", "")  # noqa: E731
    good_j = bool(re.fullmatch(r"\d{12}", v("J")))
    good_addr = bool(v("F") and re.search(r"\d", v("F")) and v("G") and re.fullmatch(r"[A-Z]{2}", v("H") or "") and re.fullmatch(r"\d{5}(-\d{4})?", v("I") or ""))
    doubts = sum(1 for k in "AJFG" if (fields.get(k) or {}).get("suspects"))
    conf = sum((fields.get(k) or {}).get("confidence") or 0 for k in "AJF")
    return (bool(v("A")), good_j, good_addr, -doubts, conf)


DEBUG_FIELDS = {"entity_name": ("A", None), "file_number": ("J", None), "business_street": ("F", "street"),
                "business_city": ("G", None), "business_state": ("H", None), "business_zip": ("I", None)}


def scan_report(fields: dict | None, extra: dict) -> dict:
    """The reading laid out for review / the dry run: every value with its source, confidence, page and box; the
    address chosen for F–I and every address turned down, each with its role and the reason."""
    fields = fields or {}
    out = {}
    for name, (k, part) in DEBUG_FIELDS.items():
        f = fields.get(k) or {}
        region = f.get("region") or {}
        out[name] = {"value": (f.get(part) if part else f.get("value")) or "", "source": f.get("source", "missing"),
                     "confidence": f.get("confidence"), "bbox": region.get("box"), "page": region.get("page")}
        if f.get("readings"):
            out[name]["readings"] = f["readings"]
    sel = extra.get("address_selected")
    return {
        "document_type": extra.get("version") or extra.get("form") or "",
        "entity_name": out["entity_name"]["value"],
        "business_address": (fields.get("F") or {}).get("value", ""),
        "file_number": out["file_number"]["value"],
        "status": extra.get("status"), "reason": extra.get("extraction_reason"),
        "failure_category": extra.get("failure_category"),
        "selected_candidates": [{"value": sel["text"], "role": sel["role"], "reason": sel["reason"]}] if sel else [],
        "rejected_candidates": [{"value": ", ".join(x for x in (c["street"], c["city"], f"{c['state']} {c['zip']}".strip()) if x),
                                 "role": c["role"], "reason": c["reason"]} for c in extra.get("address_candidates", [])],
        "fields": out,
    }


def read_scan(data: bytes, force: bool = False) -> dict:
    """The whole scan reading: OCR every page at 300 dpi, original image (cached) → identify the form → read its boxes;
    doubtful cells are re-read on their own small crop (450 dpi, then 600 dpi × image variants). Returns scan_report(…) plus "sheet": (fields, extra) for the app, or None when nothing could be read
    (status OCR_FAILED | UNKNOWN_DOCUMENT)."""
    pages = ocr_document(data, force=force)
    if not any(p.boxes for p in pages):
        extra = {"status": "OCR_FAILED", "extraction_reason": "OCR không đọc được chữ nào trên các trang",
                 "failure_category": "OCR không đọc được"}
        return {**scan_report(None, extra), "sheet": None}
    best = extract_ca_scan(pages, data)
    if not best:
        title = " | ".join(b.text for b in pages[0].boxes if b.y < pages[0].h * 0.3 and len(b.text) > 8)[:200]
        extra = {"status": "UNKNOWN_DOCUMENT", "failure_category": "detect sai mẫu / mẫu chưa hỗ trợ",
                 "extraction_reason": f"Không khớp mẫu phôi nào đã biết. Đầu trang: {title}"}
        return {**scan_report(None, extra), "sheet": None}
    best[1]["variants_tried"] = ["original"]  # whole page: 300 dpi original only; variants are for small field crops
    return {**scan_report(*best), "sheet": best}


def with_text_layer(fields: dict, extra: dict, text_fields: dict) -> None:
    """Both the (doubtful) text layer and OCR read this PDF: compare cell by cell, keep both readings with their
    source, and send any difference to review — no side is picked silently."""
    conflicts = compare_sources(fields, text_fields)
    if conflicts:
        extra["source_conflicts"] = conflicts
    extra.update(scan_status(fields, extra))
