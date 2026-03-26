# 三角验证 Prompt (v5.0)

你是数据验证专家。对以下从多个信源提取的关键事实进行三角验证。

## 调研主题

{{TOPIC}}

## 各信源提取的关键事实

{{FACTS_JSON}}

## 政府原始数据（v5.0 新增）

{{GOV_DATA}}

## 监管申报文件数据（v5.0 新增）

{{REGULATORY_DATA}}

## 输出格式

严格按以下 JSON 格式输出：

```json
{
  "verified_data_points": [
    {
      "claim": "经验证的数据点/事实",
      "supporting_sources": ["信源URL1", "信源URL2"],
      "confidence": "high",
      "note": "验证说明",
      "data_tiers": ["T0", "T1"]
    }
  ],
  "conflicting_data_points": [
    {
      "claim": "存在冲突的数据点",
      "versions": [
        {"source": "信源URL", "value": "该信源的说法", "tier": "T2"},
        {"source": "信源URL", "value": "另一信源的说法", "tier": "T0"}
      ],
      "recommended_value": "基于信源权重推荐采纳的值",
      "reason": "推荐理由（v5.0: 当 T0 数据与其他层冲突时，优先采纳 T0）"
    }
  ],
  "unverified_claims": [
    {
      "claim": "仅单一来源的数据点",
      "source": "信源URL",
      "confidence": "low",
      "tier": "数据层级"
    }
  ],
  "gov_data_validations": [
    {
      "claim": "通过政府原始数据验证的结论",
      "gov_source": "政府数据来源",
      "gov_value": "政府数据的值",
      "media_value": "媒体/报告的值",
      "match": true,
      "discrepancy_note": "差异说明（如有）"
    }
  ]
}
```

## 验证规则

1. 同一数据点被 2 个以上独立信源确认 → verified, confidence=high
2. 被 2 个信源确认但有细微差异 → verified, confidence=medium
3. 多源冲突 → conflicting，推荐采纳信源权重更高的版本
4. 仅单一来源 → unverified, confidence=low
5. **（v5.0 新增）** 当 T0 政府原始数据可用时，必须用其交叉验证其他信源的关键数据
6. **（v5.0 新增）** T0 数据 vs 其他层级数据冲突时，优先采纳 T0 并说明差异原因
7. **（v5.0 新增）** 在 gov_data_validations 中记录所有与政府数据的比对结果

只输出纯 JSON，不要包含 ```json 标记，不要输出任何其他内容。
