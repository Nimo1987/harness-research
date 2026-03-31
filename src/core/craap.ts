// Harness Research MCP Server — CRAAP Scoring
// Currency + Authority (code-based) + Relevance/Accuracy/Purpose (LLM-based)

import type { EvaluatedSource, LLMConfig, SearchResult } from "../utils/types.js"
import { CRAAP_THRESHOLD } from "../utils/config.js"
import { callLLM } from "./llm.js"
import { loadPrompt } from "../utils/prompts.js"
import { safeJsonParse } from "../utils/json.js"
import { classifyUrl, loadSourceTiers } from "./tiers.js"

// ── Date parsing ──

function parseDate(text: string): Date | null {
  if (!text) return null

  let m = text.match(/(\d{4})-(\d{1,2})-(\d{1,2})/)
  if (m) return new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]))

  m = text.match(/(\d{4})\/(\d{1,2})\/(\d{1,2})/)
  if (m) return new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]))

  const months: Record<string, number> = {
    jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
    jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
  }
  m = text.match(/(\w{3,9})\s+(\d{1,2}),?\s+(\d{4})/)
  if (m) {
    const mon = months[m[1].toLowerCase().slice(0, 3)]
    if (mon !== undefined) return new Date(parseInt(m[3]), mon, parseInt(m[2]))
  }

  m = text.match(/(\d+)\s+(day|week|month|year)s?\s+ago/i)
  if (m) {
    const n = parseInt(m[1])
    const unit = m[2].toLowerCase()
    const now = new Date()
    if (unit === "day") now.setDate(now.getDate() - n)
    else if (unit === "week") now.setDate(now.getDate() - n * 7)
    else if (unit === "month") now.setMonth(now.getMonth() - n)
    else if (unit === "year") now.setFullYear(now.getFullYear() - n)
    return now
  }

  return null
}

/** Score currency (time freshness) 0-10 */
export function scoreCurrency(publishedDate: string): number {
  const date = parseDate(publishedDate)
  if (!date) return 5.0
  const now = new Date()
  const daysDiff = (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24)
  if (daysDiff <= 30) return 10.0
  if (daysDiff <= 90) return 9.0
  if (daysDiff <= 180) return 8.0
  if (daysDiff <= 365) return 7.0
  if (daysDiff <= 730) return 5.5
  if (daysDiff <= 1095) return 4.0
  return 2.5
}

/** Score authority based on tier */
export function scoreAuthority(tier: number): number {
  const tierScores: Record<number, number> = {
    0: 10.0, 1: 9.0, 2: 7.5, 3: 5.5, 4: 3.5, 5: 1.5,
  }
  return tierScores[tier] ?? 3.5
}

/** Full CRAAP evaluation pipeline: code pre-filter + LLM batch scoring */
export async function evaluateSources(
  results: SearchResult[],
  topic: string,
  llmConfig: LLMConfig,
): Promise<{ evaluated: EvaluatedSource[]; totalBefore: number }> {
  const sourceTiers = loadSourceTiers()

  // Classify & code-score
  const classified = results.map(r => {
    const { tier, weight } = classifyUrl(r.url, sourceTiers)
    return {
      ...r,
      tier,
      weight,
      currency: scoreCurrency(r.published_date),
      authority: scoreAuthority(tier),
    }
  })

  // T0 sources: auto-pass (raw government data needs no CRAAP)
  const t0Sources: EvaluatedSource[] = classified
    .filter(r => r.tier === 0)
    .map(r => ({
      ...r,
      relevance: 8,
      accuracy: 8,
      purpose: 9,
      craapScore: 9.0,
      key_facts: [r.snippet.slice(0, 100)],
    }))

  // Pre-filter: remove T5, too-old, empty
  const preFiltered = classified.filter(r => {
    if (r.tier === 0) return false
    if (r.tier === 5) return false
    if (r.currency < 3.0) return false
    if (!r.title && !r.snippet) return false
    return true
  })

  preFiltered.sort((a, b) => a.tier - b.tier || b.currency - a.currency)

  let evaluatedSources: EvaluatedSource[] = [...t0Sources]

  // LLM batch evaluation
  if (preFiltered.length > 0) {
    const BATCH_SIZE = 15
    const batches: (typeof preFiltered)[] = []
    for (let i = 0; i < preFiltered.length; i += BATCH_SIZE) {
      batches.push(preFiltered.slice(i, i + BATCH_SIZE))
    }

    const batchPromises = batches.map(async (batch) => {
      const sourcesText = batch
        .map(
          (r, i) =>
            `[${i}] URL: ${r.url}\nTitle: ${r.title}\nSnippet: ${r.snippet.slice(0, 300)}\nSource: ${r.source}`,
        )
        .join("\n\n")

      const evalPrompt = loadPrompt("craap_eval", {
        TOPIC: topic,
        SOURCES: sourcesText,
      })

      try {
        const evalRaw = await callLLM(llmConfig, evalPrompt)
        return { batch, results: safeJsonParse<any[]>(evalRaw, []) }
      } catch {
        return { batch, results: [] }
      }
    })

    const batchResults = await Promise.allSettled(batchPromises)

    for (const br of batchResults) {
      if (br.status !== "fulfilled") continue
      const { batch, results: evalResults } = br.value

      const evalMap = new Map<string, any>()
      for (const e of evalResults) {
        if (e && e.url) evalMap.set(e.url, e)
      }

      for (const r of batch) {
        const e = evalMap.get(r.url)
        const relevance = e?.relevance?.score ?? 5
        const accuracy = e?.accuracy?.score ?? 5
        const purpose = e?.purpose?.score ?? 5
        const key_facts = e?.key_facts || [r.snippet.slice(0, 100)]

        const craapScore =
          r.currency * 0.15 +
          r.authority * 0.25 +
          relevance * 0.25 +
          accuracy * 0.2 +
          purpose * 0.15

        evaluatedSources.push({
          ...r,
          relevance,
          accuracy,
          purpose,
          craapScore,
          key_facts,
        })
      }
    }
  }

  const totalBefore = evaluatedSources.length
  evaluatedSources = evaluatedSources.filter(s => s.craapScore >= CRAAP_THRESHOLD)

  return { evaluated: evaluatedSources, totalBefore }
}
