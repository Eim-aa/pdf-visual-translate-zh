# PDF Visual Translate ZH

**A visually faithful English-to-Chinese PDF translation workflow that preserves layout, tables, charts, colors, headers, footers, page count, and page geometry as much as possible.**

[中文说明](README.md) | [Advanced Reference](REFERENCE.en.md) | [QA Checklist](references/pdf-translation-qa.en.md)

---

## What This Is

This project translates English PDFs into Chinese while preserving the original visual layout. Instead of rebuilding the document from scratch, it extracts text positions, samples the local background, covers the original English, and draws concise Chinese text back into the same coordinates.

It is designed for reports, research notes, white papers, disclosures, and data-heavy PDFs where layout fidelity matters.

## Core Trade-Off

This workflow prioritizes visual fidelity over a clean searchable Chinese text layer.

- **Visual overlay**: the visible output is Chinese, but the hidden text layer may still contain English.
- **LLM-first translation**: scripts export compact batches and merge translation patches; translation itself can be handled by any LLM.
- **File-backed state**: cache, glossary, batches, and QA artifacts live on disk.
- **Smart preservation**: proper nouns, tickers, product names, datasets, URLs, emails, numbers, and short codes are preserved unless context says otherwise.

## Workflow

```text
English PDF
  -> preflight diagnosis
  -> extract text and coordinates
  -> export translation batches
  -> translate batches with an LLM
  -> merge patch JSON into the cache
  -> rebuild with visual overlay
  -> render QA comparisons
  -> Chinese PDF
```

## Installation

Python 3.10 or newer is recommended.

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Diagnose

```bash
python3 scripts/diagnose_pdf.py --source your-report.pdf
```

If text density is very low, OCR the PDF first.

### 2. Prepare Working Files

```bash
WORK="/tmp/pdf-visual-translate-zh"
mkdir -p "$WORK"
cp references/glossary-template.json "$WORK/glossary.json"
```

### 3. Export a Batch

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --glossary "$WORK/glossary.json" \
  --cache "$WORK/translations.json" \
  --export-batch "$WORK/batch-001.json" \
  --batch-index 0 \
  --batch-size 60 \
  --context-chars 1000
```

### 4. Translate With an LLM

Translate the batch `items` into patch JSON. Keep each source string exactly as the key:

```json
{
  "Exact English source string": "Concise Chinese translation that fits the original coordinates"
}
```

### 5. Merge the Patch

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --cache "$WORK/translations.json" \
  --merge-patch "$WORK/batch-001.patch.json"
```

Repeat export with `--batch-index 0`. The script skips translated cache entries, so index `0` means "next untranslated batch."

### 6. Rebuild

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --output "$WORK/output-zh.pdf" \
  --cache "$WORK/translations.json" \
  --glossary "$WORK/glossary.json" \
  --render-dir "$WORK/qa" \
  --compare-pages 1,4,8
```

Review the comparison renders before delivery.

## Repository Layout

```text
pdf-visual-translate-zh/
├── README.md
├── README.en.md
├── SKILL.md
├── SKILL.en.md
├── REFERENCE.md
├── REFERENCE.en.md
├── requirements.txt
├── scripts/
│   ├── visual_translate_pdf.py
│   ├── diagnose_pdf.py
│   └── render_text_box_preview.py
├── references/
│   ├── glossary-template.json
│   ├── pdf-translation-qa.md
│   └── pdf-translation-qa.en.md
└── examples/
    └── glossary-example.json
```

## Limitations

- The hidden/searchable text layer may still contain English.
- Scanned PDFs require OCR first.
- AcroForm field values are not rewritten by the page overlay.
- Annotation popup contents are not translated.
- Dense tables and footnotes may need shorter manual translations.

## License

MIT
