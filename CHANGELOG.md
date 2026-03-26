# Changelog

All notable changes to this project will be documented in this file.

## [5.2.0] - 2026-03-26

### Added
- **CRAAP Code Scoring** (`craap_code_score.py`) — Currency and Authority dimensions now computed deterministically by code instead of LLM, reducing token cost by ~35%
- **Search Deduplication** (`dedup_sources.py`) — 3-level dedup (URL normalization, fuzzy title matching, SimHash content fingerprinting) runs immediately after search, removing 15-25% duplicate sources
- **Section-Source Pre-matching** (`match_sources_to_sections.py`) — TF-IDF + Jaccard similarity matching assigns relevant sources to each chapter before writing, reducing per-section prompt length by 40-50%
- **Table Sorting** in interactive HTML — click column headers to sort tables (numeric and string)
- **Table Pagination** in PDF — tables exceeding 15 rows are automatically split with continuation markers
- **Report Consistency Checks** in quality gate — orphan reference detection, executive summary-body consistency, confidence distribution validation
- **`status` subcommand** — check current progress without advancing the pipeline
- **Resume instructions** in SKILL.md — say "continue" to resume from breakpoint

### Changed
- Step `5_craap` split into `5a_craap_code` (CODE) + `5b_craap_llm` (LLM)
- Step `9_write_sections` split into `9a_match_sources` (CODE) + `9b_write_sections` (LLM)
- Step `3a2_dedup` inserted after `3a_search_web`
- `aggregate_craap.py` now merges code scores and LLM scores with `scoring_method` field
- Prompts `03a_craap_extract.md` and `03b_craap_batch.md` reduced from 5 dimensions to 3
- Total pipeline steps: 27 → 30 (LLM: 10, CODE: 20)

### Performance
- LLM token consumption: ~150K-200K → ~90K-130K (35-40% reduction)
- End-to-end time: ~20 min → ~14-16 min
- CRAAP evaluation determinism: 60% → 80% (2/5 dimensions now code-computed)

## [5.1.0] - 2026-03-25

### Added
- State machine driver (`run_research.py`) — all 27 steps orchestrated by code
- `init` / `next` / `confirm` protocol for agent interaction
- Breakpoint resume via `driver_state.json`

### Changed
- Migrated from LLM-driven step sequencing to deterministic state machine
- Zero step omission guarantee

## [5.0.0] - 2026-03-24

### Added
- T0 raw data tier (government APIs, regulatory filings)
- 6-layer search architecture
- 10 government data source APIs
- Regulatory filing access (SEC EDGAR, CNINFO, HKEX, EDINET)
- Weak signal collection (patents, hiring, procurement, academic trends)
- Information bubble detection (5-dimensional diversity scoring)
- Contradiction analysis with counter-intuitive findings
- Cross-language framework comparison
- Human verification checklist generation
- Interactive HTML report with Chart.js, dark/light theme, collapsible sections
- Triple-format rendering (PDF + DOCX + Interactive HTML)

### Changed
- Source tiers: T1-T5 → T0-T5 (530+ domains)
- Search fallback chain: Tavily → Brave → DuckDuckGo
- Academic search: arXiv → arXiv + Semantic Scholar + PubMed
