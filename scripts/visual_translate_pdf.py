#!/usr/bin/env python3
"""Create a visually 1:1 Chinese overlay translation of an English PDF.

This script preserves the source PDF as the visual base. It samples the local
background around each extractable English line, covers that line, and inserts
Chinese text in the same coordinates.

The preferred workflow is LLM-first:
1. Export translation jobs from the PDF.
2. Let an AI agent translate those jobs with document context into a cache JSON.
3. Rebuild the PDF from that cache.

Argos/legacy MT support remains as an optional last-resort fallback, not the
recommended path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import fitz


# Keep this empty for reusability. Project-specific terminology belongs in the
# per-document glossary JSON, generated after the agent reads the PDF.
DEFAULT_REPLACEMENTS: List[Tuple[str, str]] = []

SKIP_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^[\d,.\-+()%/: $~]+$"),
    re.compile(r"^[+\-−]?\d+(?:\.\d+)?%\s*l$"),
    re.compile(r"^[A-Z]$"),
    re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\.?$"),
    re.compile(r"^www\."),
    re.compile(r"^https?://"),
]

PRESERVE_TOKEN_PATTERNS = [
    re.compile(r"^[A-Z&]{2,6}$"),
    re.compile(r"^[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]*)+$"),
    re.compile(r"^[a-z][A-Z][A-Za-z0-9]*$"),
    re.compile(r"^[A-Za-z]+[\-_]?\d+[A-Za-z0-9\-]*$"),
    re.compile(r"^[A-Z]+:[A-Z0-9.]+$"),
    re.compile(r"^[A-Z]{2,}\.?[A-Z]{1,}\.?$"),
]

PRESERVE_CORP_SUFFIX = re.compile(
    r"\b(Inc|LLC|Ltd|Co|Corp|Corporation|Company|GmbH|AG|S\.A|SA|NV|BV|PLC|LP|LLP|SE|Pty|Holdings|Group|Bank|Capital|Partners|Securities)\.?$"
)

PRESERVE_STOPWORDS = frozenset({
    "the", "of", "for", "and", "in", "on", "at", "to", "with", "from", "by",
    "a", "an", "is", "are", "was", "were", "be", "been", "being", "as", "or",
    "this", "that", "these", "those", "it", "its", "their", "our", "your",
    "we", "they", "you", "i", "but", "if", "than", "then", "so", "not",
})


def looks_like_preserve_candidate(s: str) -> bool:
    s = s.strip().rstrip(".,;:")
    if not s or len(s) > 60 or not has_alpha(s):
        return False
    words = s.split()
    if any(w.lower().rstrip(".,;:") in PRESERVE_STOPWORDS for w in words):
        return False
    if len(words) == 1:
        w = words[0]
        return any(p.match(w) for p in PRESERVE_TOKEN_PATTERNS)
    if PRESERVE_CORP_SUFFIX.search(s):
        return all(w[0].isupper() or w[0].isdigit() or w[0] in "&." for w in words)
    if 2 <= len(words) <= 3 and all(any(c.isupper() for c in w) for w in words):
        if any(w.isupper() and len(w) >= 2 for w in words):
            return True
        if all(re.match(r"^[A-Z][A-Za-z0-9.&\-]*$", w) for w in words):
            return any(re.search(r"[a-z][A-Z]|[A-Z]{2,}", w) for w in words)
    return False


def norm_text(text: str) -> str:
    return " ".join(text.replace("\u00a0", " ").split())


def has_alpha(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def is_wingdings(font: str) -> bool:
    return "Wingdings" in font or "Webdings" in font


def should_skip_text(text: str) -> bool:
    s = norm_text(text)
    if not s:
        return True
    if not has_alpha(s):
        return True
    return any(pattern.match(s) for pattern in SKIP_PATTERNS)


def load_glossary(path: Optional[Path]) -> Tuple[Dict[str, str], List[Tuple[str, str]], List[str]]:
    exact: Dict[str, str] = {}
    replacements = list(DEFAULT_REPLACEMENTS)
    bad_terms: List[str] = []
    if not path:
        return exact, replacements, bad_terms
    data = json.loads(path.read_text(encoding="utf-8"))
    for k, v in data.get("exact", {}).items():
        exact[k] = v
        exact[norm_text(k)] = v
    for kept in data.get("keep_as_source", []):
        s = str(kept)
        exact[s] = s
        exact[norm_text(s)] = s
    for row in data.get("replacements", []):
        if isinstance(row, list) and len(row) == 2:
            replacements.append((str(row[0]), str(row[1])))
    bad_terms = [str(x) for x in data.get("bad_terms", [])]
    return exact, replacements, bad_terms


def postprocess_translation(src: str, dst: str, replacements: List[Tuple[str, str]]) -> str:
    out = dst.strip()
    for old, new in replacements:
        out = out.replace(old, new)
    out = re.sub(r"\(英语:[^)]+\)", "", out)
    out = re.sub(r"\(中文\(简体\)\s*\)", "", out)
    out = re.sub(r"\(简体中文\)", "", out)
    out = re.sub(r"\s*互联网档案馆的存[檔档],存档日期[\d-]+\.?", "", out)
    out = out.replace("维基月球在线解说-", "")
    out = out.replace("(韩语).", "")
    out = re.sub(r"\s+([，。；：、！？）】])", r"\1", out)
    out = re.sub(r"([（【])\s+", r"\1", out)
    out = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", out)
    out = re.sub(r"([A-Za-z])，([A-Za-z])", r"\1, \2", out)
    out = re.sub(r"([\u4e00-\u9fff]),([\u4e00-\u9fffA-Za-z0-9])", r"\1，\2", out)
    if re.search(r"(.{1,3})(?:\1){12,}", out) or "第三、第三、第三" in out:
        return src
    return out


def find_cjk_font(user_font: Optional[Path]) -> Optional[Path]:
    candidates = []
    if user_font:
        candidates.append(user_font)
    candidates.extend(
        [
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/source-han-sans/SourceHanSansCN-Regular.otf"),
        ]
    )
    for path in candidates:
        if path and path.exists():
            return path
    return None


def int_to_rgb(color: int) -> Tuple[float, float, float]:
    return (
        ((color >> 16) & 0xFF) / 255.0,
        ((color >> 8) & 0xFF) / 255.0,
        (color & 0xFF) / 255.0,
    )


def dominant_bg(pix: fitz.Pixmap, rect: fitz.Rect, scale: float) -> Tuple[float, float, float]:
    r = fitz.Rect(rect)
    r.x0 -= 1.6
    r.y0 -= 1.1
    r.x1 += 1.6
    r.y1 += 1.1
    x0 = max(0, int(r.x0 * scale))
    y0 = max(0, int(r.y0 * scale))
    x1 = min(pix.width - 1, int(r.x1 * scale))
    y1 = min(pix.height - 1, int(r.y1 * scale))
    if x1 <= x0 or y1 <= y0:
        return (1, 1, 1)
    counts: Counter[Tuple[int, int, int]] = Counter()
    step_x = max(1, (x1 - x0) // 18)
    step_y = max(1, (y1 - y0) // 10)
    for y in range(y0, y1, step_y):
        for x in range(x0, x1, step_x):
            try:
                px = pix.pixel(x, y)
            except Exception:
                continue
            rgb = tuple(int(v) for v in px[:3])
            if sum(rgb) < 80:
                continue
            counts[tuple((v // 16) * 16 for v in rgb)] += 1
    if not counts:
        return (1, 1, 1)
    rgb = counts.most_common(1)[0][0]
    out = tuple((v + 8) / 255.0 for v in rgb)
    if min(out) > 0.91 and (max(out) - min(out)) < 0.05:
        return (1, 1, 1)
    return out


def line_jobs(page: fitz.Page) -> List[dict]:
    jobs = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            non_wing = [s for s in spans if not is_wingdings(s.get("font", ""))]
            if not non_wing:
                continue
            text = "".join(s.get("text", "") for s in non_wing).strip()
            if should_skip_text(text):
                continue
            rect = fitz.Rect(
                min(s["bbox"][0] for s in non_wing),
                min(s["bbox"][1] for s in non_wing),
                max(s["bbox"][2] for s in non_wing),
                max(s["bbox"][3] for s in non_wing),
            )
            sizes = [float(s.get("size", 8)) for s in non_wing]
            colors = [int(s.get("color", 0)) for s in non_wing]
            fonts = [s.get("font", "") for s in non_wing]
            jobs.append(
                {
                    "text": text,
                    "rect": rect,
                    "size": max(set(sizes), key=sizes.count),
                    "color": max(set(colors), key=colors.count),
                    "bold": any("Bold" in f or "Medium" in f or "Black" in f for f in fonts),
                }
            )
    return jobs


def collect_texts(doc: fitz.Document, exact: Dict[str, str]) -> List[str]:
    texts = set()
    for page in doc:
        for job in line_jobs(page):
            s = norm_text(job["text"])
            if job["text"] in exact or s in exact:
                continue
            texts.add(s)
    return sorted(texts, key=lambda x: (-len(x), x))


def cache_has_translation(cache: Dict[str, str], raw: str, normalized: str) -> bool:
    for key in (raw, normalized):
        if key in cache and str(cache[key]).strip():
            return True
    return False


def collect_translation_jobs(
    doc: fitz.Document,
    exact: Dict[str, str],
    cache: Optional[Dict[str, str]] = None,
) -> List[dict]:
    cache = cache or {}
    seen: Dict[str, dict] = {}
    for pno, page in enumerate(doc, start=1):
        for job in line_jobs(page):
            src = norm_text(job["text"])
            if job["text"] in exact or src in exact or cache_has_translation(cache, job["text"], src):
                continue
            entry = seen.setdefault(
                src,
                {
                    "id": f"t{len(seen) + 1:05d}",
                    "source": src,
                    "pages": [],
                    "occurrences": 0,
                    "max_font_size": 0,
                    "style_hint": "body",
                    "_first_page": pno,
                    "_first_rect": [job["rect"].x0, job["rect"].y0, job["rect"].x1, job["rect"].y1],
                },
            )
            entry["occurrences"] += 1
            if pno not in entry["pages"]:
                entry["pages"].append(pno)
            entry["max_font_size"] = max(entry["max_font_size"], round(float(job["size"]), 2))
            if len(src) <= 36:
                entry["style_hint"] = "short_label_or_table_cell"
            elif job.get("bold") or float(job["size"]) >= 11:
                entry["style_hint"] = "heading_or_emphasis"
    return sorted(seen.values(), key=lambda x: (x["_first_page"], x["_first_rect"][1], x["_first_rect"][0], x["source"]))


def page_lines_with_geom(page: "fitz.Page") -> List[Tuple[float, float, float, str]]:
    out: List[Tuple[float, float, float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if not is_wingdings(s.get("font", ""))]
            if not spans:
                continue
            text = norm_text("".join(s.get("text", "") for s in spans))
            if not text:
                continue
            y0 = min(s["bbox"][1] for s in spans)
            y1 = max(s["bbox"][3] for s in spans)
            x0 = min(s["bbox"][0] for s in spans)
            out.append((y0, y1, x0, text))
    return out


def attach_row_context(doc: "fitz.Document", jobs: List[dict], max_neighbors: int = 6) -> None:
    page_cache: Dict[int, List[Tuple[float, float, float, str]]] = {}
    for j in jobs:
        first_page = j.get("_first_page")
        first_rect = j.get("_first_rect")
        if not first_page or not first_rect:
            continue
        if j.get("style_hint") != "short_label_or_table_cell":
            continue
        if first_page not in page_cache:
            page_cache[first_page] = page_lines_with_geom(doc[first_page - 1])
        target_y = (first_rect[1] + first_rect[3]) / 2
        tol = max(2.5, (first_rect[3] - first_rect[1]) * 0.6)
        neighbors: List[Tuple[float, str]] = []
        for y0, y1, x0, text in page_cache[first_page]:
            yc = (y0 + y1) / 2
            if abs(yc - target_y) <= tol and text != j["source"]:
                neighbors.append((x0, text))
        neighbors.sort()
        if neighbors:
            j["row_context"] = [t for _, t in neighbors[:max_neighbors]]


def strip_internal_fields(jobs: List[dict]) -> None:
    for j in jobs:
        j.pop("_first_page", None)
        j.pop("_first_rect", None)


def export_translation_jobs(
    source: Path,
    export_path: Path,
    exact: Dict[str, str],
    cache_path: Optional[Path],
    auto_preserve: bool = True,
) -> None:
    doc = fitz.open(source)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
    jobs = collect_translation_jobs(doc, exact, cache)
    attach_row_context(doc, jobs)
    strip_internal_fields(jobs)
    preserve = sorted({j["source"] for j in jobs if looks_like_preserve_candidate(j["source"])}) if auto_preserve else []
    preserve_set = set(preserve)
    for j in jobs:
        if j["source"] in preserve_set:
            j["preserve_default"] = True
    pages = []
    for pno, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append({"page": pno, "text": text})
    cache_template = {
        j["source"]: (j["source"] if j["source"] in preserve_set else "")
        for j in jobs
    }
    payload = {
        "source_pdf": str(source),
        "page_count": doc.page_count,
        "page_size": [doc[0].rect.width, doc[0].rect.height] if doc.page_count else [],
        "translation_contract": {
            "cache_format": "JSON object mapping each exact source string to its Chinese translation",
            "requirements": [
                "Translate with document-level context, not sentence-by-sentence literal MT.",
                "Preserve proper nouns, tickers, data-source names, product names, emails, URLs, and numeric values unless context requires translation.",
                "Prefer concise Chinese for table cells and headings so text fits original coordinates.",
                "Keep the source string as the JSON key exactly as provided.",
                "auto_preserve_candidates lists strings the script flagged as likely brand/product/ticker names. The cache_template pre-fills these as self-maps (English preserved). Override only if context proves a candidate should actually be translated.",
                "For items with style_hint=short_label_or_table_cell, use the row_context field (other cells on the same table row) to disambiguate before translating.",
                "When unsure whether a short capitalized term is a brand vs. a common noun, prefer to preserve the English source — false preservation is easier to spot in QA than wrong translation.",
            ],
        },
        "document_text_by_page": pages,
        "auto_preserve_candidates": preserve,
        "items": jobs,
        "cache_template": cache_template,
    }
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"exported {len(jobs)} translation jobs to {export_path}")
    if preserve:
        print(f"auto-preserve candidates: {len(preserve)} (kept as English by default in cache_template)")
    if cache_path and not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache_template, ensure_ascii=False, indent=2), encoding="utf-8")
        n_empty = sum(1 for v in cache_template.values() if not v)
        n_pre = len(cache_template) - n_empty
        print(f"wrote cache skeleton to {cache_path} ({n_empty} empty, {n_pre} pre-filled as keep-as-English)")


def parse_page_filter(value: Optional[str]) -> Optional[set[int]]:
    if not value:
        return None
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                start, end = end, start
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return pages


def compact_page_context(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    compact = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "\n[...]"


def export_translation_batch(
    source: Path,
    export_path: Path,
    exact: Dict[str, str],
    cache_path: Optional[Path],
    batch_size: int,
    batch_index: int,
    page_range: Optional[str],
    context_chars: int,
    auto_preserve: bool = True,
) -> None:
    doc = fitz.open(source)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
    jobs = collect_translation_jobs(doc, exact, cache)
    attach_row_context(doc, jobs)
    page_filter = parse_page_filter(page_range)
    if page_filter is not None:
        jobs = [j for j in jobs if any(p in page_filter for p in j["pages"])]
    preserve = {j["source"] for j in jobs if looks_like_preserve_candidate(j["source"])} if auto_preserve else set()
    for j in jobs:
        if j["source"] in preserve:
            j["preserve_default"] = True
    total = len(jobs)
    batch_size = max(1, batch_size)
    total_batches = (total + batch_size - 1) // batch_size
    if batch_index < 0:
        raise ValueError("--batch-index must be >= 0")
    start = batch_index * batch_size
    end = min(start + batch_size, total)
    batch = jobs[start:end]
    pages_in_batch = sorted({int(j.get("_first_page") or j["pages"][0]) for j in batch})
    context_by_page = [
        {"page": p, "text": compact_page_context(doc[p - 1].get_text("text"), context_chars)}
        for p in pages_in_batch
        if 1 <= p <= doc.page_count and context_chars > 0
    ]
    strip_internal_fields(batch)
    payload = {
        "source_pdf": str(source),
        "page_count": doc.page_count,
        "batch": {
            "index": batch_index,
            "batch_size": batch_size,
            "start_item": start,
            "end_item": end,
            "total_remaining_items": total,
            "total_batches": total_batches,
            "page_range_filter": page_range or "",
        },
        "translation_contract": {
            "output_format": "JSON object mapping each exact source string in items[].source to its Chinese translation.",
            "rules": [
                "Translate only this batch.",
                "Do not include context_by_page, commentary, Markdown fences, or unrequested keys in the output JSON.",
                "Preserve proper nouns, tickers, product names, data-source names, emails, URLs, numbers, and short codes unless context clearly requires translation.",
                "Use concise Chinese for headings, chart labels, and table cells so text fits the original coordinates.",
                "If preserve_default is true, keep the English source unless the page context proves it should be translated.",
            ],
        },
        "context_by_page": context_by_page,
        "items": batch,
        "cache_patch_template": {j["source"]: (j["source"] if j["source"] in preserve else "") for j in batch},
    }
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"exported batch {batch_index + 1}/{max(total_batches, 1)} with {len(batch)} items to {export_path}")
    print(f"remaining items considered: {total}; page contexts: {len(context_by_page)}")


def merge_cache_patch(cache_path: Path, patch_path: Path) -> None:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    if not isinstance(cache, dict) or not isinstance(patch, dict):
        raise ValueError("cache and patch must both be JSON objects")
    clean_patch = {str(k): str(v) for k, v in patch.items() if str(k).strip()}
    cache.update(clean_patch)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"merged {len(clean_patch)} translations into {cache_path}")
    print(f"cache entries: {len(cache)}")


def inspect_pdf(source: Path) -> None:
    doc = fitz.open(source)
    print(f"file: {source}")
    print(f"pages: {doc.page_count}")
    if doc.page_count:
        first = doc[0].rect
        print(f"first page size: {first.width:.1f} x {first.height:.1f} pt")
    fonts: set[str] = set()
    image_pages = 0
    text_pages = 0
    total_chars = 0
    for page in doc:
        for f in page.get_fonts():
            fonts.add(f[3])
        text = page.get_text("text")
        if text.strip():
            text_pages += 1
            total_chars += len(text)
        if page.get_images():
            image_pages += 1
    print(f"pages with extractable text: {text_pages}/{doc.page_count}")
    print(f"pages with images: {image_pages}/{doc.page_count}")
    print(f"total extracted characters: {total_chars}")
    sample = sorted(fonts)
    print(f"fonts ({len(sample)}): {sample[:20]}{'...' if len(sample) > 20 else ''}")
    if doc.page_count and total_chars < 80 * doc.page_count:
        print("warning: low character density — likely a scanned/image-only PDF; OCR is required before this skill can translate it")


def translate_with_argos(texts: List[str]) -> Dict[str, str]:
    os.environ.setdefault("XDG_DATA_HOME", "/tmp/codex_argos_data")
    os.environ.setdefault("XDG_CONFIG_HOME", "/tmp/codex_argos_config")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/codex_argos_cache")
    try:
        import ctranslate2
        from argostranslate import package
    except Exception as exc:
        raise RuntimeError(
            "Argos/CTranslate2 is unavailable. Install argostranslate and ctranslate2, "
            "or provide a populated cache JSON (drop --allow-legacy-mt) so the script does not fall back to MT."
        ) from exc

    packages = [p for p in package.get_installed_packages() if p.from_code == "en" and p.to_code == "zh"]
    if not packages:
        raise RuntimeError(
            "No installed Argos en->zh package. Install one first, or provide a populated cache JSON."
        )
    pkg = packages[0]
    translator = ctranslate2.Translator(str(pkg.package_path / "model"), device="cpu")
    output: Dict[str, str] = {}
    batch_size = 64
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        tokenized = [pkg.tokenizer.encode(t) for t in batch]
        results = translator.translate_batch(
            tokenized,
            beam_size=2,
            max_batch_size=32,
            batch_type="tokens",
            replace_unknowns=True,
        )
        for src, res in zip(batch, results):
            output[src] = pkg.tokenizer.decode(res.hypotheses[0]).lstrip()
        print(f"translated {min(start + batch_size, len(texts))}/{len(texts)}")
    return output


def prepare_cache(
    doc: fitz.Document,
    cache_path: Path,
    exact: Dict[str, str],
    replacements: List[Tuple[str, str]],
    allow_legacy_mt: bool,
) -> Dict[str, str]:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    needed = collect_texts(doc, exact)
    missing = [t for t in needed if t not in cache]
    print(f"unique lines needing translation: {len(needed)}; missing: {len(missing)}")
    if missing and not allow_legacy_mt:
        missing_path = cache_path.with_suffix(cache_path.suffix + ".missing.txt")
        missing_path.write_text("\n".join(missing), encoding="utf-8")
        raise RuntimeError(
            f"Missing translations written to {missing_path}. "
            "Use --export-jobs and let an AI agent fill a translation cache, "
            "or pass --allow-legacy-mt for the Argos fallback."
        )
    if missing:
        translated = translate_with_argos(missing)
        for src, dst in translated.items():
            cache[src] = postprocess_translation(src, dst, replacements)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def lookup_translation(
    text: str,
    exact: Dict[str, str],
    cache: Dict[str, str],
    replacements: List[Tuple[str, str]],
) -> str:
    s = norm_text(text)
    if text in exact:
        return postprocess_translation(text, exact[text], replacements)
    if s in exact:
        return postprocess_translation(text, exact[s], replacements)
    if text in cache:
        return postprocess_translation(text, cache[text], replacements)
    if s in cache:
        return postprocess_translation(text, cache[s], replacements)
    return postprocess_translation(text, text, replacements)


def fit_font_size(font: fitz.Font, text: str, rect: fitz.Rect, base: float) -> float:
    width = max(1.0, rect.width)
    height = max(1.0, rect.height)
    for factor in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58, 0.52, 0.46):
        size = max(3.8, base * factor)
        if font.text_length(text, fontsize=size) <= width + 1.2 and size * 1.05 <= height + 5.5:
            return size
    return max(3.2, min(base * 0.44, height * 0.92))


def build_pdf(args: argparse.Namespace) -> None:
    source = Path(args.source)
    output = Path(args.output)
    cache_path = Path(args.cache) if args.cache else output.with_suffix(".translation-cache.json")
    glossary_path = Path(args.glossary) if args.glossary else None
    exact, replacements, bad_terms = load_glossary(glossary_path)
    doc = fitz.open(source)
    cache = prepare_cache(doc, cache_path, exact, replacements, args.allow_legacy_mt)
    font_path = find_cjk_font(Path(args.font) if args.font else None)
    render_font = fitz.Font(fontfile=str(font_path)) if font_path else fitz.Font("china-s")
    scale = 2.0
    matrix = fitz.Matrix(scale, scale)
    translated = 0
    skipped = 0

    for pno, page in enumerate(doc, start=1):
        jobs = line_jobs(page)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        fontname = "cjkplus"
        if font_path:
            page.insert_font(fontfile=str(font_path), fontname=fontname)
        else:
            fontname = "china-s"
        for job in jobs:
            src = job["text"]
            cn = lookup_translation(src, exact, cache, replacements)
            if not cn or cn == src:
                skipped += 1
                continue
            translated += 1
            rect: fitz.Rect = job["rect"]
            bg = dominant_bg(pix, rect, scale)
            paint = fitz.Rect(rect)
            paint.x0 -= 0.55
            paint.y0 -= 0.35
            paint.x1 += 0.55
            paint.y1 += 0.35
            page.draw_rect(paint, color=bg, fill=bg, width=0, overlay=True)
            color = int_to_rgb(job["color"])
            if sum(color) > 2.75 and sum(bg) > 2.2:
                color = (0, 0, 0)
            size = fit_font_size(render_font, cn, rect, job["size"])
            baseline = rect.y0 + size * 0.88
            page.insert_text((rect.x0, baseline), cn, fontname=fontname, fontsize=size, color=color, overlay=True)
        if pno == 1 or pno % 5 == 0:
            print(f"rebuilt page {pno}/{doc.page_count}")

    if output.exists():
        output.unlink()
    doc.save(output, garbage=4, deflate=True, clean=True)
    doc.close()
    print(f"saved {output}")
    print(f"translated={translated} skipped={skipped}")

    if args.render_dir:
        render_comparisons(source, output, Path(args.render_dir), args.compare_pages)
    if bad_terms:
        scan_bad_terms(cache_path, bad_terms, replacements, exact)


def parse_pages(value: str) -> List[int]:
    pages = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        pages.append(int(part))
    return pages


def render_comparisons(source: Path, output: Path, render_dir: Path, compare_pages: str) -> None:
    render_dir.mkdir(parents=True, exist_ok=True)
    pages = parse_pages(compare_pages) if compare_pages else [1]
    src = fitz.open(source)
    out = fitz.open(output)
    matrix = fitz.Matrix(2, 2)
    try:
        from PIL import Image, ImageDraw
    except Exception:
        Image = None
        ImageDraw = None
    for p in pages:
        if p < 1 or p > src.page_count or p > out.page_count:
            continue
        src_png = render_dir / f"original_p{p:02d}.png"
        out_png = render_dir / f"translated_p{p:02d}.png"
        src[p - 1].get_pixmap(matrix=matrix, alpha=False).save(src_png)
        out[p - 1].get_pixmap(matrix=matrix, alpha=False).save(out_png)
        if Image and ImageDraw:
            left = Image.open(src_png).convert("RGB")
            right = Image.open(out_png).convert("RGB")
            combo = Image.new("RGB", (left.width * 2 + 40, max(left.height, right.height)), "white")
            combo.paste(left, (0, 0))
            combo.paste(right, (left.width + 40, 0))
            draw = ImageDraw.Draw(combo)
            draw.rectangle([0, 0, combo.width, 32], fill="white")
            draw.text((10, 8), f"Original - Page {p}", fill="black")
            draw.text((left.width + 50, 8), f"Chinese - Page {p}", fill="black")
            combo.save(render_dir / f"compare_p{p:02d}.png")
    print(f"rendered comparisons to {render_dir}")


def scan_bad_terms(
    cache_path: Path,
    bad_terms: Iterable[str],
    replacements: List[Tuple[str, str]],
    exact: Dict[str, str],
) -> None:
    if not cache_path.exists():
        return
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    hits = []
    for src, dst in data.items():
        cleaned = exact.get(src) or exact.get(norm_text(src)) or postprocess_translation(src, dst, replacements)
        if any(term and term in cleaned for term in bad_terms):
            hits.append((src, cleaned))
    if hits:
        print(f"bad-term hits in cache: {len(hits)}")
        for src, dst in hits[:40]:
            print("SRC:", src[:140])
            print("DST:", dst[:140])
    else:
        print("bad-term hits in cache: 0")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source English PDF")
    parser.add_argument("--output", help="Output Chinese PDF")
    parser.add_argument("--cache", help="Translation cache JSON path")
    parser.add_argument("--glossary", help="Glossary JSON with exact/replacements/bad_terms")
    parser.add_argument("--font", help="CJK-capable font file")
    parser.add_argument("--export-jobs", help="Export LLM translation jobs JSON and exit unless --output is also provided")
    parser.add_argument("--export-batch", help="Export a compact LLM translation batch JSON and exit")
    parser.add_argument("--merge-patch", help="Merge a batch patch JSON into --cache and exit")
    parser.add_argument("--batch-size", type=int, default=80, help="Items per --export-batch file")
    parser.add_argument("--batch-index", type=int, default=0, help="Zero-based batch index for --export-batch")
    parser.add_argument("--page-range", help="Optional page filter for --export-batch, e.g. 1-5,8,10-12")
    parser.add_argument("--context-chars", type=int, default=1200, help="Maximum page-context characters per page in --export-batch")
    parser.add_argument("--allow-legacy-mt", action="store_true", help="Allow Argos fallback for missing cache entries (last-resort, draft quality)")
    parser.add_argument("--inspect", action="store_true", help="Print PDF metadata (pages, size, fonts, scan-likelihood) and exit")
    parser.add_argument("--no-auto-preserve", action="store_true", help="Disable auto-detection of brand/ticker/product names that should stay in English")
    parser.add_argument("--render-dir", help="Directory for QA PNG renders")
    parser.add_argument("--compare-pages", default="1", help="Comma-separated pages for comparison renders")
    args = parser.parse_args()
    if args.inspect:
        inspect_pdf(Path(args.source))
        return
    glossary_path = Path(args.glossary) if args.glossary else None
    exact, _, _ = load_glossary(glossary_path)
    if args.merge_patch:
        if not args.cache:
            parser.error("--cache is required with --merge-patch")
        merge_cache_patch(Path(args.cache), Path(args.merge_patch))
        return
    if args.export_batch:
        cache_path = Path(args.cache) if args.cache else None
        export_translation_batch(
            Path(args.source),
            Path(args.export_batch),
            exact,
            cache_path,
            args.batch_size,
            args.batch_index,
            args.page_range,
            args.context_chars,
            auto_preserve=not args.no_auto_preserve,
        )
        return
    if args.export_jobs:
        cache_path = Path(args.cache) if args.cache else None
        export_translation_jobs(
            Path(args.source),
            Path(args.export_jobs),
            exact,
            cache_path,
            auto_preserve=not args.no_auto_preserve,
        )
        if not args.output:
            return
    if not args.output:
        parser.error("--output is required unless --export-jobs is used alone")
    try:
        build_pdf(args)
    except RuntimeError as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
