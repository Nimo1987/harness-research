# 研究计划生成 Prompt (v5.0)

你是一位顶级研究方法论专家。为给定的调研主题生成一份严谨的研究计划。

## 调研主题

{{TOPIC}}

## 输出格式

严格按以下 JSON 格式输出，不要输出任何其他内容：

```json
{
  "domain": "该主题所属的专业领域",
  "core_question": "本次调研要回答的核心问题（一句话）",
  "sections": [
    {
      "id": 1,
      "title": "行动标题（必须是完整的结论性句子）",
      "purpose": "本章节要回答的具体问题",
      "key_data_points": ["需要收集的关键数据点1", "关键数据点2"],
      "subsections": [
        {
          "id": "1.1",
          "title": "子章节行动标题",
          "purpose": "子章节要回答的问题"
        }
      ]
    }
  ],
  "search_keywords": {
    "background": [
      {"keyword": "背景层关键词1", "lang": "zh"},
      {"keyword": "background keyword 1", "lang": "en"},
      "至少15个关键词，覆盖多语言，每个必须标记 lang"
    ],
    "authority": [
      {"keyword": "权威层关键词1（含site:限定符）", "lang": "zh"},
      {"keyword": "authority keyword 1", "lang": "en"},
      "至少15个关键词"
    ],
    "timeliness": [
      {"keyword": "时效层关键词1（含年份）", "lang": "zh"},
      {"keyword": "timeliness keyword 1", "lang": "en"},
      "至少15个关键词"
    ],
    "academic": [
      {"keyword": "学术层关键词1", "lang": "zh"},
      {"keyword": "academic keyword 1", "lang": "en"},
      "至少15个关键词"
    ],
    "regulatory": [
      {"keyword": "监管层关键词1 site:gov.cn", "lang": "zh"},
      {"keyword": "regulatory keyword SEC filing", "lang": "en"},
      "至少10个关键词"
    ],
    "weak_signal": [
      {"keyword": "弱信号关键词1 site:linkedin.com/jobs", "lang": "zh"},
      {"keyword": "patent keyword", "lang": "en"},
      "至少10个关键词"
    ]
  },

  "currency_weight": 2,
  "freshness_policy": {
    "background": null,
    "authority": null,
    "timeliness": 90,
    "academic": 365,
    "regulatory": null,
    "weak_signal": null
  },
  "data_sources": {
    "web_search": true,
    "finance": true,
    "academic": true,
    "gov_data": true,
    "regulatory_filings": true,
    "weak_signals": true
  },
  "finance_context": {
    "stock_codes": ["sh600519", "03690.HK"],
    "data_types": ["quote", "kline"],
    "keywords": ["贵州茅台 营收", "美团 财报"]
  },

  "gov_data_sources": {
    "worldbank": {"indicators": ["NY.GDP.MKTP.KD.ZG"], "countries": ["CN", "US"], "years": 10},
    "imf": {"dataset": "WEO", "country": "CHN"},
    "fred": {"series": ["GDP", "UNRATE"], "years": 5},
    "china_stats": {"indicators": ["A0201"]},
    "oecd": {"dataset": "GREEN_GROWTH", "country": "OECD"},
    "eurostat": {"dataset": "nama_10_gdp"},
    "clinical_trials": {"condition": "", "status": ""},
    "epa": {"query": "", "state": ""},
    "data_gov": {"query": ""},
    "un_comtrade": {"reporter": "", "partner": "", "year": ""}
  },

  "regulatory_filings": {
    "sec_edgar": {"companies": ["AAPL"], "filing_types": ["10-K"]},
    "cninfo": {"companies": ["贵州茅台"], "types": ["年报"]},
    "hkex": {"companies": ["03690.HK"]},
    "edinet": {"companies": []}
  },

  "weak_signal_queries": {
    "patents": [{"query": "相关专利关键词", "years": 3}],
    "hiring": [{"company": "相关公司", "keywords": "关键岗位"}],
    "procurement": [{"query": "政府采购关键词"}],
    "academic_trend": [{"query": "学术趋势关键词", "months": 24}]
  }
}
```

## 要求

1. sections 必须遵循 MECE 原则（互斥且穷尽），数量 7-10 个
2. 第一个 section 必须是执行摘要
3. 倒数第三个 section 必须是研究方法与局限性
4. 倒数第二个 section 必须是人工验证清单（v5.0 新增）
5. 最后一个 section 必须是参考文献
6. 每个 title 必须是行动标题（Action Title），即完整的结论性句子
7. search_keywords 六层合计不少于 80 个关键词（background/authority/timeliness/academic 每层至少 15 个，regulatory/weak_signal 每层至少 10 个）
8. **所有搜索关键词必须使用 {"keyword": "...", "lang": "xx"} 格式标记语言**
9. 关键词应包含该领域的专业术语
10. 除执行摘要、研究方法与局限性、人工验证清单、参考文献外，必须有至少 4 个内容章节
11. 每个内容章节应包含 2-3 个子章节
12. currency_weight 取值 1-3
13. freshness_policy 为每层搜索的时效过滤天数
14. data_sources 标记需要哪些数据源（v5.0 新增 gov_data/regulatory_filings/weak_signals）
15. gov_data_sources 只填与主题相关的政府数据源，不相关的字段值留空
16. regulatory_filings 只填与主题涉及的上市公司，不相关的字段值留空数组
17. weak_signal_queries 为每种弱信号类型设计查询

## 多语言关键词强制标记规则（v5.0）

- 如果主题涉及中国市场：至少 60% zh + 30% en + 10% 其他
- 如果主题是全球性的：至少覆盖 zh/en + 1-2 种相关语言
- 每层中不同语言关键词交替排列
- regulatory 层必须含 site:gov.cn / site:.gov 等限定关键词
- weak_signal 层必须含 site:linkedin.com/jobs、patent 等限定关键词

## 搜索关键词生成策略

**background 层**：通用背景，多语言
**authority 层**：site: 限定 + 机构名
**timeliness 层**：年份限定 + 事件驱动
**academic 层**：site:arxiv.org + site:pubmed + site:scholar.google
**regulatory 层（v5.0）**：site:gov.cn / SEC filing / site:go.jp 規制
**weak_signal 层（v5.0）**：招聘 site:linkedin.com/jobs / patent / 政府采购 中标公告

只输出纯 JSON，不要包含 ```json 标记，不要输出任何其他内容。
