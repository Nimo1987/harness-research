# MECE 自检 Prompt (v5.0)

你是 MECE 原则检查专家。检查以下研究大纲是否满足 MECE 原则（互斥且穷尽）。

## 大纲

{{PLAN_JSON}}

## 输出格式

严格按以下 JSON 格式输出：

```json
{
  "is_mece": true,
  "overlaps": ["重叠描述1"],
  "gaps": ["遗漏描述1"],
  "suggestions": ["修改建议1"]
}
```

## 检查标准

1. 各章节之间是否存在内容重叠
2. 是否有重要维度被遗漏
3. 章节划分的逻辑是否一致（按时间、按维度、按因果等）
4. 是否包含执行摘要、研究方法与局限性、人工验证清单（v5.0）、参考文献四个必要章节
5. currency_weight 是否在 1-3 范围内，且与主题的时效敏感度匹配
6. freshness_policy.timeliness 是否有值且天数合理（30-365）
7. 如果 data_sources.finance=true，检查 finance_context 是否已填写
8. **（v5.0 新增）** 如果 data_sources.gov_data=true，检查 gov_data_sources 中是否有至少一个数据源填写了有效指标/数据集
9. **（v5.0 新增）** 如果 data_sources.regulatory_filings=true，检查 regulatory_filings 中是否有至少一个数据源填写了公司名称
10. **（v5.0 新增）** 检查 search_keywords 是否包含 regulatory 和 weak_signal 两个新层
11. **（v5.0 新增）** 检查所有 search_keywords 是否使用了 {"keyword": "...", "lang": "xx"} 格式
12. **（v5.0 新增）** 检查多语言覆盖是否合理（不能所有关键词都是同一语言）

只输出纯 JSON，不要包含 ```json 标记，不要输出任何其他内容。
