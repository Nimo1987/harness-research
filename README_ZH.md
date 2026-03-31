[English](./README.md) | **中文**

# Harness Research MCP

**让任何 AI Agent 拥有专业级深度调研能力的 MCP 插件。**

一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的深度调研工具服务器。5 个数据源实时搜索、CRAAP 信源评估框架、交叉验证，最终输出带参考文献的专业报告。全程用国产模型（如 Kimi K2.5）驱动，成本极低。

> 走一次完整的深度调研报告，约 10 分钟，Kimi K2.5 即可顺利驱动。

---

> ### AI Agent 安装指引（Agent 请读这里）
>
> **这是一个 Node.js MCP 服务器，不是 Python 包。** 不要 `git clone`，不要 `pip install`。
>
> **第 1 步 — 一次性配置**（在用户终端运行）：
> ```bash
> npx harness-research-mcp setup
> ```
> 交互式向导会引导配置 API Key（存储在 `~/.harness-research/.env`）。
>
> **第 2 步 — 注册为 MCP 服务器**，写入你的 Agent 配置文件：
>
> Claude Desktop / Cursor / Windsurf — 编辑 MCP 配置 JSON：
> ```json
> {
>   "mcpServers": {
>     "harness-research": {
>       "command": "npx",
>       "args": ["-y", "harness-research-mcp"]
>     }
>   }
> }
> ```
>
> OpenCode — 添加到 `~/.config/opencode/opencode.json`：
> ```json
> {
>   "mcp": {
>     "harness-research": {
>       "command": "npx",
>       "args": ["-y", "harness-research-mcp"]
>     }
>   }
> }
> ```
>
> **完成。** 注册后 Agent 将获得 3 个工具：`harness_research`（完整调研报告）、`harness_search`（快速搜索）、`harness_status`（进度查询）。
>
> **不要** clone 本仓库、不要从源码 build、不要直接运行 `node` 或 `python`。`npx` 会自动处理一切。

---

## 为什么需要这个工具？

### 现有「深度调研」工具的问题

市面上的深度调研工具（Perplexity Deep Research、ChatGPT Research、Gemini Deep Research 等）存在几个根本缺陷：

| 问题 | 说明 |
|------|------|
| **依赖模型旧知识** | 它们本质上是让 LLM 从训练数据中"回忆"信息，而非去互联网上实时搜索。你得到的可能是几个月甚至一年前的过时数据。 |
| **信源不透明** | 大部分工具不告诉你信息来自哪里，无法验证准确性。引用的 URL 有些甚至是幻觉生成的。 |
| **没有信源评估** | 一篇社交媒体帖子和一份政府统计数据被同等对待。没有任何机制评估信源的可信度。 |
| **单一搜索源** | 只用一个搜索引擎，覆盖面窄。学术论文、金融数据、政府公报无法触达。 |
| **无法自定义** | 绑定在特定平台上，无法集成到你自己的 AI Agent 工作流中。 |
| **价格昂贵** | 依赖 GPT-4、Claude 等顶级模型，单次调研成本 $1-5+。 |

### Harness Research 的不同

| 特性 | Harness Research | Perplexity / ChatGPT / Gemini |
|------|-----------------|-------------------------------|
| **数据来源** | 5 个实时搜索 API（Tavily + Brave + arXiv + PubMed + Tushare） | 单一搜索引擎或模型内部知识 |
| **数据时效** | **全部实时搜索**，不依赖任何 LLM 训练数据 | 混合旧知识 + 有限搜索 |
| **信源评估** | CRAAP 框架 5 维评分 + T0-T5 六级分类（530+ 域名数据库） | 无 |
| **交叉验证** | 自动检测数据冲突 + 反直觉发现 | 无 |
| **参考文献** | 每条引用标注信源层级、可信度评分、发布日期 | 简单 URL 列表或无引用 |
| **LLM 要求** | Kimi K2.5 即可驱动（约 ¥0.1/次） | GPT-4 / Claude（$1-5/次） |
| **输出格式** | HTML + DOCX + PDF + Markdown | 纯文本 |
| **可集成性** | MCP 标准协议，任何 Agent 可用 | 绑定特定平台 |
| **开源** | Apache 2.0 | 闭源 |

**核心理念：LLM 只负责"思考"，不负责"知道"。一切事实数据都来自实时搜索。**

