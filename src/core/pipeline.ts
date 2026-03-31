// Harness Research MCP Server — 6-Step Research Pipeline
// Orchestrates the full deep research workflow

import fs from "node:fs"
import path from "node:path"
import type {
  EvaluatedSource,
  LLMConfig,
  ResearchPlan,
  ResearchStats,
  ResearchTask,
} from "../utils/types.js"
import { MAX_SOURCES } from "../utils/config.js"
import { generateFilename, safeJsonParse } from "../utils/json.js"
import { loadPrompt } from "../utils/prompts.js"
import { createLLMConfig, callLLM } from "./llm.js"
import {
  searchTavily,
  searchBrave,
  searchArxiv,
  searchPubmed,
  searchTushare,
} from "./search.js"
import { dedup } from "./dedup.js"
import { evaluateSources } from "./craap.js"
import { verify } from "./verify.js"
import { writeSections, writeExecSummary } from "./write.js"
import {
  generateReferencesHtml,
  mergeHtml,
  sanitizeHtml,
  htmlToMarkdown,
} from "./render-html.js"
import { renderDocx } from "./render-docx.js"
import { isPdfAvailable, renderPdf } from "./render-pdf.js"
import type { SearchResult } from "../utils/types.js"

/** In-memory task store for progress tracking */
const tasks = new Map<string, ResearchTask>()

export function getTask(id: string): ResearchTask | undefined {
  return tasks.get(id)
}

export function getAllTasks(): ResearchTask[] {
  return Array.from(tasks.values())
}

/** Progress callback type */
type ProgressCallback = (step: string, progress: number, detail: string) => void

