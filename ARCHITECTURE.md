# Harness Research v5.2 — Architecture

## Core Design Philosophy

From "search-engine-dependent research" to "multi-layer direct-access knowledge discovery".

This is a **Harness Skill** — an implementation of Harness Engineering where deterministic code orchestrates LLM capabilities rather than letting the LLM orchestrate itself.

### Key Architecture Decisions

- **State machine over LLM orchestration** — 30 steps in strict order, zero step omission
- **Hybrid scoring** — deterministic code for Currency/Authority, LLM for Relevance/Accuracy/Purpose
- **Skill is logic layer, not infrastructure** — search via system tools, LLM via system model, data via API scripts

## Information Architecture (6 Layers)

| Layer | Sources | Method |
|-------|---------|--------|
| **L1 Background** | General web | Tavily → Brave → DuckDuckGo |
| **L2 Authority** | Government, academic | .gov / .edu / journals |
| **L3 Timeliness** | Recent news | Freshness-filtered search |
| **L4 Academic** | Papers, preprints | arXiv + Semantic Scholar + PubMed |
| **L5 Regulatory** | Filings, disclosures | SEC EDGAR + CNINFO + HKEX + EDINET |
| **L6 Weak Signals** | Patents, hiring, procurement | PatentsView + job search + gov procurement |

## Source Credibility (T0-T5)

| Tier | Weight | Description | CRAAP |
|------|--------|-------------|-------|
| T0 | 1.2 | Raw government/org data (APIs) | Skip |
| T1 | 1.0 | Government agencies, top journals | Hybrid |
| T2 | 0.8 | Top consultancies, industry analysts | Hybrid |
| T3 | 0.6 | Mainstream news, tech media | Hybrid |
| T4 | 0.4 | General websites, blogs | Hybrid |
| T5 | 0.15 | Social media, forums, UGC | Hybrid |

## File Structure

```
harness-research/
├── _meta.json              # Skill metadata (v5.2.0)
├── SKILL.md                # Agent entry point — execution protocol
├── ARCHITECTURE.md         # This file
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
│   ├── aggregate_craap.py       # CRAAP aggregation (code + LLM merge)
│   ├── classify_sources.py      # Source classification (T0-T5)
│   ├── cross_source_detect.py   # Cross-layer source detection
│   ├── diversity_check.py       # Information bubble detection (5-dim)
│   ├── quality_gate.py          # Quality gates + consistency checks
│   ├── fetch_gov_data.py        # Government data (10 sources)
│   ├── fetch_regulatory_filings.py  # Regulatory filings (4 markets)
│   ├── fetch_weak_signals.py    # Weak signals (patents/hiring/procurement)
│   ├── fetch_financial_data.py  # Financial data
│   ├── fetch_full_content.py    # Full-text fetching (top 20)
│   ├── sanitize_html.py         # HTML cleanup
│   ├── render_pdf.py            # PDF with table pagination
│   ├── render_docx.py           # DOCX rendering
│   └── render_interactive.py    # Interactive HTML (Chart.js + sorting)
│
├── prompts/                # 14 LLM prompt templates
│   ├── 01_plan.md               # Research planning
│   ├── 02_mece_check.md         # MECE validation
│   ├── 03_craap_eval.md         # CRAAP evaluation (reference)
│   ├── 03a_craap_extract.md     # T1-2 fast extraction (3 dimensions)
│   ├── 03b_craap_batch.md       # T3-5 full evaluation (3 dimensions)
│   ├── 04_triangulate.md        # Triangulation
│   ├── 05_analyze.md            # Analysis
│   ├── 06_write_exec_summary.md # Executive summary
│   ├── 07_write_section.md      # Section writing
│   ├── 08_write_methodology.md  # Methodology
│   ├── 09_analyze_and_write.md  # Analysis + writing (combined)
│   ├── 10_contradiction_analysis.md  # Contradiction analysis
│   ├── 11_cross_language_compare.md  # Cross-language comparison
│   └── 12_human_verification.md      # Human verification checklist
│
├── references/
│   └── source_tiers.yaml  # 530+ domain credibility database
│
└── templates/
    ├── report.html         # PDF/DOCX template
    └── styles.css          # Styling (light/dark themes)
```

