# Harness Research

**[中文文档](README_ZH.md)**

A state-machine orchestrated deep research engine built as a **Harness Skill** — a practical product born from exploring the [Harness Engineering](https://github.com/anthropics/anthropic-cookbook) paradigm for AI agent development.

Instead of letting the LLM decide what to do next, the entire 30-step research pipeline is controlled by a deterministic state machine. The AI agent only handles what it's good at: reasoning over text. Everything else — search, scoring, filtering, rendering — is pure code.

## What It Does

Give it a research topic. Get back a professional-grade research report in three formats (PDF + DOCX + Interactive HTML), backed by:

- **6-layer search** across web, academic, government, regulatory, financial, and weak-signal sources
- **530+ domain classification** with T0-T5 tiered source credibility
- **CRAAP evaluation** — hybrid code + LLM scoring (Currency/Authority by code, Relevance/Accuracy/Purpose by LLM)
- **Triangulation** — cross-source verification with government data
- **Contradiction analysis** — surfacing counter-intuitive findings
- **Information bubble detection** — 5-dimensional diversity scoring
- **Quality gates** — automated retry loops when source quality is insufficient

## Architecture: Harness Engineering in Practice

This project is a concrete implementation of the **Harness Skill** pattern:

```
Traditional approach:    LLM decides everything → unpredictable, expensive
Harness approach:        Code orchestrates, LLM reasons → deterministic, efficient
```

The `run_research.py` state machine:
- Defines 30 steps in strict order (10 LLM + 20 CODE)
- Executes CODE steps directly (search, scoring, filtering, rendering)
- Hands off LLM steps with precise prompts, variables, and output schemas
- Manages retries, quality gates, and graceful degradation automatically

The agent's only job: call `init`, then loop `next` / `confirm` until `completed`.

**Result**: Zero step omissions. Deterministic execution. 35-40% lower LLM token cost compared to fully LLM-driven approaches.

## Cost & Time Estimates

| Metric | Typical Range |
|--------|---------------|
| **Total LLM tokens** | 90K - 130K tokens per research |
| **End-to-end time** | 14 - 20 minutes |
| **LLM steps** | 10 (out of 30 total steps) |
| **Sources evaluated** | 30 - 60 per research |

> Token consumption depends on topic complexity and number of sources found. The v5.2 hybrid CRAAP scoring and source pre-matching reduce LLM tokens by ~35-40% compared to v5.0.

## Prerequisites

### Runtime Environment

This is a **Harness Skill** designed to run inside an AI agent that supports Skill/tool orchestration:

- **Any LLM agent** that can execute shell commands and follow JSON instructions

### System Requirements

- Python 3.9+
- System dependencies for PDF rendering:
  ```bash
  # macOS
  brew install pango libffi

  # Ubuntu/Debian
  sudo apt-get install libpango1.0-dev libffi-dev
  ```

### Python Dependencies

```bash
pip install -r requirements.txt
```

### API Keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Key | Required | Free? | Purpose |
|-----|----------|-------|---------|
| `TAVILY_API_KEY` | **Yes** | Free tier available | Primary web search |
| `BRAVE_API_KEY` | Recommended | Free tier available | Search fallback |
| `FRED_API_KEY` | Optional | Yes | US economic data |
| `PUBMED_API_KEY` | Optional | Yes | Biomedical literature |
| `SEC_EDGAR_USER_AGENT` | Optional | Yes (just email) | SEC filings |
| `TUSHARE_TOKEN` | Optional | Free tier | Chinese market data |
| `SEMANTIC_SCHOLAR_KEY` | Optional | Works without key | Academic search |

> **DuckDuckGo** serves as the final search fallback and requires no key. The system degrades gracefully — missing optional keys simply skip those data sources.

## Quick Start

### As a Harness Skill

1. Place this directory in your agent's skill directory
2. The agent reads `SKILL.md` and follows the state-machine protocol:

```bash
# Initialize
python3 scripts/run_research.py init \
  --topic "Your research topic" \
  --workspace /path/to/workspace \
  --skill-dir /path/to/harness-research

# The agent then loops:
python3 scripts/run_research.py next --workspace ... --skill-dir ...
# → Returns JSON: {"status": "done_code", "next": true} or {"status": "need_llm", ...}

# Check progress anytime:
python3 scripts/run_research.py status --workspace ... --skill-dir ...
```

### The 30-Step Pipeline

| Phase | Steps | Type | What Happens |
|-------|-------|------|--------------|
| **PLAN** | 1-2 | LLM | Research plan + MECE validation |
| **SEARCH** | 3-9 | CODE | 6-layer search + dedup + finance/academic/gov/regulatory/weak-signals |
| **EVALUATE** | 10-16 | Mixed | Source classification + CRAAP (code+LLM) + aggregation + diversity check |
| **VERIFY** | 17-20 | Mixed | Triangulation + contradiction analysis + cross-language + quality gate |
| **WRITE** | 21-25 | Mixed | Source pre-matching + section writing + executive summary + methodology |
| **RENDER** | 26-30 | CODE | References + merge + sanitize + quality gate + triple-format render |

## Output

Every research produces three files in the `output/` directory:

- **PDF** — Print-ready report with table pagination
- **DOCX** — Editable document for further customization
- **Interactive HTML** — Sidebar navigation, collapsible sections, Chart.js visualizations, table sorting, dark/light theme

## Project Structure

```
harness-research/
├── _meta.json              # Skill metadata (v5.2.0)
├── SKILL.md                # Agent entry point — execution protocol
├── ARCHITECTURE.md         # Technical architecture details
├── config.yaml             # Global config (search, scoring, quality gates)
├── requirements.txt        # Python dependencies
├── .env.example            # API key template
│
├── scripts/                # 19 Python scripts
│   ├── run_research.py          # State machine driver (30 steps)
│   ├── search_sources.py        # 3-tier search fallback chain
│   ├── dedup_sources.py         # [v5.2] 3-level deduplication
│   ├── craap_code_score.py      # [v5.2] Deterministic Currency/Authority scoring
│   ├── match_sources_to_sections.py  # [v5.2] Section-source pre-matching
│   ├── aggregate_craap.py       # CRAAP score aggregation (code + LLM merge)
│   ├── quality_gate.py          # Quality gates with consistency checks
│   ├── render_pdf.py            # PDF with table pagination
│   ├── render_interactive.py    # Interactive HTML with sorting
│   └── ...                      # fetch_*, classify, diversity, sanitize, etc.
│
├── prompts/                # 14 LLM prompt templates
│   ├── 01_plan.md               # Research planning
│   ├── 03a_craap_extract.md     # CRAAP fast extraction (3 dimensions)
│   ├── 09_analyze_and_write.md  # Section analysis + writing
│   └── ...
│
├── references/
│   └── source_tiers.yaml  # 530+ domain credibility database (T0-T5)
│
└── templates/
    ├── report.html         # PDF/DOCX template
    └── styles.css          # Styling (light/dark themes)
```

## How Harness Engineering Works Here

The core insight: **don't let the LLM orchestrate — let code orchestrate the LLM.**

| Concern | Traditional | Harness Approach |
|---------|-------------|------------------|
| Step sequencing | LLM decides | State machine enforces |
| Source scoring (Currency) | LLM guesses | Code calculates from dates |
| Source scoring (Authority) | LLM guesses | Code maps from domain database |
| Source-to-section matching | LLM picks (position bias) | TF-IDF + Jaccard (no bias) |
| Search deduplication | LLM or late-stage | Code, immediately after search |
| Quality control | Hope for the best | Automated gates with retry loops |
| Report consistency | Manual review | Code checks (orphan refs, confidence distribution) |

This isn't about replacing the LLM — it's about using it where it adds value (reasoning, analysis, writing) and using deterministic code everywhere else.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE)

## Acknowledgments

Built by [Jiaqi](https://github.com/Nimo1987) through the practice of Harness Engineering — the discipline of building deterministic orchestration harnesses around LLM capabilities.
