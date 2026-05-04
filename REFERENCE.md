# PDF 视觉翻译高级参考

[English version](REFERENCE.en.md)

这份文档收集难处理 PDF 的补救路线。日常使用优先看 `README.md` 和 `SKILL.md`；只有当诊断或 QA 暴露出特殊问题时，再查这里。

## 预检决策表

| 信号 | 含义 | 建议动作 |
|---|---|---|
| 可提取文本密度很低 | 扫描件或图片型 PDF | 先 OCR，再重新诊断 |
| 需要密码 | 文本提取和渲染可能被阻止 | 请用户提供密码或解密后的 PDF |
| 检测到表单组件 | 可见英文可能存在于 AcroForm 字段中 | 单独检查表单字段值 |
| 检测到注释 | 弹窗、批注或评论可能仍是英文 | 必要时单独提取并翻译注释 |
| 检测到旋转页 | 坐标映射风险更高 | 对这些页面渲染文本框预览 |
| 页面尺寸混杂 | QA 页面必须覆盖每种尺寸 | 对每种尺寸选择样张渲染对比 |
| 大量碎片化小文本框 | 文本抽取被切碎 | 对受影响行使用精确缓存覆盖 |

## OCR 路线

扫描件需要先生成文本层，再走视觉翻译流程。

优先命令：

```bash
ocrmypdf --deskew --rotate-pages input.pdf ocr-output.pdf
```

备选路线：

```bash
pdftoppm -png -r 300 input.pdf page
tesseract page-1.png page-1 -l eng pdf
```

OCR 后重新诊断：

```bash
python3 scripts/diagnose_pdf.py --source ocr-output.pdf
python3 scripts/visual_translate_pdf.py --inspect --source ocr-output.pdf
```

只有当文本密度合理、文本框预览能覆盖主要可见英文时，才继续后续翻译。

## 抽取失败时的诊断工具

如果 PyMuPDF 漏抽文本或把句子切得很碎，可以用其他工具辅助判断 PDF 结构。

导出带坐标 XML：

```bash
pdftotext -bbox-layout input.pdf bbox.xml
```

导出版面文本：

```bash
pdftotext -layout input.pdf layout.txt
```

检查表格结构：

```python
import pdfplumber

with pdfplumber.open("input.pdf") as pdf:
    page = pdf.pages[0]
    print(page.extract_text())
    print(page.extract_tables())
```

这些工具只用于诊断。正常重建仍使用 `visual_translate_pdf.py`，除非后续专门写新的抽取适配器。

## PDF 修复

如果 PDF 无法打开、渲染不稳定，或对象结构损坏：

```bash
qpdf --check input.pdf
qpdf input.pdf repaired.pdf
```

然后对 `repaired.pdf` 重新诊断和翻译。

## 表单与注释

页面覆盖翻译只改变页面外观，不会自动改写：

- AcroForm 字段值
- 注释弹窗内容
- 嵌入附件
- 隐藏元数据

如果这些内容对交付很重要，需要单独提取、翻译，并决定是更新 PDF 结构还是在交付说明里明确标注未处理范围。

## 文本框预览规则

批量翻译前，先用 `render_text_box_preview.py` 检查代表性页面。

- 橙色框应覆盖仍需翻译的可见英文。
- 绿色框应对应已有术语表或缓存翻译。
- 重要文字没有框，通常说明需要 OCR 或换抽取策略。
- 穿过图表、表格边线的框，需要最终人工 QA。
- 很短的小框可能需要更短的中文缓存覆盖。

## QA 页面选择

至少覆盖这些页面：

- 封面或开篇页
- 第一页密集正文
- 有代表性的表格页，尤其是彩色表头、热力图或数字密集页
- 有代表性的图表或插图页
- 第一页和最后一页法律、附录、披露或脚注密集页
- 诊断中提示的旋转页或特殊尺寸页

## 交付说明

交付覆盖翻译 PDF 时，应该说明：

- 可视输出是否已经是中文。
- 隐藏文本层或搜索/复制结果是否仍可能包含英文。
- 扫描页、表单字段、注释或附件是否被排除，或者是否已单独处理。
