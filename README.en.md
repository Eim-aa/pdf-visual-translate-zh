# PDF Visual Translate ZH

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20%2F%20Codex-6f42c1)](SKILL.en.md)
[![Made for Chinese readers](https://img.shields.io/badge/Chinese%20readers-first-red)](README.md)

**Translate English PDFs into Chinese while preserving the original page geometry, tables, charts, colors, headers, footers, and visual layout as much as possible.**

Built for research reports, industry reports, white papers, disclosures, contracts, and slide-like PDFs where the Chinese output must still look like the source document.

[中文说明](README.md) | [Advanced Reference](REFERENCE.en.md) | [QA Checklist](references/pdf-translation-qa.en.md) | [Skill Guide](SKILL.en.md)

---

## Why This Exists

Many PDF translation tools translate text but break layouts when reports contain dense tables, charts, headers, footers, footnotes, or multi-column pages. This project takes a different path:

- It does not rebuild the PDF from scratch. It overlays Chinese text back onto the original page coordinates.
- It does not lock you into one translation model. Any LLM that can return JSON patches can be used.
- It does not rely on one huge chat context. Long documents can be translated in batches, cached, resumed, and reviewed.
- It does not stop at outputting a PDF. It can render comparison images for visual QA before delivery.

In short, this is a Chinese PDF delivery workflow, not a generic online translator.

## 30-Second Fit Check

| Your source or goal | Fit | Recommendation |
|---|---:|---|
| Selectable English PDF and layout must stay stable | Strong fit | Use this project directly |
| Research reports, filings, white papers, contracts, chart-heavy PDFs | Strong fit | Diagnose first, then translate in batches |
| Scanned or image-only PDFs | Not directly | OCR first, then use this workflow |
| Searchable/copyable Chinese text layer is mandatory | Needs extra work | This project prioritizes visible Chinese output |
| You only need Markdown text extraction | Weak fit | Use a lighter PDF extraction tool |

## Highlights

- **Layout first**: preserve page count, dimensions, tables, charts, colors, headers, footers, and geometry as much as possible.
- **Batch translation**: export compact batches for LLM translation to reduce long-document failure risk.
- **Resumable cache**: translation state is stored in JSON, so failed runs can continue.
- **Glossary protection**: brand names, tickers, product names, datasets, URLs, emails, numbers, and short codes are preserved by default.
- **Visual QA**: render comparison pages to catch leftover English, white blocks, tiny text, table issues, and chart-page regressions.
- **Agent-skill ready**: works as a reusable Claude/Codex-style skill for repeatable PDF translation workflows.

## Start in One Minute

```bash
git clone https://github.com/Eim-aa/pdf-visual-translate-zh.git
cd pdf-visual-translate-zh
python3 -m pip install -r requirements.txt
```

Diagnose the source PDF first:

```bash
python3 scripts/diagnose_pdf.py --source your-report.pdf
```

If text density is very low, the PDF is likely scanned or image-only. OCR it first.

## Standard Workflow

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

### 1. Prepare Glossary and Cache

```bash
WORK="/tmp/pdf-visual-translate-zh"
mkdir -p "$WORK"
cp references/glossary-template.json "$WORK/glossary.json"
```

### 2. Export the First Translation Batch

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

### 3. Translate With an LLM

Translate the batch `items` into patch JSON. Keep every source string exactly as the key:

```json
{
  "Exact English source string": "Concise Chinese translation that fits the original coordinates"
}
```

### 4. Merge the Patch

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --cache "$WORK/translations.json" \
  --merge-patch "$WORK/batch-001.patch.json"
```

Repeat export with `--batch-index 0`. The script skips translated cache entries, so index `0` means "next untranslated batch."

### 5. Rebuild the Chinese PDF

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --output "$WORK/output-zh.pdf" \
  --cache "$WORK/translations.json" \
  --glossary "$WORK/glossary.json" \
  --render-dir "$WORK/qa" \
  --compare-pages 1,4,8
```

Review the rendered comparisons before delivery, especially covers, dense tables, chart pages, and legal/disclosure pages.

## Install as an Agent Skill

This repository can be installed as a reusable PDF translation skill for Claude/Codex-style agents.

| Environment | Recommended location | Example |
|---|---|---|
| Claude Code | `~/.claude/skills/pdf-visual-translate-zh-enhanced` | `cp -R . ~/.claude/skills/pdf-visual-translate-zh-enhanced` |
| Codex | `$CODEX_HOME/skills/pdf-visual-translate-zh-enhanced` or `~/.codex/skills/pdf-visual-translate-zh-enhanced` | `cp -R . ~/.codex/skills/pdf-visual-translate-zh-enhanced` |

Example agent request:

```text
Use pdf-visual-translate-zh to translate /path/to/report.pdf into a Chinese PDF.
Prioritize preserving page count, tables, charts, colors, and page geometry.
Use batched cache files and render QA comparison images before delivery.
```

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

## Commands

| Command | Purpose |
|---|---|
| `scripts/diagnose_pdf.py` | Preflight text density, scanned pages, encryption, forms, annotations, rotation, and page-size issues |
| `scripts/visual_translate_pdf.py --inspect` | Inspect translation-facing PDF metadata |
| `scripts/visual_translate_pdf.py --export-batch` | Export compact batches for LLM translation |
| `scripts/visual_translate_pdf.py --merge-patch` | Merge one patch JSON into the translation cache |
| `scripts/visual_translate_pdf.py --output` | Rebuild the Chinese visual-overlay PDF from the cache |
| `scripts/render_text_box_preview.py` | Render text-box previews to inspect what will be covered and translated |

## Limitations

- **Hidden text may still be English**: visible output is Chinese, but copy/search may still hit the English source layer.
- **Scanned PDFs require OCR**: image-only PDFs need a text layer first.
- **Form fields are not rewritten automatically**: AcroForm values require separate checks.
- **Annotation popups are not translated automatically**: comments and attachment metadata are outside page-text overlay.
- **Dense text may need manual compression**: Chinese must fit back into the original coordinates.

## Roadmap

- Add public before/after demo PDFs and rendered comparison images.
- Add a one-command orchestration script for batch export, patch merge, rebuild, and QA.
- Explore an OCR preprocessing path for scanned PDFs.
- Explore rebuilding a searchable Chinese text layer to reduce the hidden-English limitation.

## Who Should Star This

If you regularly handle English research reports, industry reports, company filings, white papers, contracts, or chart-heavy PDFs for Chinese readers, this repo is meant to be a reusable delivery workflow.

## License

MIT
