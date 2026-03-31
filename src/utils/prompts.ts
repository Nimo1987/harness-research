// Harness Research MCP Server — Prompt template loader

import fs from "node:fs"
import path from "node:path"
import { PROMPTS_DIR } from "./config.js"

/** Load and render a prompt template with variable substitution */
export function loadPrompt(name: string, vars: Record<string, string>): string {
  const filePath = path.join(PROMPTS_DIR, `${name}.md`)
  if (!fs.existsSync(filePath)) {
    throw new Error(`Prompt template not found: ${filePath}`)
  }
  let content = fs.readFileSync(filePath, "utf-8")
  for (const [key, value] of Object.entries(vars)) {
    content = content.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), value)
  }
  return content
}
