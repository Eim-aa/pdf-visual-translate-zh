---
name: pdf-visual-translate-zh-enhanced
description: Create visually faithful Chinese translations of extractable-text English PDFs while preserving page count, page size, tables, charts, colors, headers, footers, and layout. Use for report, deck, disclosure, contract, and data-heavy PDFs where visual fidelity matters more than a clean searchable Chinese text layer.
---

# PDF Visual Translate ZH Enhanced

## What This Skill Does

This skill turns an English PDF into a visually matched Chinese PDF.

It keeps the source PDF as the visual base, covers visible English text in place, and draws concise Chinese text back into the original coordinates. It is designed for extractable-text PDFs such as reports, research notes, disclosures, white papers, and slide-like PDFs.

Prefer visual fidelity over searchable text. Overlay mode may leave hidden original English text underneath; tell the user when that matters.

## Operating Principles

- Diagnose the PDF before translating.
- Keep translation state in files, not chat context.
- Translate in small batches and merge patches into a cache.
- Preserve proper nouns, tickers, product names, dataset names, URLs, emails, numbers, and short codes unless context clearly says otherwise.
- Validate visually before delivery, especially dense tables, charts, colored headers, and legal pages.
- Do not rasterize the whole PDF unless the user accepts a non-searchable image PDF.

## Decision Guide

Use this path when:

- The PDF has extractable English text.
- The user wants a Chinese PDF that looks like the original.
- Page count, page size, charts, tables, colors, logos, headers, and footers must remain stable.

Pause or change approach when:

- `diagnose_pdf.py` reports very low text density: run OCR first, then retry.
- The PDF is encrypted: ask for a password or decrypted source.
- The PDF uses fillable form fields or annotations: page text translation may not update field values or annotation contents; inspect these separately.
- The user needs selectable/searchable Chinese text: this overlay workflow is not the right final format without a clean rebuild layer.

## Quick Start

Set paths:

```bash
PDF="/path/to/source.pdf"
WORK="/tmp/pdf-visual-translate-zh"
GLOSSARY="$WORK/glossary.json"
CACHE="$WORK/translations.json"
OUT="$WORK/output-zh.pdf"
mkdir -p "$WORK"
cp references/glossary-template.json "$GLOSSARY"
```

### 1. Diagnose

Run a preflight diagnosis:

```bash
python3 scripts/diagnose_pdf.py \
  --source "$PDF" \
  --json-output "$WORK/diagnosis.json"
```

Also inspect the translation extractor:

```bash
python3 scripts/visual_translate_pdf.py --inspect --source "$PDF"
```

If the document looks scanned or image-only, OCR it first. Do not continue with visual translation until text extraction is usable.

### 2. Build The Glossary

Export a small first batch:

```bash
python3 scripts/visual_translate_pdf.py \
  --source "$PDF" \
  --glossary "$GLOSSARY" \
  --cache "$CACHE" \
  --export-batch "$WORK/batch-000.json" \
  --batch-index 0 \
  --batch-size 40 \
  --context-chars 1200
```

Read only this compact batch. Identify names, brands, tickers, product names, data sources, abbreviations, table headers, and repeated terms. Update `GLOSSARY` before translating many batches.

### 3. Preview Text Boxes

Render candidate text boxes on representative pages:

```bash
python3 scripts/render_text_box_preview.py \
  --source "$PDF" \
  --glossary "$GLOSSARY" \
  --cache "$CACHE" \
  --pages 1,4,6,12 \
  --output-dir "$WORK/box-preview"
```

Use this to catch extraction problems, rotated pages, overly fragmented text, and tiny table cells before spending time on translation.

### 4. Translate In Batches

Export the next untranslated batch:

```bash
python3 scripts/visual_translate_pdf.py \
  --source "$PDF" \
  --glossary "$GLOSSARY" \
  --cache "$CACHE" \
  --export-batch "$WORK/batch-001.json" \
  --batch-index 0 \
  --batch-size 60 \
  --context-chars 1000
```

