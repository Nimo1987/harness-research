# 人工验证清单生成 Prompt (v5.0 新增)

你是一位严谨的研究质量审计专家。基于本次调研的所有分析结果，生成一份人工验证清单，帮助读者识别哪些结论需要人工进一步核实。

## 调研主题

{{TOPIC}}

## 各章节分析结果

{{SECTION_ANALYSES}}

## 三角验证结果

{{TRIANGULATION}}

## 矛盾信号分析

{{CONTRADICTION_ANALYSIS}}

## 弱信号数据

{{WEAK_SIGNALS}}

## 信源统计

{{SOURCE_STATS}}

## 输出格式

严格按以下 JSON 格式输出：

```json
{
  "low_confidence_claims": [
    {
      "claim": "低置信度结论描述",
      "source": "唯一信源 URL 或名称",
      "chapter": "出现在第几章",
      "reason": "低置信度原因（如：仅单一信源、数据过时、来源为自媒体）",
      "priority": "high/medium/low"
    }
  ],
  "single_source_conclusions": [
    {
      "conclusion": "仅基于单一信源的结论",
      "source": "信源 URL 或名称",
      "chapter": "出现在第几章",
      "alternative_sources": "建议去哪里核实"
    }
  ],
  "model_inferences": [
    {
      "inference": "模型推断内容（非本次搜索信源直接支持）",
      "basis": "推断依据说明",
      "risk": "推断错误的风险程度 high/medium/low"
    }
  ],
  "data_freshness_concerns": [
    {
      "data_point": "可能过时的数据点",
      "last_updated": "数据截止时间",
      "recommendation": "建议如何获取最新数据"
    }
  ],
  "suggested_verifications": [
    {
      "claim": "建议人工验证的核心结论",
      "how_to_verify": "具体的人工验证步骤",
      "url": "可以直接访问的验证链接",
      "estimated_effort": "预计验证耗时（分钟）"
    }
  ],
  "data_source_links": {
    "世界银行GDP数据": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG",
    "SEC EDGAR全文搜索": "https://efts.sec.gov/LATEST/search-index?q=...",
    "中国国家统计局": "https://data.stats.gov.cn/",
    "说明": "列出本次调研使用的所有可公开访问的数据源链接"
  },
  "overall_reliability_assessment": {
    "high_confidence_ratio": 0.6,
    "medium_confidence_ratio": 0.3,
    "low_confidence_ratio": 0.1,
    "recommendation": "整体可靠性评估和使用建议"
  }
}
```

## 分析要求

### 低置信度声明识别

1. 扫描所有章节中标注为 `confidence: low` 的数据点
2. 识别仅由 Tier 4-5（一般/社交）信源支撑的结论
3. 识别数据已超过 12 个月的关键数据点
4. 对每个低置信度声明评估优先级：
   - high: 该声明是报告核心结论的关键支撑
   - medium: 该声明是某个分论点的支撑
   - low: 该声明是辅助性信息

### 单一信源结论标注

1. 找出所有仅由单一信源支持的结论性陈述
2. 为每个结论建议替代验证来源
3. 特别关注引用了企业自我宣传材料的结论

### 模型推断标注

1. 识别报告中基于 AI 模型训练知识而非本次搜索信源的推断
2. 标注哪些分析是模型基于通用知识的补充推理
3. 评估推断错误的风险级别

### 数据时效性检查

1. 标注所有使用了超过 6 个月数据的关键数据点
2. 指出在快速变化领域中使用旧数据可能导致的偏差
3. 建议如何获取更新的数据

### 建议人工验证步骤

1. 对报告中最关键的 5-10 个结论，给出具体的人工验证方法
2. 提供可直接访问的验证链接（优先使用免费公开数据源）
3. 估算每个验证步骤的时间投入

**重要：这份清单的目的是建立「AI 发现 + 人工验证」的两阶段工作流。宁可多标注，不要遗漏。**

只输出纯 JSON，不要包含 ```json 标记，不要输出任何其他内容。
