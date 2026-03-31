#!/usr/bin/env node

// Harness Research MCP — CLI Entry Point
// Usage:
//   harness-research serve   → Start MCP server (default, stdio)
//   harness-research setup   → Interactive setup wizard
//   harness-research doctor  → Check environment & API keys

import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const distDir = join(__dirname, "..", "dist")

const command = process.argv[2] || "serve"

if (command === "setup" || command === "doctor") {
  const { run } = await import(join(distDir, "cli.js"))
  await run(command)
} else {
  // Default: start MCP server (stdio)
  await import(join(distDir, "index.js"))
}
