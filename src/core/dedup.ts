// Harness Research MCP Server — Deduplication
// URL normalization + title Jaccard similarity

import type { SearchResult } from "../utils/types.js"

/** Normalize URL for dedup comparison */
function normalizeUrl(url: string): string {
  try {
    const u = new URL(url)
    u.protocol = "https:"
    u.hostname = u.hostname.replace(/^www\./, "")
    u.search = ""
    u.hash = ""
    const p = u.pathname.replace(/\/+$/, "")
    return `${u.hostname}${p}`.toLowerCase()
  } catch {
    return url.toLowerCase()
  }
}

/** Jaccard similarity between two titles (supports CJK) */
function titleJaccard(a: string, b: string): number {
  const tokenize = (s: string) => {
    const words = new Set<string>()
    s.split(/\s+/).forEach(w => { if (w.length > 1) words.add(w.toLowerCase()) })
    for (const ch of s) {
      if (/[\u4e00-\u9fff]/.test(ch)) words.add(ch)
    }
    return words
  }
  const setA = tokenize(a)
  const setB = tokenize(b)
  if (setA.size === 0 || setB.size === 0) return 0

  let intersection = 0
  for (const w of setA) if (setB.has(w)) intersection++
  return intersection / (setA.size + setB.size - intersection)
}

/** Deduplicate search results by URL + title similarity */
export function dedup(results: SearchResult[]): SearchResult[] {
  const seen = new Map<string, SearchResult>()
  const deduped: SearchResult[] = []

  for (const r of results) {
    const normUrl = normalizeUrl(r.url)
    if (seen.has(normUrl)) continue

    let isDuplicate = false
    for (const [, existing] of seen) {
      if (titleJaccard(r.title, existing.title) > 0.8) {
        isDuplicate = true
        break
      }
    }
    if (isDuplicate) continue

    seen.set(normUrl, r)
    deduped.push(r)
  }
  return deduped
}
