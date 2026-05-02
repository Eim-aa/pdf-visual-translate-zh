# PDF Translation QA

## Preflight Checks

- Run `scripts/diagnose_pdf.py` before translation. If it reports low text density, OCR first.
- Check whether the PDF is encrypted, has form widgets, has annotations, contains rotated pages, or mixes page sizes.
- Render `scripts/render_text_box_preview.py` on representative pages before translating many batches.
- Include cover, dense prose, table, chart, and legal/disclosure pages in the final comparison render.

## Common Failure Modes

- White rectangles cover blue table headers: use sampled local background fill, not fixed white redaction.
- Chinese is unreadably tiny: add exact/manual shorter translations for those lines.
- Latin letters are spaced out: switch to a different CJK-capable font such as Arial Unicode, PingFang, Noto Sans CJK, or Source Han Sans.
- Legal/disclosure pages remain English: they often contain long paragraphs not covered by glossary; export missing jobs, translate them with document context, and manually fix repeated boilerplate.
- Product or technical names are hallucinated: add exact glossary entries for the specific names and codes in the current PDF.
- Text extraction contains control characters or broken Japanese/Chinese names: skip or manually replace those lines.
- Copy/search still shows English: overlay mode preserves the original text layer. Explain this to the user or use a clean-text rebuild workflow.
- Translation reads like literal MT: go back to the exported jobs, read the surrounding page text, and rewrite the cache entries in natural Chinese while keeping numbers and labels concise.
- Output PDF has zero translated lines: source is likely scanned/image-only — run `--inspect` and OCR the source first.
- Dark text becomes invisible on a dark cell: the contrast fallback only flips white-on-light to black. If you hit dark-on-dark, add an exact glossary entry that pairs the source with a translation prefixed by a unicode marker, or post-edit by hand.
- Form-field values remain English: page overlay translation does not edit AcroForm field values; inspect form widgets separately.
- Annotation popups remain English: page overlay translation does not rewrite annotation contents.
- Rotated page text is misplaced: preview text boxes and include those pages in final QA.

## Large-PDF Strategy

When the export contains hundreds of unique strings:

- Translate the cache in batches grouped by page range or section, then merge back into one JSON before rebuild.
- Keep the glossary growing across batches so later batches translate consistently with earlier ones.
- Always rebuild from the merged cache only — never run rebuild against a partial cache, since the script will fail-closed and write a `.missing.txt`.

## Table-Cell Sweep

Tables are the highest-risk surface for over-translation. After rendering, on every dense table page check:

- Company names (e.g. `Apple Inc.`, `Goldman Sachs`) appear in English, not as `苹果公司` / `高盛`, unless the document's convention says otherwise.
- Tickers and exchange codes (e.g. `AAPL`, `NYSE:MSFT`, `005930.KS`) are untouched.
- Product / model names (e.g. `iPhone 15`, `Model Y`, `A100`, `GPT-4`) are untouched.
- Region / country codes (`US`, `EU`, `APAC`, `EMEA`) are untouched unless explicitly translated elsewhere.
- Header cells like `Rank`, `Symbol`, `Sector`, `Weight` are translated consistently across every table.

When you find a table cell that should have stayed English: add the source string to the glossary's `keep_as_source` list, delete its entry from the cache (or set value=source), and rerun the rebuild step. Do **not** rely on `--no-auto-preserve` to fix this — that just disables the heuristic globally.

## Editing Postprocessing

`postprocess_translation` in the script applies a few generic Argos-era cleanups (Wikipedia archive footnotes, `(英语:...)` tails, etc.). Do **not** add unconditional `replace()` calls for real Chinese words there — they will silently corrupt valid translations across all future PDFs. Document-specific bad terms belong in the glossary's `bad_terms` list (warning only) or `replacements` list (substitution).

## Suggested Comparison Pages

Render the cover or opening page, one or two dense text pages, two dense table pages if present, one chart/figure page if present, and the first and last appendix/legal/disclaimer pages if present.

## Box Preview Review

When reviewing `text_boxes_pXX.png`:

- Orange boxes should cover all visible English text that needs translation.
- Important text with no box means extraction missed it; consider OCR or manual handling.
- Many tiny boxes inside one sentence may lead to choppy translation; use exact cache overrides for affected lines.
- Boxes crossing table borders or chart graphics need careful final QA.
- Green boxes should correspond to glossary or cache entries already translated or intentionally preserved.

## Bad-Term Sweep

Search the generated translation cache and output text for obvious artifacts. If these appear, fix the cache with the LLM and rerun the renderer:

```text
流行音乐节
拉布邦
互联网档案馆
闪光闪光
第三、第三
中文(简体)
英语:
低级
表现不佳
非机密
非秘密
```