Translate only `items` from that batch. Write a patch JSON:

```json
{
  "Exact English source string": "简洁、准确、能放回原坐标的中文"
}
```

Merge the patch:

```bash
python3 scripts/visual_translate_pdf.py \
  --source "$PDF" \
  --cache "$CACHE" \
  --merge-patch "$WORK/batch-001.patch.json"
```

Repeat with `--batch-index 0`. The script skips cache entries that already have translations, so index `0` means "next remaining batch." Stop when the export contains `0 items`.

### 5. Rebuild

```bash
python3 scripts/visual_translate_pdf.py \
  --source "$PDF" \
  --output "$OUT" \
  --cache "$CACHE" \
  --glossary "$GLOSSARY" \
  --render-dir "$WORK/qa" \
  --compare-pages 1,4,6,12,16,22,29,37
```

If rebuild writes a `.missing.txt`, do not paste or read the whole file into chat. Export another compact batch, translate it, merge it, and rebuild.

### 6. Verify

Review rendered comparison PNGs before delivery. Check:

- Same page count and dimensions as source.
- No blank white patches over colored areas.
- No visible English paragraphs left untranslated unless intentionally preserved.
- No mistranslated brands, product names, tickers, ratings, or data sources.
- No unreadably tiny Chinese in dense cells.
- Headers, footers, page numbers, colors, charts, and table geometry remain intact.

## Translation Contract

- Translate with page and section context, not isolated fragments.
- Use concise Chinese for table cells, legends, labels, axis text, captions, headings, and footers.
- Preserve proper nouns and identifiers unless the document clearly uses a Chinese convention.
- Keep each source string exactly as the JSON key.
- Add document-specific rules to `GLOSSARY`; do not add one-off replacements to the script.
- Prefer preserving a short ambiguous capitalized term over inventing a Chinese name.

## Batch Sizing

- `60-80` items for labels, tables, charts, and mostly numeric pages.
- `30-50` items for normal report prose.
- `20-30` items for legal disclosures, risk sections, long footnotes, or dense narrative pages.

If output gets too large, reduce `--batch-size` immediately and continue from files.

## Script Reference

- `scripts/diagnose_pdf.py`: preflight PDF diagnosis and route suggestions.
- `scripts/render_text_box_preview.py`: renders candidate text boxes for visual validation.
- `scripts/visual_translate_pdf.py --inspect`: prints translation-oriented metadata.
- `scripts/visual_translate_pdf.py --export-batch`: exports compact file-backed translation batches.
- `scripts/visual_translate_pdf.py --merge-patch`: merges one patch JSON into the cache.
- `scripts/visual_translate_pdf.py --output`: rebuilds the Chinese overlay PDF.
- `REFERENCE.md`: advanced OCR, repair, extraction fallback, form, annotation, and QA routes.
- `references/glossary-template.json`: per-document terminology and QA sweep starter.
- `references/pdf-translation-qa.md`: failure modes, recovery patterns, and manual checks.

## Hard Context Rules

These rules are mandatory for large PDFs.

- Do not paste the full PDF text, full cache JSON, full `translation_jobs.json`, full `.missing.txt`, or full diagnosis JSON into chat.
- Use `--export-batch` for translation work.
- Keep each batch to a size the model can translate cleanly.
- Write patch JSON files and merge them into the cache.
- Treat `CACHE`, `GLOSSARY`, and batch files as durable state.
- If a response approaches output limits, stop the batch, lower `--batch-size`, and continue.

## Recovery

- Scanned PDF: OCR first, then rerun diagnosis and batch export.
- Missing translations: export the next compact batch instead of reading `.missing.txt`.
- Bad terminology: update `GLOSSARY`, override affected cache entries, and rebuild.
- Tiny Chinese: shorten the affected cache translation manually.
- Wrong table/product preservation: add exact or `keep_as_source` glossary entries.
- Hidden English search/copy text: explain overlay behavior or switch to a clean rebuild strategy.
