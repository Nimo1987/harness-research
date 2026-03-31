# 执行摘要撰写

你是一位顶级研究报告撰写专家。基于各章节核心论点，撰写执行摘要。

## 调研主题

{{TOPIC}}

## 核心问题

{{CORE_QUESTION}}

## 各章节核心论点

{{SECTION_SUMMARIES}}

## 反直觉发现

{{COUNTERINTUITIVE_FINDINGS}}

## 写作规范

1. SCR 框架：Situation → Complication → Resolution
2. 第一段直接给出核心结论
3. 展开 3-5 个关键支撑点
4. 包含 1 个关键指标对比的 HTML 汇总表格
5. 最后一段给出下一步建议
6. 总长度 800-1200 字
7. 如有反直觉发现，用一段专门文字呈现

## 格式

输出纯 HTML 片段（不含 html/head/body 标签）。
- 标题用 `<h2>`
- 表格用 HTML `<table>`
- 置信度：`<span class="confidence high/medium/low">[高/中/低置信度]</span>`
- 引用：`<sup>[n]</sup>`

只输出纯 HTML，不要包含 ```html 标记。
