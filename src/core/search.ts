// Harness Research MCP Server — Multi-source Search Engine
// 5 data sources: Tavily, Brave, arXiv, PubMed, Tushare

import type { SearchResult } from "../utils/types.js"
import { sleep } from "../utils/json.js"
import { SEARCH_TIMEOUT } from "../utils/config.js"

// ── Tavily Search ──

export async function searchTavily(keywords: string[]): Promise<SearchResult[]> {
  const apiKey = process.env.TAVILY_API_KEY
  if (!apiKey) return []

  const results: SearchResult[] = []
  for (const kw of keywords.slice(0, 4)) {
    try {
      const resp = await fetch("https://api.tavily.com/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          query: kw,
          max_results: 5,
          include_raw_content: false,
          search_depth: "advanced",
          days: 365,
        }),
        signal: AbortSignal.timeout(SEARCH_TIMEOUT),
      })
      if (!resp.ok) continue
      const data = (await resp.json()) as any
      for (const r of data.results || []) {
        results.push({
          title: r.title || "",
          url: r.url || "",
          snippet: (r.content || "").slice(0, 500),
          source: "tavily",
          published_date: r.published_date || "",
        })
      }
      await sleep(200)
    } catch {
      // Silent fail — search degradation is expected
    }
  }
  return results
}

// ── Brave Search ──

export async function searchBrave(keywords: string[]): Promise<SearchResult[]> {
  const apiKey = process.env.BRAVE_API_KEY
  if (!apiKey) return []

  const results: SearchResult[] = []
  for (const kw of keywords.slice(0, 4)) {
    try {
      const params = new URLSearchParams({ q: kw, count: "5", freshness: "py" })
      const resp = await fetch(`https://api.search.brave.com/res/v1/web/search?${params}`, {
        headers: { "X-Subscription-Token": apiKey, Accept: "application/json" },
        signal: AbortSignal.timeout(SEARCH_TIMEOUT),
      })
      if (!resp.ok) continue
      const data = (await resp.json()) as any
      for (const r of data.web?.results || []) {
        results.push({
          title: r.title || "",
          url: r.url || "",
          snippet: (r.description || "").slice(0, 500),
          source: "brave",
          published_date: r.age || "",
        })
      }
      await sleep(500)
    } catch {
      // Silent fail
    }
  }
  return results
}

// ── arXiv Search ──

export async function searchArxiv(keywords: string[]): Promise<SearchResult[]> {
  const results: SearchResult[] = []
  try {
    const query = keywords.slice(0, 5).join(" OR ")
    const params = new URLSearchParams({
      search_query: `all:${query}`,
      start: "0",
      max_results: "10",
      sortBy: "submittedDate",
      sortOrder: "descending",
    })

    const resp = await fetch(`http://export.arxiv.org/api/query?${params}`, {
      signal: AbortSignal.timeout(SEARCH_TIMEOUT),
    })
    if (!resp.ok) return []

    const xml = await resp.text()
    const entries = xml.split("<entry>").slice(1)
    for (const entry of entries) {
      const title = entry.match(/<title>([\s\S]*?)<\/title>/)?.[1]?.trim().replace(/\n/g, " ")
      const summary = entry.match(/<summary>([\s\S]*?)<\/summary>/)?.[1]?.trim().replace(/\n/g, " ")
      const id = entry.match(/<id>([\s\S]*?)<\/id>/)?.[1]?.trim()
      const published = entry.match(/<published>([\s\S]*?)<\/published>/)?.[1]?.trim()

      if (title && id) {
        results.push({
          title,
          url: id,
          snippet: (summary || "").slice(0, 500),
          source: "arxiv",
          published_date: published || "",
        })
      }
    }
  } catch {
    // Silent fail
  }
  return results
}

// ── PubMed Search ──

export async function searchPubmed(keywords: string[]): Promise<SearchResult[]> {
  const results: SearchResult[] = []
  try {
    const query = keywords.slice(0, 3).join(" OR ")
    const searchParams = new URLSearchParams({
      db: "pubmed",
      term: query,
      retmax: "10",
      retmode: "json",
      sort: "date",
    })
    const searchResp = await fetch(
      `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?${searchParams}`,
      { signal: AbortSignal.timeout(SEARCH_TIMEOUT) },
    )
    if (!searchResp.ok) return []
    const searchData = (await searchResp.json()) as any
    const ids: string[] = searchData.esearchresult?.idlist || []
    if (ids.length === 0) return []

    const summaryParams = new URLSearchParams({
      db: "pubmed",
      id: ids.join(","),
      retmode: "json",
    })
    const summaryResp = await fetch(
      `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?${summaryParams}`,
      { signal: AbortSignal.timeout(SEARCH_TIMEOUT) },
    )
    if (!summaryResp.ok) return []
    const summaryData = (await summaryResp.json()) as any

    for (const id of ids) {
      const doc = summaryData.result?.[id]
      if (!doc) continue
      results.push({
        title: doc.title || "",
        url: `https://pubmed.ncbi.nlm.nih.gov/${id}/`,
        snippet: doc.title || "",
        source: "pubmed",
        published_date: doc.pubdate || "",
      })
    }
  } catch {
    // Silent fail
  }
  return results
}

// ── Tushare Financial Data ──

function convertToTushareCode(code: string): string {
  const lower = code.toLowerCase()
  if (lower.startsWith("sh")) return code.slice(2) + ".SH"
  if (lower.startsWith("sz")) return code.slice(2) + ".SZ"
  if (lower.includes(".")) return code.toUpperCase()
  return code + ".SH"
}

function formatDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
}

function getLatestQuarter(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  if (month <= 3) return `${year - 1}1231`
  if (month <= 6) return `${year}0331`
  if (month <= 9) return `${year}0630`
  return `${year}0930`
}

export async function searchTushare(financeContext: any): Promise<SearchResult[]> {
  const token = process.env.TUSHARE_TOKEN
  if (!token || !financeContext?.stock_codes?.length) return []

  const results: SearchResult[] = []

  for (const code of (financeContext.stock_codes as string[]).slice(0, 3)) {
    const tsCode = convertToTushareCode(code)

    for (const dataType of (financeContext.data_types || ["quote"]) as string[]) {
      try {
        let apiName = "daily"
        const params: Record<string, string> = { ts_code: tsCode }

        if (dataType === "income") {
          apiName = "income"
          params.period = getLatestQuarter()
        } else if (dataType === "balancesheet") {
          apiName = "balancesheet"
          params.period = getLatestQuarter()
        } else {
          apiName = "daily"
          const today = new Date()
          const sixMonthsAgo = new Date(today.getTime() - 180 * 86400000)
          params.start_date = formatDate(sixMonthsAgo)
          params.end_date = formatDate(today)
        }

        const resp = await fetch("http://api.tushare.pro", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            api_name: apiName,
            token,
            params,
            fields: "",
          }),
          signal: AbortSignal.timeout(SEARCH_TIMEOUT),
        })

        if (!resp.ok) continue
        const data = (await resp.json()) as any

        if (data.data?.items?.length > 0) {
          results.push({
            title: `${tsCode} ${apiName} data`,
            url: `https://tushare.pro/document/2?doc_id=${apiName}`,
            snippet: JSON.stringify(data.data.items.slice(0, 5)),
            source: "tushare",
            published_date: new Date().toISOString().split("T")[0],
            structured_data: {
              fields: data.data.fields,
              items: data.data.items.slice(0, 20),
            },
          })
        }
      } catch {
        // Silent fail
      }
    }
  }
  return results
}