---

## 六步调研流程

```
用户: "帮我调研 2025 年全球 AI 芯片市场格局"
         │
         ▼
Step 1 ── 研究计划 (LLM)
         │  生成章节结构 + 搜索关键词
         ▼
Step 2 ── 五源并行搜索 (Code)
         │  Tavily + Brave + arXiv + PubMed + Tushare
         │  去重 → 限制 50 条
         ▼
Step 3 ── CRAAP 信源评估 (Code + LLM)
         │  代码预筛: T5 淘汰、超 3 年淘汰
         │  LLM 分批评分: Relevance + Accuracy + Purpose
         │  加权平均 → 过滤低分源
         ▼
Step 4 ── 交叉验证 (LLM)
         │  数据三角验证 + 矛盾检测 + 反直觉发现
         ▼
Step 5 ── 并行撰写 (LLM)
         │  各章节并行 + 执行摘要
         ▼
Step 6 ── 渲染输出 (Code)
         │  HTML + DOCX + PDF (macOS) + Markdown
         ▼
    输出专业调研报告 (~10 分钟)
```

---

## 快速开始

### 1. 安装配置（一次性）

```bash
npx harness-research-mcp setup
```

交互式向导会引导你：
- 配置搜索引擎 API Key（Tavily 或 Brave，至少一个）
- 配置 LLM API Key（推荐 Kimi K2.5，最便宜）
- 可选：Tushare（中国金融数据）、NCBI（PubMed 学术搜索）
- 自动测试 API 连通性

### 2. 注册到你的 AI Agent

根据你使用的 Agent 框架，复制对应配置：

**Claude Desktop / Cursor / Windsurf：**
```json
{
  "mcpServers": {
    "harness-research": {
      "command": "npx",
      "args": ["-y", "harness-research-mcp"]
    }
  }
}
```

**OpenClaw：**
```bash
openclaw mcp set harness-research '{"command":"npx","args":["-y","harness-research-mcp"]}'
```

**OpenCode：**
```jsonc
// ~/.config/opencode/opencode.json
{
  "mcp": {
    "harness-research": {
      "command": "npx",
      "args": ["-y", "harness-research-mcp"]
    }
  }
}
```

### 3. 开始使用

直接对你的 Agent 说：

> "帮我深度调研一下 2025 年全球 AI 芯片市场格局"

Agent 会自动调用 `harness_research` 工具，约 10 分钟后返回完整报告。

---

## 三个 MCP 工具

| 工具 | 说明 | 耗时 |
|------|------|------|
| `harness_research` | 完整深度调研，输出专业报告 | ~10 分钟 |
| `harness_search` | 快速多源搜索，返回结构化结果 | 几秒 |
| `harness_status` | 查询调研任务进度 | 即时 |

---

## API Key 说明

### 为什么需要这些 Key？

Harness Research 不依赖任何 LLM 的历史知识库。**所有信息都是实时从互联网搜索获取的**。这需要调用各种搜索和数据 API。

