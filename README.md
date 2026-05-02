# PDF Visual Translate ZH

**Visually faithful English-to-Chinese PDF translation that preserves layout, tables, charts, colors, and page geometry.**

[中文说明](#中文说明) | [English](#english)

---

## 中文说明

### 这是什么

一个 PDF 视觉翻译工具，把英文 PDF 翻译成中文，同时保持原文档的视觉外观——页面尺寸、页数、表格、图表、配色、页眉页脚全部不变。

与传统翻译工具不同，本工具采用**视觉覆盖**方式：在原 PDF 上采样局部背景色，覆盖英文文本，再在相同坐标绘制中文。适合报告、研报、白皮书、披露文件等对排版有要求的场景。

### 工作原理

```
英文 PDF → 预检诊断 → 提取文本坐标 → 分批导出 → LLM 翻译 → 合并缓存 → 视觉覆盖重建 → QA 验证 → 中文 PDF
```

核心设计：
- **不破坏原始 PDF**：以原文件为视觉底层，在上方覆盖翻译
- **LLM 优先翻译**：导出紧凑批次给 AI 翻译，而非机器翻译
- **文件级状态管理**：翻译缓存、术语表、批次文件持久化在磁盘上，不依赖聊天上下文
- **智能保留**：自动识别品牌名、股票代码、产品名等应保留英文的内容

### 快速开始

**安装依赖：**

```bash
pip install pymupdf pillow
```

**1. 诊断 PDF：**

```bash
python3 scripts/diagnose_pdf.py --source your-report.pdf
```

**2. 导出翻译批次：**

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --glossary references/glossary-template.json \
  --cache /tmp/translations.json \
  --export-batch /tmp/batch-001.json \
  --batch-index 0 --batch-size 60
```

**3. 翻译批次内容**（使用任何 LLM），生成 patch JSON：

```json
{
  "Original English text": "对应的中文翻译"
}
```

**4. 合并翻译并重建：**

```bash
# 合并翻译
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --cache /tmp/translations.json \
  --merge-patch /tmp/batch-001.patch.json

# 重建中文 PDF
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --output /tmp/output-zh.pdf \
  --cache /tmp/translations.json \
  --glossary references/glossary-template.json \
  --render-dir /tmp/qa \
  --compare-pages 1,4,8
```

### 项目结构

```
pdf-visual-translate-zh/
├── README.md                          # 本文件
├── SKILL.md                           # Cowork/Claude skill 定义
├── REFERENCE.md                       # 高级场景参考（OCR、修复、表单等）
├── requirements.txt                   # Python 依赖
├── scripts/
│   ├── visual_translate_pdf.py        # 核心翻译引擎（导出、合并、重建）
│   ├── diagnose_pdf.py                # PDF 预检诊断
│   └── render_text_box_preview.py     # 文本框可视化预览
├── references/
│   ├── glossary-template.json         # 术语表模板
│   └── pdf-translation-qa.md          # QA 检查清单与常见问题
└── examples/
    └── glossary-example.json          # 术语表使用示例
```

### 脚本说明

| 脚本 | 用途 |
|------|------|
| `diagnose_pdf.py` | 预检：检测文本密度、扫描件、加密、表单、注释、旋转页等 |
| `visual_translate_pdf.py --inspect` | 查看 PDF 元数据（页数、尺寸、字体） |
| `visual_translate_pdf.py --export-batch` | 导出紧凑翻译批次供 LLM 翻译 |
| `visual_translate_pdf.py --merge-patch` | 将翻译补丁合并到缓存 |
| `visual_translate_pdf.py --output` | 重建中文覆盖 PDF |
| `render_text_box_preview.py` | 渲染文本框预览图（绿色=已翻译，橙色=待翻译） |

### 作为 Cowork Skill 使用

本项目可以作为 Claude Cowork 的 skill 使用。将整个文件夹复制到 `~/.claude/skills/pdf-visual-translate-zh-enhanced/` 即可：

```bash
mkdir -p ~/.claude/skills/pdf-visual-translate-zh-enhanced
cp -r . ~/.claude/skills/pdf-visual-translate-zh-enhanced/
```

重启 Cowork 后，skill 会自动加载。

### 局限性

- **覆盖模式**：隐藏的文本层仍为英文，复制/搜索时会看到英文原文
- **扫描件**：纯图片 PDF 需先 OCR 再使用本工具
- **表单字段**：页面文本翻译不会更新 AcroForm 字段值
- **注释**：弹出式注释内容不会被翻译

---

## English

### What is this

A PDF visual translation tool that converts English PDFs to Chinese while preserving the original document's visual appearance -- page size, page count, tables, charts, colors, headers, and footers all remain intact.

Unlike conventional translation tools, this uses a **visual overlay** approach: it samples the local background color around each English text line, covers it, and draws Chinese text at the same coordinates. Ideal for reports, research notes, white papers, and disclosure documents where layout fidelity matters.

### How it works

```
English PDF → Preflight diagnosis → Extract text coordinates → Export batches
→ LLM translation → Merge cache → Visual overlay rebuild → QA verification → Chinese PDF
```

### Quick start

```bash
# Install dependencies
pip install pymupdf pillow

# 1. Diagnose
python3 scripts/diagnose_pdf.py --source report.pdf

# 2. Export a translation batch
python3 scripts/visual_translate_pdf.py \
  --source report.pdf \
  --export-batch /tmp/batch.json \
  --batch-index 0 --batch-size 60

# 3. Translate the batch with any LLM, save as patch JSON

# 4. Merge and rebuild
python3 scripts/visual_translate_pdf.py \
  --source report.pdf \
  --cache /tmp/cache.json \
  --merge-patch /tmp/patch.json

python3 scripts/visual_translate_pdf.py \
  --source report.pdf \
  --output /tmp/output-zh.pdf \
  --cache /tmp/cache.json
```

### Key features

- **Non-destructive**: original PDF serves as the visual base layer
- **LLM-first translation**: exports compact batches for AI translation, not machine translation
- **File-backed state**: translation cache, glossary, and batch files persist on disk
- **Smart preservation**: auto-detects brand names, tickers, and product names to keep in English
- **Visual QA**: comparison renders and text-box previews before delivery
- **Batch workflow**: handles large PDFs by translating in manageable chunks

### Limitations

- Overlay mode: the hidden text layer remains in English (copy/search shows English)
- Scanned PDFs require OCR before use
- Form field values and annotation contents are not translated

## License

MIT
