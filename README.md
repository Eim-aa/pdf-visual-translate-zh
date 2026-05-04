# PDF 视觉翻译中文工具

**面向中文用户的英文 PDF 版式保真翻译工具：把英文报告、研报、白皮书、披露文件等转换为中文 PDF，同时尽量保持页面尺寸、页数、表格、图表、配色和版面结构不变。**

[English README](README.en.md) | [高级参考](REFERENCE.md) | [QA 检查清单](references/pdf-translation-qa.md)

---

## 这是什么

这是一个 PDF 视觉翻译工作流。它不尝试把 PDF 重新排版成一个全新的文档，而是在原 PDF 的视觉层上工作：提取英文文本和坐标，采样局部背景色覆盖原文，再把简洁中文绘制回相同位置。

它适合这类材料：

- 金融研报、行业报告、公司公告、披露文件
- 带大量表格、图表、页眉页脚和脚注的 PDF
- 需要中文可读性，但又不能破坏原版式的资料
- 需要用 LLM 分批翻译，并保留术语表、缓存和 QA 记录的大型 PDF

## 设计取舍

这个项目优先保证“看起来像原 PDF 的中文版本”，不是优先生成一个干净、可搜索、可复制的中文文本层。

- **版式保真**：页数、页面尺寸、表格、图表、颜色和页眉页脚尽量保持不变。
- **视觉覆盖**：原英文通常仍在底层文本层中，复制或搜索时可能看到英文。
- **LLM 优先**：脚本负责导出批次、合并缓存和重建 PDF；翻译本身交给你选择的 LLM。
- **文件化状态**：翻译缓存、术语表、批次文件和 QA 输出都落到磁盘，适合长文档反复迭代。
- **术语保护**：品牌名、股票代码、产品名、数据源、URL、邮箱、数字和短代码默认倾向保留。

## 工作流程

```text
英文 PDF
  -> 预检诊断
  -> 提取文本和坐标
  -> 导出翻译批次
  -> LLM 翻译为 patch JSON
  -> 合并翻译缓存
  -> 视觉覆盖重建
  -> 渲染对照图 QA
  -> 中文 PDF
```

## 安装

建议使用 Python 3.10 或更新版本。

```bash
pip install -r requirements.txt
```

当前核心依赖：

```text
pymupdf
pillow
```

## 快速开始

### 1. 诊断 PDF

```bash
python3 scripts/diagnose_pdf.py --source your-report.pdf
```

如果诊断显示文本密度很低，通常说明 PDF 是扫描件或图片型 PDF，需要先 OCR。

### 2. 准备术语表和缓存

```bash
WORK="/tmp/pdf-visual-translate-zh"
mkdir -p "$WORK"
cp references/glossary-template.json "$WORK/glossary.json"
```

### 3. 导出第一个翻译批次

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

### 4. 用 LLM 翻译批次

把批次里的 `items` 翻译成 patch JSON。键必须保持英文原文完全一致，值写中文译文：

```json
{
  "Exact English source string": "简洁、准确、能放回原坐标的中文"
}
```

### 5. 合并翻译补丁

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --cache "$WORK/translations.json" \
  --merge-patch "$WORK/batch-001.patch.json"
```

继续用 `--batch-index 0` 导出下一批。脚本会跳过已经有翻译的缓存项，所以索引 `0` 表示“下一批未翻译内容”。

### 6. 重建中文 PDF

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --output "$WORK/output-zh.pdf" \
  --cache "$WORK/translations.json" \
  --glossary "$WORK/glossary.json" \
  --render-dir "$WORK/qa" \
  --compare-pages 1,4,8
```

`--render-dir` 会输出对照渲染图，建议在交付前检查封面、正文页、密集表格页、图表页和法律/披露页。

## 项目结构

```text
pdf-visual-translate-zh/
├── README.md                          # 中文默认说明
├── README.en.md                       # English README
├── SKILL.md                           # 中文 Skill 使用说明
├── SKILL.en.md                        # English Skill guide
├── REFERENCE.md                       # 中文高级参考
├── REFERENCE.en.md                    # English advanced reference
├── requirements.txt                   # Python 依赖
├── scripts/
│   ├── visual_translate_pdf.py        # 核心引擎：导出、合并、重建
│   ├── diagnose_pdf.py                # PDF 预检诊断
│   └── render_text_box_preview.py     # 文本框可视化预览
├── references/
│   ├── glossary-template.json         # 术语表模板
│   ├── pdf-translation-qa.md          # 中文 QA 检查清单
│   └── pdf-translation-qa.en.md       # English QA checklist
└── examples/
    └── glossary-example.json          # 术语表示例
```

## 脚本说明

| 脚本或命令 | 用途 |
|---|---|
| `scripts/diagnose_pdf.py` | 预检 PDF：文本密度、扫描件、加密、表单、注释、旋转页、混合页面尺寸等 |
| `scripts/visual_translate_pdf.py --inspect` | 查看面向翻译的 PDF 元数据 |
| `scripts/visual_translate_pdf.py --export-batch` | 导出紧凑翻译批次，供 LLM 翻译 |
| `scripts/visual_translate_pdf.py --merge-patch` | 把一个 patch JSON 合并进翻译缓存 |
| `scripts/visual_translate_pdf.py --output` | 根据缓存重建中文覆盖 PDF |
| `scripts/render_text_box_preview.py` | 渲染文本框预览图，检查哪些文字会被覆盖和翻译 |

## 作为 Skill 使用

这个仓库也可以作为 Claude/Codex 一类智能体的 PDF 翻译 Skill 使用。把整个文件夹放到对应的 skills 目录后，按 `SKILL.md` 的工作流执行即可。

示例：

```bash
mkdir -p ~/.claude/skills/pdf-visual-translate-zh-enhanced
cp -r . ~/.claude/skills/pdf-visual-translate-zh-enhanced/
```

## 常见限制

- **隐藏文本层仍可能是英文**：可视输出是中文，但复制和搜索可能仍命中英文原文。
- **扫描件需要 OCR**：纯图片 PDF 不能直接靠文本坐标覆盖，需要先生成文本层。
- **表单字段不会自动改写**：AcroForm 字段值需要单独检查。
- **注释内容不会自动翻译**：弹出式注释、批注和附件元数据不属于页面文本覆盖范围。
- **长文本可能需要人工压缩**：中文必须能放回原坐标，密集表格和脚注尤其需要简短译文。

## 许可证

MIT
