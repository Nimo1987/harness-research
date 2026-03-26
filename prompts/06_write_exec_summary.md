# 执行摘要撰写 Prompt (v5.0)

你是一位顶级研究报告撰写专家。基于以下分析结果，撰写执行摘要。

## 调研主题

{{TOPIC}}

## 核心问题

{{CORE_QUESTION}}

## 各章节核心论点

{{SECTION_SUMMARIES}}

## 反直觉发现汇总（v5.0 新增）

{{COUNTERINTUITIVE_FINDINGS}}

## 写作规范

1. 严格遵循 SCR 框架（Situation → Complication → Resolution）
2. 第一段直接给出核心结论/建议（The Answer）
3. 后续段落展开 3-5 个关键支撑点
4. **（v5.0 新增）新增一段「反直觉发现」摘要**：从 COUNTERINTUITIVE_FINDINGS 中选取 1-3 个最有价值的发现，用一段专门的文字呈现。如果没有反直觉发现，说明所有数据一致（这本身值得注意）。
5. 最后一段给出"So What"——影响和建议的下一步行动
6. 总长度 800-1200 字（硬性要求，低于 800 字视为不合格）
7. 必须包含一个关键指标对比的 HTML 汇总表格

## 格式规范

1. 输出纯 HTML 片段（不含 html/head/body 标签）
2. 使用 `<h2>` 作为章节标题
3. 所有表格使用 HTML `<table>` 标签，禁止 Markdown 表格
4. 关键数据标注置信度：`<span class="confidence high/medium/low">[高/中/低置信度]</span>`
5. 引用使用 `<sup>[n]</sup>` 格式
6. **（v5.0 新增）** 反直觉发现使用 `<div class="counterintuitive-finding"><span class="finding-label">反直觉发现</span>内容</div>` 格式

只输出纯 HTML 片段，不要包含 ```html 标记，不要输出任何其他内容。
