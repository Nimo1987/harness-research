# Changelog

## v2.0.0 (2026-03-31)

**Major rewrite: MCP Server architecture**

This is a complete rewrite of Harness Research as a standard MCP (Model Context Protocol) server. It can now be used as a plugin by any MCP-compatible AI agent.

### Breaking Changes
- Repackaged from OpenCode custom tool to standalone MCP Server
- Removed Python dependency entirely — now pure Node.js
- New configuration location: `~/.harness-research/` (was `~/.config/opencode/research-resources/`)

### New Features
- **MCP Standard Protocol**: Works with Claude Desktop, Cursor, Windsurf, OpenClaw, OpenCode, and any MCP client
- **Interactive Setup Wizard**: `npx harness-research-mcp setup` guides first-time configuration
- **Doctor Command**: `npx harness-research-mcp doctor` for environment diagnostics
- **Pure Node.js Rendering**: DOCX via `docx` npm package (all platforms), PDF via Puppeteer (macOS)
- **3 MCP Tools**: `harness_research` (full report), `harness_search` (quick search), `harness_status` (progress)
- **Cross-platform**: macOS (HTML+DOCX+PDF), Windows/Linux (HTML+DOCX+Markdown)
- **Zero Python**: No more weasyprint, no more cairo/pango system dependencies
- **npx one-liner**: `npx harness-research-mcp` — zero global install required

### Core (unchanged)
- 6-step research pipeline
- 5 data sources: Tavily, Brave, arXiv, PubMed, Tushare
- CRAAP evaluation framework (5-dimension + T0-T5 tiers)
- 530+ domain credibility database
- Cross-verification with conflict detection
- Parallel chapter writing

---

## v1.7.0 (Previous)

- State machine architecture with 30-step pipeline
- Python-based rendering (weasyprint + python-docx)
- OpenCode custom tool integration
- Parallel section writing (4 workers)
