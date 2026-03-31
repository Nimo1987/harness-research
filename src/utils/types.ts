// Harness Research MCP Server — Types
// Shared type definitions across all modules

export interface SearchResult {
  title: string
  url: string
  snippet: string
  source: "tavily" | "brave" | "arxiv" | "pubmed" | "tushare"
  published_date: string
  structured_data?: any
}

export interface EvaluatedSource extends SearchResult {
  tier: number
  weight: number
  currency: number
  authority: number
  relevance: number
  accuracy: number
  purpose: number
  craapScore: number
  key_facts: string[]
}

export interface ResearchPlan {
  domain: string
  core_question: string
  sections: Array<{
    id: number
    title: string
    purpose: string
    key_data_points: string[]
  }>
  search_keywords: {
    web: string[]
    academic: string[]
    financial: string[]
  }
  data_sources: {
    web_search: boolean
    academic: boolean
    finance: boolean
  }
  finance_context: {
    stock_codes: string[]
    data_types: string[]
    keywords: string[]
  }
}

export interface VerificationResult {
  verified_data_points: Array<{
    claim: string
    supporting_sources: string[]
    confidence: string
  }>
  conflicting_data_points: Array<{
    claim: string
    versions: Array<{ source: string; value: string }>
    recommended_value: string
    reason: string
  }>
  counterintuitive_findings: Array<{
    finding: string
    evidence: string[]
    confidence: string
  }>
}

export interface ResearchStats {
  tavily: { queries: number; results: number }
  brave: { queries: number; results: number }
  arxiv: { queries: number; results: number }
  pubmed: { queries: number; results: number }
  tushare: { queries: number; results: number }
  totalSources: number
  rejectedSources: number
  tierDistribution: Record<number, number>
}

export interface LLMConfig {
  provider: "kimi" | "openrouter"
  model: string
  apiKey: string
  baseUrl: string
}

export interface ResearchTask {
  id: string
  topic: string
  status: "running" | "completed" | "failed"
  step: string
  progress: number // 0-100
  startTime: number
  endTime?: number
  error?: string
  outputs?: {
    html?: string
    pdf?: string
    docx?: string
    markdown?: string
  }
}
