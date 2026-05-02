# PDF Visual Translation Reference

This reference collects advanced routes for difficult PDFs. Keep `SKILL.md` as the default workflow; use this file only when diagnosis or QA shows a special case.

## Preflight Decision Table

| Signal | Meaning | Recommended Action |
|---|---|---|
| Very low extractable text | Scanned or image-heavy PDF | OCR first, then rerun diagnosis |
| Password required | Text and rendering blocked | Ask for password or decrypted PDF |
| Form widgets detected | AcroForm fields may hold visible English | Inspect form values separately |
| Annotations detected | Popups/comments may remain English | Extract and translate annotations if needed |
| Rotated pages detected | Coordinates may need extra QA | Render box previews for those pages |
| Mixed page sizes | QA pages must cover each size | Include each size in comparison renders |
| Many tiny boxes | Text extraction is fragmented | Use exact cache overrides for affected lines |

## OCR Route

For scanned PDFs, create a text layer before using the visual translation workflow.

Preferred command when available:

```bash
ocrmypdf --deskew --rotate-pages input.pdf ocr-output.pdf
```

Fallback route:

```bash
pdftoppm -png -r 300 input.pdf page
tesseract page-1.png page-1 -l eng pdf
```

After OCR, rerun:

```bash
python3 scripts/diagnose_pdf.py --source ocr-output.pdf
python3 scripts/visual_translate_pdf.py --inspect --source ocr-output.pdf
```

Continue only when text density is reasonable and box previews cover the visible English.

## Extraction Fallbacks

If PyMuPDF extraction misses text or fragments lines badly, inspect the PDF with another tool before rebuilding.

Bounding-box XML:

```bash
pdftotext -bbox-layout input.pdf bbox.xml
```

Layout text:

```bash
pdftotext -layout input.pdf layout.txt
```

Structural table inspection:

```python
import pdfplumber

with pdfplumber.open("input.pdf") as pdf:
    page = pdf.pages[0]
    print(page.extract_text())
    print(page.extract_tables())
```

These fallback tools are diagnostic. The normal rebuild still uses `visual_translate_pdf.py` unless a new extraction adapter is written.

## PDF Repair

If a PDF fails to open, renders inconsistently, or has broken object structure:

```bash
qpdf --check input.pdf
qpdf input.pdf repaired.pdf
```

Then diagnose and translate `repaired.pdf`.

## Forms And Annotations

Overlay translation edits page appearance. It does not rewrite:

- AcroForm field values.
- Annotation popup contents.
- Embedded file attachments.
- Hidden metadata.

When these matter, extract them separately, translate them, and either update the PDF structure or tell the user what remains unchanged.

## Text-Box Preview Rules

Use `render_text_box_preview.py` before translating many batches.

- Orange boxes should cover text that still needs cache entries.
- Green boxes should match exact glossary entries or cache translations.
- Missing boxes usually mean OCR or another extraction strategy is needed.
- Boxes that cut across chart graphics or table borders need final manual QA.
- Very short boxes may require shorter Chinese cache overrides.

## QA Page Selection

Always include:

- Cover or opening page.
- First dense prose page.
- Representative table pages, especially colored headers or heatmaps.
- Representative chart or figure pages.
- First and last legal, appendix, disclosure, or footnote-heavy pages.
- Any rotated or unusual-size pages reported by diagnosis.

## Delivery Notes

When delivering an overlay-translated PDF, say whether:

- The visible output is Chinese.
- The hidden/searchable text layer may still contain English.
- Any scanned pages, form fields, or annotations were excluded or handled separately.
