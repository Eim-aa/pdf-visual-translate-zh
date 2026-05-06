# PDF Visual Translate · 英文 PDF 版式保真中文翻译 Skill

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20%2F%20Codex-6f42c1)](SKILL.md)
[![Made for Chinese readers](https://img.shields.io/badge/%E4%B8%AD%E6%96%87%E7%94%A8%E6%88%B7-%E4%BC%98%E5%85%88-red)](README.md)

**一个适配 Claude Code / Codex 等 Agent 环境的英文 PDF 中文翻译 Skill，用于把研报、公告、合同、白皮书和图表密集 PDF 转成更接近原版式的中文交付件。**

它优先保留页面尺寸、页数、表格、图表、配色、页眉页脚和页面结构，适合“内容要中文，版式不能乱”的材料。

[English README](README.en.md) | [高级参考](REFERENCE.md) | [QA 检查清单](references/pdf-translation-qa.md) | [Skill 使用说明](SKILL.md)

---

## 为什么会需要它

很多 PDF 翻译工具能翻文本，但一遇到表格、图表、页眉页脚、脚注和多栏报告，版式就容易被打散。这个项目走的是另一条路线：

- 不把 PDF 重排成新文档，而是在原页面坐标上做中文视觉覆盖。
- 不绑定某一个翻译模型，任何能输出 JSON 的 LLM 都可以接入。
- 不依赖一次性长上下文，长文档可以分批翻译、缓存、恢复和复查。
- 不只输出 PDF，还会生成页面渲染对照图，方便交付前做视觉 QA。

一句话：它更像一个“PDF 中文交付工作流”，不是普通在线翻译器。

## 30 秒判断

| 你的材料或目标 | 是否适合 | 建议 |
|---|---:|---|
| 英文 PDF 可以选中文本，且希望保留原排版 | 很适合 | 直接使用本项目 |
| 研报、公告、白皮书、合同、图表密集 PDF | 很适合 | 先跑诊断，再分批翻译 |
| 扫描件或纯图片 PDF | 暂不直接适合 | 先 OCR，再使用本项目 |
| 必须复制和搜索中文文本层 | 需要额外处理 | 本项目优先可视中文，不保证隐藏文本层变中文 |
| 只想把文字导出成 Markdown | 不太适合 | 用普通 PDF 文本抽取工具更轻 |

## 核心亮点

- **版式优先**：尽量保持页数、页面尺寸、图表、表格、配色、页眉页脚和页面几何结构。
- **分批翻译**：导出紧凑 batch，让 LLM 逐批翻译，降低长文档失败率。
- **缓存可恢复**：翻译状态写入 JSON，失败后可以继续，不必重来。
- **术语保护**：品牌名、股票代码、产品名、数据来源、URL、邮箱、数字和短代码默认倾向保留。
- **视觉 QA**：生成对照渲染图，方便检查残留英文、白块、字号、表格和图表页。
- **可作为 Skill 使用**：适配 Claude/Codex 一类智能体，把复杂 PDF 翻译流程变成可复用工作流。

## 一分钟开始

```bash
git clone https://github.com/Eim-aa/pdf-visual-translate-zh.git
cd pdf-visual-translate-zh
python3 -m pip install -r requirements.txt
```

先诊断 PDF：

```bash
python3 scripts/diagnose_pdf.py --source your-report.pdf
```

如果诊断显示文本密度很低，通常说明 PDF 是扫描件或图片型 PDF，需要先 OCR。

## 标准工作流

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

### 1. 准备术语表和缓存

```bash
WORK="/tmp/pdf-visual-translate-zh"
mkdir -p "$WORK"
cp references/glossary-template.json "$WORK/glossary.json"
```

### 2. 导出第一个翻译批次

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

### 3. 用 LLM 翻译批次

把批次里的 `items` 翻译成 patch JSON。键必须保持英文原文完全一致，值写中文译文：

```json
{
  "Exact English source string": "简洁、准确、能放回原坐标的中文"
}
```

### 4. 合并翻译补丁

```bash
python3 scripts/visual_translate_pdf.py \
  --source your-report.pdf \
  --cache "$WORK/translations.json" \
  --merge-patch "$WORK/batch-001.patch.json"
```

继续用 `--batch-index 0` 导出下一批。脚本会跳过已经有翻译的缓存项，所以索引 `0` 表示“下一批未翻译内容”。

### 5. 重建中文 PDF

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

## 作为 Agent Skill 安装

这个仓库可以直接作为 Claude/Codex 一类智能体的 PDF 翻译 Skill 使用。

| 环境 | 推荐安装位置 | 示例 |
|---|---|---|
| Claude Code | `~/.claude/skills/pdf-visual-translate-zh-skill` | `git clone https://github.com/Eim-aa/pdf-visual-translate-zh.git ~/.claude/skills/pdf-visual-translate-zh-skill` |
| Codex | `$CODEX_HOME/skills/pdf-visual-translate-zh-skill` 或 `~/.codex/skills/pdf-visual-translate-zh-skill` | `git clone https://github.com/Eim-aa/pdf-visual-translate-zh.git ~/.codex/skills/pdf-visual-translate-zh-skill` |

安装后可以这样对智能体说：

```text
使用 pdf-visual-translate-zh-skill，把 /path/to/report.pdf 翻译成中文 PDF。
优先保持原 PDF 的页数、表格、图表、颜色和页面结构。
翻译过程使用分批缓存，并在交付前输出 QA 对照图。
```

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

## 常见限制

- **隐藏文本层仍可能是英文**：可视输出是中文，但复制和搜索可能仍命中英文原文。
- **扫描件需要 OCR**：纯图片 PDF 不能直接靠文本坐标覆盖，需要先生成文本层。
- **表单字段不会自动改写**：AcroForm 字段值需要单独检查。
- **注释内容不会自动翻译**：弹出式注释、批注和附件元数据不属于页面文本覆盖范围。
- **长文本可能需要人工压缩**：中文必须能放回原坐标，密集表格和脚注尤其需要简短译文。

## 路线图

- 增加可公开演示的 before/after 示例 PDF 和渲染图。
- 增加一条命令完成“导出批次 -> 合并补丁 -> 重建 -> QA”的编排脚本。
- 探索 OCR 后处理路线，让扫描件也能进入同一工作流。
- 探索可搜索中文文本层重建，减少隐藏英文文本层带来的限制。

## 适合收藏的人

如果你经常处理英文研报、行业报告、上市公司公告、白皮书、合同或图表密集 PDF，这个项目可以作为一个可复用的中文交付工作流收藏起来。

## 许可证

MIT
