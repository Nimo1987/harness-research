// Harness Research MCP Server — JSON/HTML parsing utilities

/** Extract JSON from LLM response (handles markdown code blocks, etc.) */
export function extractJson(text: string): string {
  let cleaned = text.replace(/```json\s*/gi, "").replace(/```\s*/g, "")

  const idxBrace = cleaned.indexOf("{")
  const idxBracket = cleaned.indexOf("[")
  let startChar: string
  let endChar: string

  if (idxBrace < 0 && idxBracket < 0) return cleaned
  if (idxBrace < 0) { startChar = "["; endChar = "]" }
  else if (idxBracket < 0) { startChar = "{"; endChar = "}" }
  else if (idxBrace <= idxBracket) { startChar = "{"; endChar = "}" }
  else { startChar = "["; endChar = "]" }

  const startIdx = cleaned.indexOf(startChar)
  if (startIdx < 0) return cleaned

  let depth = 0
  let inString = false
  let escape = false
  for (let i = startIdx; i < cleaned.length; i++) {
    const ch = cleaned[i]
    if (escape) { escape = false; continue }
    if (ch === "\\") { escape = true; continue }
    if (ch === '"') { inString = !inString; continue }
    if (inString) continue
    if (ch === startChar) depth++
    else if (ch === endChar) {
      depth--
      if (depth === 0) return cleaned.slice(startIdx, i + 1)
    }
  }
  return cleaned.slice(startIdx)
}

/** Extract HTML content from LLM response */
export function extractHtml(text: string): string {
  return text.replace(/```html\s*/gi, "").replace(/```\s*/g, "").trim()
}

/** Safe JSON parse with fallback */
export function safeJsonParse<T>(text: string, fallback: T): T {
  try {
    return JSON.parse(extractJson(text)) as T
  } catch {
    return fallback
  }
}

/** Escape HTML entities */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

/** Generate timestamp-based filename */
export function generateFilename(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return `harness-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

/** Sleep utility */
export function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms))
}
