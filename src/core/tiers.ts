// Harness Research MCP Server — Source Tier Classification
// 530+ domain credibility database (T0-T5)

import fs from "node:fs"
import path from "node:path"
import { RESOURCE_DIR } from "../utils/config.js"

/** Load source tiers from YAML file */
export function loadSourceTiers(): Map<string, { tier: number; weight: number }> {
  const yamlPath = path.join(RESOURCE_DIR, "source_tiers.yaml")
  if (!fs.existsSync(yamlPath)) return new Map()

  const content = fs.readFileSync(yamlPath, "utf-8")
  const tiers = new Map<string, { tier: number; weight: number }>()

  const tierConfig: Record<string, { tier: number; weight: number }> = {
    tier_0_raw_data: { tier: 0, weight: 1.2 },
    tier_1_authority: { tier: 1, weight: 1.0 },
    tier_2_professional: { tier: 2, weight: 0.8 },
    tier_3_news: { tier: 3, weight: 0.6 },
    tier_5_social: { tier: 5, weight: 0.15 },
  }

  let currentTier: { tier: number; weight: number } | null = null
  for (const line of content.split("\n")) {
    const trimmed = line.trim()
    if (trimmed.startsWith("#") || !trimmed) continue

    for (const [key, cfg] of Object.entries(tierConfig)) {
      if (trimmed.startsWith(key + ":")) {
        currentTier = cfg
        break
      }
    }

    if (currentTier && trimmed.startsWith("- \"")) {
      const domain = trimmed.match(/- "([^"]+)"/)?.[1]
      if (domain) tiers.set(domain, currentTier)
    }
  }

  return tiers
}

/** Classify a URL into a tier based on domain */
export function classifyUrl(
  url: string,
  tiers: Map<string, { tier: number; weight: number }>,
): { tier: number; weight: number } {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    for (const [domain, config] of tiers) {
      if (hostname === domain || hostname.endsWith("." + domain) || hostname.includes(domain)) {
        return config
      }
    }
  } catch { /* ignore */ }
  return { tier: 4, weight: 0.3 }
}