| Key | 用途 | 必要性 | 获取方式 | 费用 |
|-----|------|--------|---------|------|
| **TAVILY_API_KEY** | 高级网页搜索（支持深度抓取） | 必填（二选一） | [tavily.com](https://tavily.com) | 免费 1000 次/月 |
| **BRAVE_API_KEY** | 网页搜索（隐私保护） | 必填（二选一） | [brave.com/search/api](https://brave.com/search/api/) | 免费 2000 次/月 |
| **KIMI_API_KEY** | LLM 推理（研究计划、评估、撰写） | 必填（二选一） | [platform.moonshot.cn](https://platform.moonshot.cn) | 极低成本 |
| **OPENROUTER_API_KEY** | LLM 推理（替代 Kimi） | 必填（二选一） | [openrouter.ai](https://openrouter.ai) | 按模型定价 |
| TUSHARE_TOKEN | 中国 A 股金融数据 | 可选 | [tushare.pro](https://tushare.pro) | 免费基础版 |
| NCBI_API_KEY | PubMed 学术论文搜索 | 可选 | [ncbi.nlm.nih.gov](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) | 免费 |

**最低配置：1 个搜索 Key + 1 个 LLM Key = 2 个 Key 即可运行。**

### 为什么推荐 Kimi K2.5？

- 价格：约 ¥0.1 / 次完整调研（对比 GPT-4 约 ¥7-35 / 次）
- 中文能力：原生中文支持，无需翻译中间层
- 上下文：128K token 上下文窗口，足以处理大量搜索结果
- 稳定性：API 可用性 99.9%+

---

## 输出格式

| 格式 | macOS | Windows / Linux | 说明 |
|------|-------|-----------------|------|
| **HTML** | ✅ | ✅ | 专业排版，支持暗色主题，浏览器打开即可 |
| **DOCX** | ✅ | ✅ | Word 文档，可直接编辑分享 |
| **PDF** | ✅ | ❌ | 基于 Puppeteer，仅 macOS |
| **Markdown** | ✅ | ✅ | 纯文本，便于二次处理 |

---

## CRAAP 评估框架

每一条信源都经过 5 维评估：

| 维度 | 权重 | 评估内容 |
|------|------|---------|
| **C**urrency（时效性） | 15% | 发布日期距今多久？ |
| **A**uthority（权威性） | 25% | 信源来自哪个层级？政府 > 学术 > 媒体 > 博客 |
| **R**elevance（相关性） | 25% | 与调研主题的匹配度 |
| **A**ccuracy（准确性） | 20% | 数据是否可验证？有无引用？ |
| **P**urpose（目的性） | 15% | 信源的写作目的是否客观？ |

### 信源六级分类

| 层级 | 权重 | 来源类型 | 示例 |
|------|------|---------|------|
| T0 | 1.2x | 政府原始数据 API | 世界银行 API、美联储 FRED、SEC EDGAR |
| T1 | 1.0x | 权威机构 | WHO、学术期刊 (Nature, Science)、政府报告 |
| T2 | 0.8x | 专业机构 | McKinsey、Gartner、金融时报 |
| T3 | 0.6x | 主流媒体 | Reuters、Bloomberg、TechCrunch |
| T4 | 0.3x | 一般网站 | 未归类的域名（默认） |
| T5 | 0.15x | 社交媒体 | Twitter、Reddit、知乎（自动淘汰） |

内置 **530+ 域名**的可信度数据库，覆盖全球主要政府、学术、媒体和专业机构。

---

## 环境诊断

```bash
npx harness-research-mcp doctor
```

输出示例：
```
  Node.js: v22.15.0 ✅
  Config dir: ~/.harness-research ✅
  .env file: ~/.harness-research/.env ✅

  API Keys:
    TAVILY_API_KEY:     ✅ set
    BRAVE_API_KEY:      ✅ set
    KIMI_API_KEY:       ✅ set
    TUSHARE_TOKEN:      ✅ set

  Rendering:
    HTML:  ✅ (all platforms)
    DOCX:  ✅ (all platforms)
    PDF:   ✅ (Puppeteer available)

  ✅ All checks passed!
```

---

## 技术架构

```
┌──────────────────────────────────────────┐
│  Claude / Cursor / OpenClaw / OpenCode   │
│            (MCP Client)                  │
└────────────────┬─────────────────────────┘
                 │ stdio (MCP Protocol)
                 ▼
┌──────────────────────────────────────────┐
│      harness-research-mcp (Node.js)      │
│                                          │
│  Tools:                                  │
│    harness_research — 完整深度调研         │
│    harness_search   — 快速多源搜索         │
│    harness_status   — 进度查询            │
│                                          │
│  Core:                                   │
│    6-Step Pipeline                        │
│    ├─ LLM (Kimi K2.5 / OpenRouter)       │
│    ├─ Search (5 sources, parallel)        │
│    ├─ CRAAP (code + LLM hybrid)           │
│    ├─ Verify (cross-validation)           │
│    └─ Render (HTML/DOCX/PDF/MD)           │
│                                          │
│  Resources:                              │
│    prompts/ (5 templates)                │
│    source_tiers.yaml (530+ domains)       │
│    styles.css (light/dark themes)         │
└──────────────────────────────────────────┘
         │           │           │
         ▼           ▼           ▼
    Tavily API   Brave API   arXiv/PubMed/Tushare
```

**纯 Node.js，无 Python 依赖。** `npx` 一键启动。

---

## 开发

```bash
git clone https://github.com/Nimo1987/harness-research.git
cd harness-research
npm install
npm run build
```

---

## License

Apache 2.0 — 自由使用，商业友好。
