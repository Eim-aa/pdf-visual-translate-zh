#!/usr/bin/env python3
"""Preflight diagnosis for PDF visual translation.

The goal is to route the document before translation work begins: extractable
text, likely scanned PDF, encrypted PDF, forms, annotations, rotated pages, and
other features that can affect visual overlay quality.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import fitz


def bool_attr(obj: object, name: str) -> bool:
    value = getattr(obj, name, None)
    try:
        return bool(value() if callable(value) else value)
    except Exception:
        return False


def count_iter(values: Optional[Iterable[Any]]) -> int:
    if values is None:
        return 0
    try:
        return sum(1 for _ in values)
    except Exception:
        return 0


def page_summary(page: fitz.Page, pno: int) -> Dict[str, Any]:
    text = page.get_text("text")
    image_count = len(page.get_images(full=True))
    annotation_count = count_iter(page.annots())
    widget_count = count_iter(page.widgets())
    rect = page.rect
    return {
        "page": pno,
        "width": round(rect.width, 2),
        "height": round(rect.height, 2),
        "rotation": int(page.rotation or 0),
        "text_chars": len(text.strip()),
        "image_count": image_count,
        "annotation_count": annotation_count,
        "widget_count": widget_count,
    }


def diagnose(source: Path, password: Optional[str] = None) -> Dict[str, Any]:
    doc = fitz.open(source)
    encrypted = bool_attr(doc, "is_encrypted") or bool_attr(doc, "needs_pass")
    needs_password = bool_attr(doc, "needs_pass")
    authenticated = False

    if needs_password and password:
        authenticated = bool(doc.authenticate(password))
        needs_password = not authenticated

    result: Dict[str, Any] = {
        "source_pdf": str(source),
        "encrypted": encrypted,
        "needs_password": needs_password,
        "authenticated": authenticated,
        "page_count": doc.page_count,
        "page_sizes": [],
        "pages": [],
        "totals": {},
        "warnings": [],
        "recommended_path": [],
    }

    if needs_password:
        result["warnings"].append("PDF requires a password before text extraction or rendering.")
        result["recommended_path"].append("Ask for a password or a decrypted source PDF.")
        return result

    fonts: Counter[str] = Counter()
    page_sizes: Counter[str] = Counter()
    pages: List[Dict[str, Any]] = []

    for pno, page in enumerate(doc, start=1):
        summary = page_summary(page, pno)
        pages.append(summary)
        page_sizes[f"{summary['width']}x{summary['height']}"] += 1
        for font in page.get_fonts():
            if len(font) > 3:
                fonts[str(font[3])] += 1

    total_text_chars = sum(p["text_chars"] for p in pages)
    text_pages = sum(1 for p in pages if p["text_chars"] > 0)
    image_pages = sum(1 for p in pages if p["image_count"] > 0)
    annotation_pages = sum(1 for p in pages if p["annotation_count"] > 0)
    widget_pages = sum(1 for p in pages if p["widget_count"] > 0)
    rotated_pages = [p["page"] for p in pages if p["rotation"]]

    avg_chars = total_text_chars / max(1, doc.page_count)
    likely_scanned = doc.page_count > 0 and (text_pages == 0 or avg_chars < 80)

    result["page_sizes"] = [{"size": k, "pages": v} for k, v in page_sizes.most_common()]
    result["pages"] = pages
    result["totals"] = {
        "text_pages": text_pages,
        "image_pages": image_pages,
        "annotation_pages": annotation_pages,
        "widget_pages": widget_pages,
        "total_text_chars": total_text_chars,
        "average_text_chars_per_page": round(avg_chars, 1),
        "rotated_pages": rotated_pages,
        "font_count": len(fonts),
        "sample_fonts": [name for name, _ in fonts.most_common(20)],
    }

    if likely_scanned:
        result["warnings"].append("Low extractable text density; this is likely scanned or image-heavy.")
        result["recommended_path"].append("Run OCR first, then rerun diagnosis and batch export.")
    else:
        result["recommended_path"].append("Proceed with compact batch export and visual overlay rebuild.")

    if widget_pages:
        result["warnings"].append("Fillable form widgets detected; visible page text translation may not update form values.")
        result["recommended_path"].append("Inspect form fields separately if form content must be translated.")

    if annotation_pages:
        result["warnings"].append("Annotations detected; annotation text may remain English unless handled separately.")

    if rotated_pages:
        result["warnings"].append("Rotated pages detected; preview text boxes before translating those pages.")

    if len(page_sizes) > 1:
        result["warnings"].append("Multiple page sizes detected; include representative pages in QA renders.")

    return result


def print_report(result: Dict[str, Any]) -> None:
    print(f"file: {result['source_pdf']}")
    print(f"pages: {result['page_count']}")
    print(f"encrypted: {result['encrypted']}; needs_password: {result['needs_password']}")
    if result["page_sizes"]:
        print("page sizes:")
        for row in result["page_sizes"]:
            print(f"  - {row['size']} pt: {row['pages']} page(s)")
    totals = result.get("totals", {})
    if totals:
        print(f"text pages: {totals['text_pages']}/{result['page_count']}")
        print(f"image pages: {totals['image_pages']}/{result['page_count']}")
        print(f"annotation pages: {totals['annotation_pages']}/{result['page_count']}")
        print(f"form-widget pages: {totals['widget_pages']}/{result['page_count']}")
        print(f"total extracted characters: {totals['total_text_chars']}")
        print(f"average characters/page: {totals['average_text_chars_per_page']}")
        if totals["rotated_pages"]:
            print(f"rotated pages: {totals['rotated_pages']}")
        print(f"fonts ({totals['font_count']}): {totals['sample_fonts']}")
    if result["warnings"]:
        print("warnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")
    print("recommended path:")
    for step in result["recommended_path"]:
        print(f"  - {step}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source PDF")
    parser.add_argument("--password", help="Password for encrypted PDFs")
    parser.add_argument("--json-output", help="Optional path for machine-readable diagnosis JSON")
    args = parser.parse_args()

    result = diagnose(Path(args.source), args.password)
    print_report(result)

    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote diagnosis JSON to {out}")


if __name__ == "__main__":
    main()
