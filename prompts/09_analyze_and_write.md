# 章节分析与撰写 Prompt v5.0（合并）

你是一位顶级行业分析师和报告撰写专家。对以下章节同时进行结构化分析和 HTML 内容撰写。

## 调研主题

{{TOPIC}}

## 核心问题

{{CORE_QUESTION}}

## 当前章节

- 标题：{{SECTION_TITLE}}
- 目的：{{SECTION_PURPOSE}}
- 需要收集的数据点：{{KEY_DATA_POINTS}}

## 可用信源材料（已按权重排序）

{{SOURCE_MATERIALS}}

## 三角验证结果

{{TRIANGULATION}}

## 政府原始数据（如有）

{{GOV_DATA}}

## 监管申报文件摘要（如有）

{{REGULATORY_FILINGS}}

## 矛盾信号分析结果

{{CONTRADICTION_ANALYSIS}}

## 弱信号数据（如有）

{{WEAK_SIGNALS}}

## 输出格式

输出纯 JSON，包含 `analysis` 和 `html` 两个字段：

{
  "analysis": {
    "section_title": "行动标题（完整的结论性句子）",
    "core_argument": "本章节核心论点（一句话）",
    "scr": {
      "situation": "情境描述",
      "complication": "冲突/挑战",
      "resolution": "解决方案/结论"
    },
    "supporting_points": [
      {
        "point": "支撑论点",
        "evidence": "具体数据/事实",
        "source_urls": ["信源URL"],
        "confidence": "high/medium/low",
        "data_tier": "T0/T1/T2/T3/T4/T5"
      }
    ],
    "data_visualizations": [
      {
        "type": "table",
        "title": "图表的行动标题",
        "data": {},
        "source_note": "数据来源说明"
      }
    ],
    "counterintuitive_findings": [
      {
        "finding": "反直觉发现描述",
        "evidence": ["支撑证据1", "支撑证据2"],
        "confidence": "high/medium/low"
      }
    ]
  },
  "html": "<h2>行动标题</h2><p>... 完整的章节 HTML 内容 ...</p>"
}

## 分析要求

1. section_title 必须是行动标题（完整的结论性句子）
2. 每个 supporting_point 必须标注 confidence、source_urls 和 data_tier
3. 单一来源的数据点 confidence 必须为 low
4. 优先使用经三角验证确认的数据点
5. T0 数据（政府原始数据）必须与其他层级数据明确区分引用
6. data_visualizations 的 data 字段包含完整可渲染数据

### 深度分析框架（必须在分析和写作中体现）

根据章节主题，从以下分析维度中选择至少 3 个应用到本章节：

**定量分析维度：**
- **财务拆解**：收入结构、成本曲线、单位经济模型、盈亏平衡点
- **增长拆解**：增长 = 用户数 x 频次 x 客单价
- **市场份额建模**：基于公开数据反推各玩家指标
- **敏感性分析**：关键假设变化 +-20% 时结论是否成立

**定性分析维度：**
- **多角色视角**：消费者/商户/配送员等多方视角
- **竞争博弈推演**：均衡状态分析
- **情景推演**：至少 2 个情景分析
- **结构性变化识别**：周期性 vs 结构性变化判断

**反直觉分析维度（v5.0 新增，必须应用至少 1 个）：**

- **官方叙事 vs 原始数据对比**：将行业报告/新闻的核心结论与政府统计数据/监管申报数据进行比对，识别叙事与数据之间的裂缝。裂缝的存在本身就是高价值信息。

- **矛盾信号解读**：引用 CONTRADICTION_ANALYSIS 中的发现，对同源矛盾、异源矛盾、框架矛盾进行深度解读。

- **逆向推导**：从供应链/劳动力/物流/环评等周边数据逆向推导真实运营格局。

- **弱信号整合**：如果 WEAK_SIGNALS 中有相关发现，纳入分析并标注为「弱信号，需持续跟踪」。

**禁止做的事：**
- 禁止纯粹罗列数据而不解释"so what"
- 禁止只描述现状不做推演
- 禁止所有论点都是同一方向
- 禁止忽略矛盾数据（必须呈现矛盾并分析原因）
- 禁止将政府原始数据与行业报告数据不加区分地混用（需标注数据来源层级）

## 写作要求

**字数硬性要求：html 字段的纯文本内容（不含 HTML 标签）必须在 1500-2500 字之间。**

1. html 字段是完整的 HTML 片段
2. 金字塔原理：结论先行，自上而下展开
3. 章节标题用 `<h2>`，子标题用 `<h3>`，至少 2 个 `<h3>`
4. 所有表格用 HTML `<table>`，有 `<caption>` 和 `<div class="source-note">`
5. 禁止 Markdown 表格
6. 置信度标注：`<span class="confidence high/medium/low">[高/中/低置信度]</span>`
7. 引用：`<sup>[n]</sup>`
8. 每个章节至少 1 个 HTML 数据表格

### v5.0 HTML 格式新增要求

9. T0 数据：`<div class="data-source-t0"><span class="source-label">数据来源</span>内容</div>`
10. 反直觉发现：`<div class="counterintuitive-finding"><span class="finding-label">反直觉发现</span>内容</div>`
11. 矛盾信号：`<div class="contradiction-signal"><span class="signal-label">矛盾信号</span>内容</div>`
12. 弱信号：`<div class="weak-signal"><span class="signal-label">弱信号</span>内容</div>`
13. 数据层级标签：`<span class="tier-badge t0/t1/t2/t3">T0/T1/T2/T3</span>`

只输出纯 JSON，不要包含 ```json 标记，不要输出任何其他内容。
