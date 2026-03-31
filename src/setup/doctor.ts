// Harness Research MCP Server — Doctor (Environment Diagnostics)

import fs from "node:fs"
import { CONFIG_DIR, ENV_PATH, loadEnv, getKeyStatus, getPlatformCapabilities, RESOURCE_DIR, PROMPTS_DIR } from "../utils/config.js"

export async function runDoctor(): Promise<void> {
  loadEnv()

  console.log("")
  console.log("╔══════════════════════════════════════════════════╗")
  console.log("║       Harness Research MCP — Doctor              ║")
  console.log("╚══════════════════════════════════════════════════╝")
  console.log("")

  let issues = 0

  // 1. Node.js version
  const nodeVersion = process.version
  const major = parseInt(nodeVersion.slice(1))
  console.log(`  Node.js: ${nodeVersion} ${major >= 18 ? "✅" : "❌ (need >= 18)"}`)
  if (major < 18) issues++

  // 2. Config directory
  console.log(`  Config dir: ${CONFIG_DIR} ${fs.existsSync(CONFIG_DIR) ? "✅" : "❌ (not found)"}`)
  if (!fs.existsSync(CONFIG_DIR)) issues++

  // 3. .env file
  console.log(`  .env file: ${ENV_PATH} ${fs.existsSync(ENV_PATH) ? "✅" : "❌ (run setup)"}`)
  if (!fs.existsSync(ENV_PATH)) issues++

  // 4. API keys
  console.log("")
  console.log("  API Keys:")
  const keys = getKeyStatus()

  const hasSearch = keys.TAVILY_API_KEY || keys.BRAVE_API_KEY
  const hasLLM = keys.KIMI_API_KEY || keys.OPENROUTER_API_KEY

  console.log(`    TAVILY_API_KEY:     ${keys.TAVILY_API_KEY ? "✅ set" : "⬜ not set"}`)
  console.log(`    BRAVE_API_KEY:      ${keys.BRAVE_API_KEY ? "✅ set" : "⬜ not set"}`)
  console.log(`    KIMI_API_KEY:       ${keys.KIMI_API_KEY ? "✅ set" : "⬜ not set"}`)
  console.log(`    OPENROUTER_API_KEY: ${keys.OPENROUTER_API_KEY ? "✅ set" : "⬜ not set"}`)
  console.log(`    TUSHARE_TOKEN:      ${keys.TUSHARE_TOKEN ? "✅ set" : "⬜ optional"}`)
  console.log(`    NCBI_API_KEY:       ${keys.NCBI_API_KEY ? "✅ set" : "⬜ optional"}`)

  if (!hasSearch) {
    console.log("    ❌ Need at least one search key (TAVILY or BRAVE)")
    issues++
  }
  if (!hasLLM) {
    console.log("    ❌ Need at least one LLM key (KIMI or OPENROUTER)")
    issues++
  }

  // 5. Resources
  console.log("")
  console.log("  Resources:")
  const promptFiles = ["plan.md", "craap_eval.md", "verify.md", "write_section.md", "exec_summary.md"]
  for (const f of promptFiles) {
    const p = `${PROMPTS_DIR}/${f}`
    const exists = fs.existsSync(p)
    console.log(`    prompts/${f}: ${exists ? "✅" : "❌"}`)
    if (!exists) issues++
  }

  const tiersPath = `${RESOURCE_DIR}/source_tiers.yaml`
  console.log(`    source_tiers.yaml: ${fs.existsSync(tiersPath) ? "✅" : "❌"}`)
  if (!fs.existsSync(tiersPath)) issues++

  const cssPath = `${RESOURCE_DIR}/styles.css`
  console.log(`    styles.css: ${fs.existsSync(cssPath) ? "✅" : "❌"}`)
  if (!fs.existsSync(cssPath)) issues++

  // 6. Platform capabilities
  console.log("")
  console.log("  Rendering:")
  const caps = await getPlatformCapabilities()
  console.log(`    HTML:  ✅ (all platforms)`)
  console.log(`    DOCX:  ✅ (all platforms)`)
  console.log(`    PDF:   ${caps.pdf ? "✅ (Puppeteer available)" : `❌ (${caps.os === "darwin" ? "install puppeteer" : "macOS only"})`}`)

  // Summary
  console.log("")
  if (issues === 0) {
    console.log("  ✅ All checks passed! Harness Research is ready.")
  } else {
    console.log(`  ⚠ ${issues} issue(s) found. Run 'npx harness-research-mcp setup' to fix.`)
  }
  console.log("")
}