/** Run the full 6-step research pipeline */
export async function runResearch(
  topic: string,
  options: {
    provider?: string
    model?: string
    outputDir?: string
    formats?: string[]
  },
  onProgress?: ProgressCallback,
): Promise<{
  taskId: string
  outputs: { html?: string; pdf?: string; docx?: string; markdown?: string }
  stats: ResearchStats
  summary: string
}> {
  const taskId = `research-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const startTime = Date.now()
  const llmConfig = createLLMConfig(options.provider, options.model)
  const outputDir = options.outputDir || process.cwd()
  const requestedFormats = options.formats || ["html", "docx"]

  const task: ResearchTask = {
    id: taskId,
    topic,
    status: "running",
    step: "initializing",
    progress: 0,
    startTime,
  }
  tasks.set(taskId, task)

  const report = (step: string, progress: number, detail: string) => {
    task.step = step
    task.progress = progress
    onProgress?.(step, progress, detail)
  }

  // Validate API key
  if (!llmConfig.apiKey) {
    task.status = "failed"
    task.error = `Missing API key: ${llmConfig.provider === "openrouter" ? "OPENROUTER_API_KEY" : "KIMI_API_KEY"}`
    throw new Error(task.error)
  }

  const stats: ResearchStats = {
    tavily: { queries: 0, results: 0 },
    brave: { queries: 0, results: 0 },
    arxiv: { queries: 0, results: 0 },
    pubmed: { queries: 0, results: 0 },
    tushare: { queries: 0, results: 0 },
    totalSources: 0,
    rejectedSources: 0,
    tierDistribution: {},
  }

  try {
    // ── Step 1/6: Research Plan ──
    report("Step 1/6", 5, "Generating research plan...")

    const planPrompt = loadPrompt("plan", { TOPIC: topic })
    const planRaw = await callLLM(llmConfig, planPrompt, 0.4)
    const plan = safeJsonParse<ResearchPlan>(planRaw, null as any)

    if (!plan || !plan.sections || plan.sections.length === 0) {
      throw new Error(`Research plan generation failed. Raw output: ${planRaw.slice(0, 300)}`)
    }

    const elapsed1 = Math.round((Date.now() - startTime) / 1000)
    report("Step 1/6", 15, `Done (${elapsed1}s) | Plan: ${plan.sections.length} sections`)

    // ── Step 2/6: Multi-source Search ──
    report("Step 2/6", 20, "Searching across 5 data sources...")

    const webKeywords = plan.search_keywords?.web || []
    const academicKeywords = plan.search_keywords?.academic || []

    stats.tavily.queries = Math.min(webKeywords.length, 4)
    stats.brave.queries = Math.min(webKeywords.length, 4)

    const searchPromises: Promise<SearchResult[]>[] = [
      searchTavily(webKeywords),
      searchBrave(webKeywords),
    ]
    if (plan.data_sources?.academic !== false) {
      stats.arxiv.queries = 1
      stats.pubmed.queries = 1
      searchPromises.push(searchArxiv(academicKeywords))
      searchPromises.push(searchPubmed(academicKeywords))
    }
    if (plan.data_sources?.finance && plan.finance_context) {
      stats.tushare.queries = (plan.finance_context.stock_codes || []).length
      searchPromises.push(searchTushare(plan.finance_context))
    }

    const searchResults = await Promise.allSettled(searchPromises)
    let allResults: SearchResult[] = []
    for (const r of searchResults) {
      if (r.status === "fulfilled") allResults = allResults.concat(r.value)
    }

    // Count per source
    for (const r of allResults) {
      if (r.source === "tavily") stats.tavily.results++
      else if (r.source === "brave") stats.brave.results++
      else if (r.source === "arxiv") stats.arxiv.results++
      else if (r.source === "pubmed") stats.pubmed.results++
      else if (r.source === "tushare") stats.tushare.results++
    }

    let dedupedResults = dedup(allResults)
    if (dedupedResults.length > MAX_SOURCES) {
      dedupedResults = dedupedResults.slice(0, MAX_SOURCES)
    }

    const elapsed2 = Math.round((Date.now() - startTime) / 1000)
    report("Step 2/6", 35, `Done (${elapsed2}s) | ${allResults.length} results → ${dedupedResults.length} after dedup`)

    if (dedupedResults.length === 0) {
      throw new Error("All search sources returned 0 results. Check API keys and network.")
    }

    // ── Step 3/6: CRAAP Evaluation ──
    report("Step 3/6", 40, `Evaluating ${dedupedResults.length} sources with CRAAP...`)

    const { evaluated: evaluatedSources, totalBefore } = await evaluateSources(
      dedupedResults,
      topic,
      llmConfig,
    )

    stats.totalSources = evaluatedSources.length
    stats.rejectedSources = totalBefore - evaluatedSources.length
    for (const s of evaluatedSources) {
      stats.tierDistribution[s.tier] = (stats.tierDistribution[s.tier] || 0) + 1
    }

    const elapsed3 = Math.round((Date.now() - startTime) / 1000)
    report("Step 3/6", 55, `Done (${elapsed3}s) | ${stats.totalSources}/${totalBefore} sources passed`)

    // ── Step 4/6: Cross-verification ──
    report("Step 4/6", 60, "Cross-verifying data points...")

    const verification = await verify(evaluatedSources, topic, llmConfig)

    const elapsed4 = Math.round((Date.now() - startTime) / 1000)
    report("Step 4/6", 70, `Done (${elapsed4}s) | ${verification.verified_data_points.length} verified data points`)

    // ── Step 5/6: Writing ──
    report("Step 5/6", 72, "Writing chapters in parallel...")

    const { chapters, summaries } = await writeSections(
      plan,
      evaluatedSources,
      verification,
      topic,
      llmConfig,
    )

    report("Step 5/6", 85, "Writing executive summary...")

    const execSummaryHtml = await writeExecSummary(
      topic,
      plan.core_question,
      summaries,
      verification,
      llmConfig,
    )

    const elapsed5 = Math.round((Date.now() - startTime) / 1000)
    report("Step 5/6", 88, `Done (${elapsed5}s) | ${chapters.length} chapters + summary`)

    // ── Step 6/6: Rendering ──
    report("Step 6/6", 90, "Rendering report...")

    const referencesHtml = generateReferencesHtml(evaluatedSources)
    const fullHtml = mergeHtml(topic, {
      execSummary: execSummaryHtml,
      chapters,
      references: referencesHtml,
    })

    const baseName = generateFilename()
    const outputs: { html?: string; pdf?: string; docx?: string; markdown?: string } = {}

    // Sanitize HTML
    const cleanHtml = await sanitizeHtml(fullHtml)

    // HTML output
    if (requestedFormats.includes("html")) {
      const htmlPath = path.join(outputDir, `${baseName}.html`)
      fs.writeFileSync(htmlPath, cleanHtml, "utf-8")
      outputs.html = htmlPath
    }

    // DOCX output
    if (requestedFormats.includes("docx")) {
      try {
        const docxPath = path.join(outputDir, `${baseName}.docx`)
        await renderDocx(cleanHtml, docxPath)
        if (fs.existsSync(docxPath)) {
          outputs.docx = docxPath
        }
      } catch (e: any) {
        console.error("DOCX render failed:", e.message)
      }
    }

    // PDF output (macOS only)
    if (requestedFormats.includes("pdf")) {
      const pdfOk = await isPdfAvailable()
      if (pdfOk) {
        try {
          // Write temp HTML for PDF rendering
          const tempHtmlPath = path.join(outputDir, `${baseName}-temp.html`)
          fs.writeFileSync(tempHtmlPath, cleanHtml, "utf-8")
          const pdfPath = path.join(outputDir, `${baseName}.pdf`)
          const success = await renderPdf(tempHtmlPath, pdfPath)
          if (success) outputs.pdf = pdfPath
          // Cleanup temp
          if (fs.existsSync(tempHtmlPath)) fs.unlinkSync(tempHtmlPath)
        } catch (e: any) {
          console.error("PDF render failed:", e.message)
        }
      }
    }

    // Markdown output (always generated as fallback)
    const markdown = htmlToMarkdown(cleanHtml)
    const mdPath = path.join(outputDir, `${baseName}.md`)
    fs.writeFileSync(mdPath, markdown, "utf-8")
    outputs.markdown = mdPath

    const elapsed6 = Math.round((Date.now() - startTime) / 1000)
    report("Step 6/6", 100, `Complete (${elapsed6}s)`)

    // Update task
    task.status = "completed"
    task.endTime = Date.now()
    task.outputs = outputs

    const outputList = Object.entries(outputs)
      .map(([format, filePath]) => `  ${format.toUpperCase()}: ${filePath}`)
      .join("\n")

    const tierDist = Object.entries(stats.tierDistribution)
      .map(([t, c]) => `T${t}:${c}`)
      .join(" | ")

    const summary = `Deep research report generated!

Output files:
${outputList}

Statistics:
- Duration: ${elapsed6}s
- LLM: ${llmConfig.provider} (${llmConfig.model})
- Search results: ${allResults.length} (${dedupedResults.length} after dedup)
- CRAAP evaluation: ${stats.totalSources}/${totalBefore} passed (threshold 4.5)
- Source tiers: ${tierDist}
- Sections: ${chapters.length} + executive summary + references
- Verified data points: ${verification.verified_data_points.length}
- Conflicting data points: ${verification.conflicting_data_points.length}`

    return { taskId, outputs, stats, summary }
  } catch (e: any) {
    task.status = "failed"
    task.error = e.message
    task.endTime = Date.now()
    throw e
  }
}
