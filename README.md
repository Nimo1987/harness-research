**English** | [中文](./README_ZH.md)

# Harness Research MCP

**Give any AI Agent professional-grade deep research capabilities.**

An MCP (Model Context Protocol) server that performs real-time deep research across 5 data sources, evaluates source credibility with the CRAAP framework, cross-verifies findings, and generates professional reports — all driven by affordable models like Kimi K2.5.

> A full deep research report takes ~10 minutes and can be driven by Kimi K2.5 at ~$0.01/run.

---

> ### For AI Agents: How to install this tool
>
> **This is a Node.js MCP server, NOT a Python package.** Do NOT `git clone` or `pip install`.
>
> **Step 1 — One-time setup** (run in user's terminal):
> ```bash
> npx harness-research-mcp setup
> ```
> This launches an interactive wizard to configure API keys (stored in `~/.harness-research/.env`).
>
> **Step 2 — Register as MCP server** in your agent's config file:
>
> Claude Desktop / Cursor / Windsurf — edit MCP config JSON:
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
> OpenCode — add to `~/.config/opencode/opencode.json`:
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
> **That's it.** After registration, the agent gets 3 tools: `harness_research` (full report), `harness_search` (quick search), `harness_status` (progress check).
>
> **Do NOT** clone this repo, build from source, or run `node`/`python` directly. `npx` handles everything.
>
> **Async workflow — no timeout issues:**
> `harness_research` returns a `task_id` immediately (< 1 second). The research runs in the background (~10 minutes). You **must** poll `harness_status(task_id)` every 30–60 seconds until status is `"completed"` or `"failed"`. This design means the default 60-second MCP timeout will NOT be a problem.
>
> If your MCP client has a configurable timeout, setting it to **1200 seconds (20 minutes)** is still recommended as a safety margin:
> ```json
> {
>   "mcpServers": {
>     "harness-research": {
>       "command": "npx",
>       "args": ["-y", "harness-research-mcp"],
>       "timeout": 1200
>     }
>   }
> }
> ```

---

## Why This Tool Exists

### The Problem with Current "Deep Research" Tools

Existing deep research tools (Perplexity Deep Research, ChatGPT Research, Gemini Deep Research, etc.) share fundamental flaws:

| Problem | Explanation |
|---------|-------------|
| **Rely on stale knowledge** | They primarily draw from the LLM's training data, not real-time internet search. You may get data that's months or years out of date. |
| **Opaque sourcing** | Most tools don't show where information came from. Some cited URLs are hallucinated. |
| **No source evaluation** | A social media post and a government statistical report are treated equally. No mechanism to assess credibility. |
| **Single search source** | One search engine, narrow coverage. Academic papers, financial data, and government reports are unreachable. |
| **Not integrable** | Locked into specific platforms. Can't plug into your own AI Agent workflow. |
| **Expensive** | Require GPT-4, Claude, etc. Each research session costs $1-5+. |

### How Harness Research Is Different

| Feature | Harness Research | Perplexity / ChatGPT / Gemini |
|---------|-----------------|-------------------------------|
| **Data sources** | 5 real-time search APIs (Tavily + Brave + arXiv + PubMed + Tushare) | Single search engine or model's internal knowledge |
| **Data freshness** | **100% real-time search** — zero reliance on LLM training data | Mixed stale knowledge + limited search |
| **Source evaluation** | CRAAP framework with 5-dimension scoring + T0-T5 tier classification (530+ domain database) | None |
| **Cross-verification** | Automatic conflict detection + counterintuitive finding identification | None |
| **Citations** | Every reference tagged with source tier, credibility score, publication date | Simple URL list or no citations |
| **LLM requirement** | Kimi K2.5 works great (~$0.01/run) | GPT-4 / Claude ($1-5/run) |
| **Output formats** | HTML + DOCX + PDF + Markdown | Plain text |
| **Integrability** | Standard MCP protocol — works with any Agent | Locked to specific platform |
| **Open source** | Apache 2.0 | Proprietary |

**Core principle: The LLM only "thinks" — it never "knows." All factual data comes from real-time search.**

---

## The 6-Step Research Pipeline

```
User: "Research the global AI chip market landscape in 2025"
         │
         ▼
Step 1 ── Research Plan (LLM)
         │  Generate chapter structure + search keywords
         ▼
Step 2 ── 5-Source Parallel Search (Code)
         │  Tavily + Brave + arXiv + PubMed + Tushare
         │  Dedup → cap at 50 results
         ▼
Step 3 ── CRAAP Source Evaluation (Code + LLM)
         │  Code pre-filter: T5 eliminated, >3yr eliminated
         │  LLM batch scoring: Relevance + Accuracy + Purpose
         │  Weighted average → filter low-scoring sources
         ▼
Step 4 ── Cross-Verification (LLM)
         │  Data triangulation + conflict detection + counterintuitive findings
         ▼
Step 5 ── Parallel Writing (LLM)
         │  All chapters in parallel + executive summary
         ▼
Step 6 ── Render Output (Code)
         │  HTML + DOCX + PDF (macOS) + Markdown
         ▼
    Professional research report (~10 minutes)
```

---

## Quick Start

### 1. Setup (one-time)

```bash
npx harness-research-mcp setup
```

The interactive wizard will guide you through:
- Configuring search API keys (Tavily or Brave, at least one)
- Configuring an LLM API key (Kimi K2.5 recommended — cheapest option)
- Optional: Tushare (Chinese financial data), NCBI (PubMed academic search)
- Automatic API connectivity test

### 2. Register with Your AI Agent

Copy the appropriate config for your Agent framework:

**Claude Desktop / Cursor / Windsurf:**
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

**OpenClaw:**
```bash
openclaw mcp set harness-research '{"command":"npx","args":["-y","harness-research-mcp"]}'
```

**OpenCode:**
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

### 3. Use It

Just tell your Agent:

> "Do a deep research on the global AI chip market landscape in 2025"

The Agent will automatically call `harness_research` and return the full report in ~10 minutes.

---

## Three MCP Tools

| Tool | Description | Duration |
|------|-------------|----------|
| `harness_research` | Full deep research with professional report output | ~10 min |
| `harness_search` | Quick multi-source search, returns structured results | Seconds |
| `harness_status` | Check research task progress | Instant |

---

## API Keys Explained

### Why Do You Need These Keys?

Harness Research does **not** rely on any LLM's historical knowledge. **All information is fetched in real-time from the internet.** This requires calling various search and data APIs.

| Key | Purpose | Required? | Get it | Cost |
|-----|---------|-----------|--------|------|
| **TAVILY_API_KEY** | Advanced web search (deep scraping support) | Required (pick one) | [tavily.com](https://tavily.com) | Free 1000 calls/mo |
| **BRAVE_API_KEY** | Privacy-focused web search | Required (pick one) | [brave.com/search/api](https://brave.com/search/api/) | Free 2000 calls/mo |
| **KIMI_API_KEY** | LLM reasoning (planning, evaluation, writing) | Required (pick one) | [platform.moonshot.cn](https://platform.moonshot.cn) | Very low cost |
| **OPENROUTER_API_KEY** | LLM reasoning (alternative to Kimi) | Required (pick one) | [openrouter.ai](https://openrouter.ai) | Per-model pricing |
| TUSHARE_TOKEN | Chinese A-share financial data | Optional | [tushare.pro](https://tushare.pro) | Free basic tier |
| NCBI_API_KEY | PubMed academic paper search | Optional | [ncbi.nlm.nih.gov](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) | Free |

**Minimum: 1 search key + 1 LLM key = 2 keys to get started.**

### Why Kimi K2.5?

- **Cost**: ~$0.01 per full research session (vs. GPT-4 at $1-5)
- **Chinese support**: Native Chinese language, no translation layer needed
- **Context**: 128K token window — handles large volumes of search results
- **Reliability**: 99.9%+ API availability

---

## Output Formats

| Format | macOS | Windows / Linux | Notes |
|--------|-------|-----------------|-------|
| **HTML** | ✅ | ✅ | Professional layout, dark theme support |
| **DOCX** | ✅ | ✅ | Word document, ready to edit and share |
| **PDF** | ✅ | ❌ | Puppeteer-based, macOS only |
| **Markdown** | ✅ | ✅ | Plain text, easy to post-process |

---

## CRAAP Evaluation Framework

Every source is scored across 5 dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **C**urrency | 15% | How recent is the publication? |
| **A**uthority | 25% | Source tier: Government > Academic > Media > Blog |
| **R**elevance | 25% | How well does it match the research topic? |
| **A**ccuracy | 20% | Is the data verifiable? Does it cite sources? |
| **P**urpose | 15% | Is the writing objective or biased? |

### 6-Tier Source Classification

| Tier | Weight | Source Type | Examples |
|------|--------|-------------|----------|
| T0 | 1.2x | Raw government data APIs | World Bank API, Fed FRED, SEC EDGAR |
| T1 | 1.0x | Authoritative institutions | WHO, Nature, Science, government reports |
| T2 | 0.8x | Professional organizations | McKinsey, Gartner, Financial Times |
| T3 | 0.6x | Mainstream media | Reuters, Bloomberg, TechCrunch |
| T4 | 0.3x | General websites | Unclassified domains (default) |
| T5 | 0.15x | Social media | Twitter, Reddit (auto-eliminated) |

Built-in **530+ domain** credibility database covering major governments, academia, media, and professional institutions worldwide.

---

## Diagnostics

```bash
npx harness-research-mcp doctor
```

---

## Architecture

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
│    harness_research — full deep research  │
│    harness_search   — quick multi-search  │
│    harness_status   — progress query      │
│                                          │
│  6-Step Pipeline:                         │
│    Plan → Search → CRAAP → Verify →       │
│    Write → Render                         │
│                                          │
│  Pure Node.js. Zero Python dependency.    │
└──────────────────────────────────────────┘
```

---

## Development

```bash
git clone https://github.com/Nimo1987/harness-research.git
cd harness-research
npm install
npm run build
```

---

## License

Apache 2.0
