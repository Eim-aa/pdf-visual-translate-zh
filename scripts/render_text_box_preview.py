#!/usr/bin/env python3
"""Render text boxes that the visual translation workflow will consider.

Green boxes already have an exact/cache translation. Orange boxes still need a
translation. This is a lightweight visual QA step before rebuilding the PDF.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import fitz
from PIL import Image, ImageDraw

# Ensure sibling module is importable regardless of working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from visual_translate_pdf import line_jobs, load_glossary, norm_text


def parse_pages(value: Optional[str], page_count: int, max_pages: int) -> List[int]:
    if not value:
        return list(range(1, min(page_count, max_pages) + 1))
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
    return [p for p in sorted(pages) if 1 <= p <= page_count]


def load_cache(path: Optional[Path]) -> Dict[str, str]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cache must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def has_translation(text: str, exact: Dict[str, str], cache: Dict[str, str]) -> bool:
    normalized = norm_text(text)
    for key in (text, normalized):
        if key in exact and str(exact[key]).strip():
            return True
        if key in cache and str(cache[key]).strip():
            return True
    return False


def draw_boxes(
    source: Path,
    output_dir: Path,
    pages: Iterable[int],
    exact: Dict[str, str],
    cache: Dict[str, str],
    scale: float,
) -> None:
    doc = fitz.open(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    for pno in pages:
        page = doc[pno - 1]
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        draw = ImageDraw.Draw(image)
        translated = 0
        missing = 0

        for job in line_jobs(page):
            rect = job["rect"]
            box = [rect.x0 * scale, rect.y0 * scale, rect.x1 * scale, rect.y1 * scale]
            if has_translation(job["text"], exact, cache):
                color = (0, 150, 80)
                translated += 1
            else:
                color = (230, 125, 0)
                missing += 1
            draw.rectangle(box, outline=color, width=2)

        label = f"Page {pno}: green={translated} translated/exact, orange={missing} missing"
        draw.rectangle([0, 0, min(image.width, 720), 28], fill=(255, 255, 255))
        draw.text((8, 7), label, fill=(0, 0, 0))
        output_path = output_dir / f"text_boxes_p{pno:02d}.png"
        image.save(output_path)
        print(f"saved {output_path} ({label})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source PDF")
    parser.add_argument("--output-dir", required=True, help="Directory for preview PNGs")
    parser.add_argument("--pages", help="Pages or ranges, e.g. 1,4,6-8")
    parser.add_argument("--max-pages", type=int, default=6, help="Default number of pages when --pages is omitted")
    parser.add_argument("--scale", type=float, default=2.0, help="Render scale")
    parser.add_argument("--glossary", help="Optional glossary JSON")
    parser.add_argument("--cache", help="Optional translation cache JSON")
    args = parser.parse_args()

    source = Path(args.source)
    doc = fitz.open(source)
    pages = parse_pages(args.pages, doc.page_count, args.max_pages)
    exact, _, _ = load_glossary(Path(args.glossary) if args.glossary else None)
    cache = load_cache(Path(args.cache) if args.cache else None)
    draw_boxes(source, Path(args.output_dir), pages, exact, cache, args.scale)


if __name__ == "__main__":
    main()