## 30-Step Pipeline (v5.2)

### Phase 1: Research Plan (PLAN)
1. Generate research plan → LLM + `01_plan.md`
2. MECE validation → LLM + `02_mece_check.md`

### Phase 2: Multi-Layer Search (SEARCH)
3. 6-layer web search → `search_sources.py` (Tavily→Brave→DDG)
4. **[v5.2]** Search deduplication → `dedup_sources.py`
5. Financial data → `fetch_financial_data.py` (conditional)
6. Academic search → `search_sources.py` academic (arXiv+S2+PubMed)
7. Government data → `fetch_gov_data.py` (10 sources, conditional)
8. Regulatory filings → `fetch_regulatory_filings.py` (conditional)
9. Weak signals → `fetch_weak_signals.py` (conditional)

### Phase 3: Source Evaluation (EVALUATE)
10. Source classification (T0-T5) → `classify_sources.py`
11. Cross-source detection → `cross_source_detect.py`
12. Full-text fetching (top 20) → `fetch_full_content.py`
13. **[v5.2]** CRAAP code scoring (Currency/Authority) → `craap_code_score.py`
14. CRAAP LLM evaluation (Relevance/Accuracy/Purpose) → LLM + `03a/03b`
15. Score aggregation + filtering → `aggregate_craap.py` (T0 passthrough)
16. Diversity detection → `diversity_check.py` (5-dimensional)

### Phase 4: Verification (VERIFY)
17. Triangulation → LLM + `04_triangulate.md` (with gov data cross-check)
18. Contradiction analysis → LLM + `10_contradiction_analysis.md`
19. Cross-language comparison → LLM + `11_cross_language_compare.md`
20. Quality gate 1 → `quality_gate.py` (with diversity + counter-intuitive gates)

### Phase 5: Analysis & Writing (WRITE)
21. **[v5.2]** Section-source pre-matching → `match_sources_to_sections.py`
22. Section analysis + writing → LLM + `09_analyze_and_write.md`
23. Executive summary → LLM + `06_write_exec_summary.md`
24. Methodology → LLM + `08_write_methodology.md`
25. Human verification checklist → LLM + `12_human_verification.md`

### Phase 6: Assembly & Rendering (RENDER)
26. Generate references HTML
27. Merge HTML fragments
28. Sanitize (remove Markdown residue) → `sanitize_html.py`
29. Quality gate 2 → `quality_gate.py` (report consistency checks)
30. Triple-format render → `render_pdf.py` + `render_docx.py` + `render_interactive.py`

## Data Source Matrix

| Source | Script | API Key? | Data Type |
|--------|--------|----------|-----------|
| Tavily | search_sources.py | Yes | Web search (primary) |
| Brave | search_sources.py | Yes | Web search (fallback) |
| DuckDuckGo | search_sources.py | No | Web search (final fallback) |
| arXiv | search_sources.py | No | Academic papers |
| Semantic Scholar | search_sources.py | No | Academic papers |
| PubMed | search_sources.py | Yes (free) | Biomedical |
| World Bank | fetch_gov_data.py | No | Macro data (190 countries) |
| IMF | fetch_gov_data.py | No | Global economic forecasts |
| FRED | fetch_gov_data.py | Yes (free) | US macroeconomic |
| China NBS | fetch_gov_data.py | No | China statistics |
| OECD | fetch_gov_data.py | No | OECD indicators |
| Eurostat | fetch_gov_data.py | No | EU statistics |
| ClinicalTrials | fetch_gov_data.py | No | Clinical trials |
| EPA | fetch_gov_data.py | No | US environmental |
| data.gov | fetch_gov_data.py | No | US open data |
| UN Comtrade | fetch_gov_data.py | No | International trade |
| SEC EDGAR | fetch_regulatory_filings.py | No (UA) | US regulatory filings |
| CNINFO | fetch_regulatory_filings.py | No | China A-share filings |
| HKEX | fetch_regulatory_filings.py | No | HK stock filings |
| EDINET | fetch_regulatory_filings.py | No | Japan disclosures |
| PatentsView | fetch_weak_signals.py | No | US patents |
| Tushare | fetch_financial_data.py | Yes | China market data |
