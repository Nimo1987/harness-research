// Harness Research MCP Server — Configuration Manager
// Manages ~/.harness-research/ directory for API keys and settings

import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

/** User config directory */
export const CONFIG_DIR = path.join(process.env.HOME || process.env.USERPROFILE || "", ".harness-research")
export const ENV_PATH = path.join(CONFIG_DIR, ".env")
export const CONFIG_PATH = path.join(CONFIG_DIR, "config.yaml")

/** Resource directory (bundled in npm package) */
export const RESOURCE_DIR = path.resolve(__dirname, "..", "resources")
export const PROMPTS_DIR = path.join(RESOURCE_DIR, "prompts")

/** Constants */
export const SEARCH_TIMEOUT = 10_000
export const LLM_TIMEOUT = 300_000
export const MAX_SOURCES = 50
export const CRAAP_THRESHOLD = 4.5

/** Ensure config directory exists */
export function ensureConfigDir(): void {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true })
  }
}

/** Load .env file into process.env (without overwriting existing values) */
export function loadEnv(): void {
  // Priority 1: user config dir
  const envPaths = [ENV_PATH]

  // Priority 2: legacy OpenCode location (for backward compat)
  const legacyPath = path.join(
    process.env.HOME || "",
    ".config/opencode/research-resources/.env"
  )
  envPaths.push(legacyPath)

  for (const envPath of envPaths) {
    if (!fs.existsSync(envPath)) continue
    for (const line of fs.readFileSync(envPath, "utf-8").split("\n")) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith("#")) continue
      const eqIdx = trimmed.indexOf("=")
      if (eqIdx < 0) continue
      const key = trimmed.slice(0, eqIdx).trim()
      const value = trimmed.slice(eqIdx + 1).trim()
      if (!process.env[key]) {
        process.env[key] = value
      }
    }
    break // Only load the first found .env
  }
}

/** Check if setup has been completed */
export function isSetupComplete(): boolean {
  return fs.existsSync(ENV_PATH)
}

/** Get required API key status */
export function getKeyStatus(): Record<string, boolean> {
  return {
    TAVILY_API_KEY: !!process.env.TAVILY_API_KEY,
    BRAVE_API_KEY: !!process.env.BRAVE_API_KEY,
    KIMI_API_KEY: !!process.env.KIMI_API_KEY,
    OPENROUTER_API_KEY: !!process.env.OPENROUTER_API_KEY,
    TUSHARE_TOKEN: !!process.env.TUSHARE_TOKEN,
    NCBI_API_KEY: !!process.env.NCBI_API_KEY,
  }
}

/** Check if at least one search key and one LLM key are available */
export function hasMinimalKeys(): boolean {
  const keys = getKeyStatus()
  const hasSearch = keys.TAVILY_API_KEY || keys.BRAVE_API_KEY
  const hasLLM = keys.KIMI_API_KEY || keys.OPENROUTER_API_KEY
  return hasSearch && hasLLM
}

/** Check if puppeteer (PDF) is available */
export async function hasPuppeteer(): Promise<boolean> {
  try {
    await import("puppeteer")
    return true
  } catch {
    return false
  }
}

/** Detect platform capabilities */
export async function getPlatformCapabilities(): Promise<{
  os: string
  html: boolean
  docx: boolean
  pdf: boolean
}> {
  const pdfAvailable = process.platform === "darwin" && (await hasPuppeteer())
  return {
    os: process.platform,
    html: true,
    docx: true,
    pdf: pdfAvailable,
  }
}
