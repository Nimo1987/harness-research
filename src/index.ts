// Harness Research MCP Server — Main Entry Point
// Registers tools and starts stdio transport

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { z } from "zod"
import { loadEnv, isSetupComplete, hasMinimalKeys, getPlatformCapabilities } from "./utils/config.js"
import { runResearch, startResearchBackground, getTask, getAllTasks } from "./core/pipeline.js"
import { searchTavily, searchBrave, searchArxiv, searchPubmed } from "./core/search.js"
import { dedup } from "./core/dedup.js"

// Load environment
loadEnv()

const server = new McpServer({
  name: "harness-research",
  version: "2.0.0",
  capabilities: {
    tools: {},
  },
})

// ── Tool 1: harness_research (full deep research) ──

server.tool(
  "harness_research",
  `Start a deep research session: multi-source search (Tavily/Brave/arXiv/PubMed/Tushare) + CRAAP source evaluation + cross-verification → professional HTML/DOCX/PDF report.

IMPORTANT: This tool returns IMMEDIATELY with a task_id. The research runs in the background and takes ~8-12 minutes. After calling this tool, you MUST poll harness_status with the returned task_id every 30-60 seconds until status is "completed" or "failed". Do NOT wait idle — poll actively.

Workflow:
1. Call harness_research → get task_id (returns in <1 second)
2. Call harness_status with task_id every 30-60s to check progress
3. When status is "completed", harness_status returns the output file paths

Driven by affordable models like Kimi K2.5 (~$0.01/run).`,
  {
    topic: z.string().describe("Research topic, e.g. 'Global AI chip market landscape 2025'"),
    provider: z.enum(["kimi", "openrouter"]).optional().describe("LLM provider: kimi (default, cheapest) or openrouter"),
    model: z.string().optional().describe("Model name. kimi default: kimi-k2.5, openrouter default: anthropic/claude-sonnet-4"),
    output_dir: z.string().optional().describe("Output directory for reports. Defaults to current working directory."),
    formats: z.array(z.enum(["html", "docx", "pdf"])).optional().describe("Output formats. Default: ['html', 'docx']. PDF only available on macOS."),
  },
  async (args) => {
    // Pre-flight checks
    if (!isSetupComplete() && !hasMinimalKeys()) {
      return {
        content: [
          {
            type: "text" as const,
            text: "Harness Research is not configured yet.\n\nPlease run:\n  npx harness-research-mcp setup\n\nThis will guide you through API key configuration.",
          },
        ],
      }
    }

    if (!hasMinimalKeys()) {
      return {
        content: [
          {
            type: "text" as const,
            text: "Missing required API keys. You need at least:\n1. One search key (TAVILY_API_KEY or BRAVE_API_KEY)\n2. One LLM key (KIMI_API_KEY or OPENROUTER_API_KEY)\n\nRun: npx harness-research-mcp setup",
          },
        ],
      }
    }

    // Start research in background (fire-and-forget), return task_id immediately
    const taskId = startResearchBackground(args.topic, {
      provider: args.provider,
      model: args.model,
      outputDir: args.output_dir,
      formats: args.formats,
    })

    return {
      content: [
        {
          type: "text" as const,
          text: `Research started!\n\nTask ID: ${taskId}\nTopic: ${args.topic}\n\nThe research is running in the background and will take ~8-12 minutes.\nPoll progress with: harness_status(task_id="${taskId}")\nPoll every 30-60 seconds until status is "completed".`,
        },
      ],
    }
  },
)

// ── Tool 2: harness_search (quick multi-source search) ──

server.tool(
  "harness_search",
  "Quick multi-source search without generating a full report. Returns structured results from Tavily, Brave, arXiv, and PubMed. Completes in seconds.",
  {
    query: z.string().describe("Search query"),
    sources: z.array(z.enum(["tavily", "brave", "arxiv", "pubmed"])).optional()
      .describe("Which sources to search. Default: all available."),
    limit: z.number().optional().describe("Max results per source. Default: 5."),
  },
  async (args) => {
    if (!hasMinimalKeys()) {
      return {
        content: [{ type: "text" as const, text: "Missing API keys. Run: npx harness-research-mcp setup" }],
      }
    }

    const sources = args.sources || ["tavily", "brave", "arxiv", "pubmed"]
    const keywords = [args.query]

    const promises: Promise<any[]>[] = []
    if (sources.includes("tavily")) promises.push(searchTavily(keywords))
    if (sources.includes("brave")) promises.push(searchBrave(keywords))
    if (sources.includes("arxiv")) promises.push(searchArxiv(keywords))
    if (sources.includes("pubmed")) promises.push(searchPubmed(keywords))

    const results = await Promise.allSettled(promises)
    let all: any[] = []
    for (const r of results) {
      if (r.status === "fulfilled") all = all.concat(r.value)
    }

    const dedupedResults = dedup(all).slice(0, args.limit || 20)

    const text = dedupedResults.length === 0
      ? "No results found."
      : dedupedResults
        .map(
          (r, i) =>
            `[${i + 1}] ${r.title}\n    ${r.url}\n    Source: ${r.source} | ${r.published_date || "N/A"}\n    ${r.snippet.slice(0, 200)}`,
        )
        .join("\n\n")

    return {
      content: [
        {
          type: "text" as const,
          text: `Found ${dedupedResults.length} results for "${args.query}":\n\n${text}`,
        },
      ],
    }
  },
)

// ── Tool 3: harness_status (check research task progress) ──

server.tool(
  "harness_status",
  `Check the progress of a research task started by harness_research.

After calling harness_research, you MUST poll this tool with the returned task_id every 30-60 seconds.
- status "running": research is in progress, keep polling
- status "completed": research is done, output file paths are included
- status "failed": an error occurred, error message is included

If no task_id is provided, lists all tasks.`,
  {
    task_id: z.string().optional().describe("Task ID to check. If omitted, lists all tasks."),
  },
  async (args) => {
    if (args.task_id) {
      const task = getTask(args.task_id)
      if (!task) {
        return {
          content: [{ type: "text" as const, text: `Task not found: ${args.task_id}` }],
        }
      }

      const duration = task.endTime
        ? `${Math.round((task.endTime - task.startTime) / 1000)}s`
        : `${Math.round((Date.now() - task.startTime) / 1000)}s (running)`

      let text = `Task: ${task.id}\nTopic: ${task.topic}\nStatus: ${task.status}\nStep: ${task.step}\nProgress: ${task.progress}%\nDuration: ${duration}`

      if (task.error) text += `\nError: ${task.error}`
      if (task.outputs) {
        text += "\nOutputs:"
        for (const [fmt, filePath] of Object.entries(task.outputs)) {
          if (filePath) text += `\n  ${fmt.toUpperCase()}: ${filePath}`
        }
      }

      return { content: [{ type: "text" as const, text }] }
    }

    // List all tasks
    const allTasks = getAllTasks()
    if (allTasks.length === 0) {
      return { content: [{ type: "text" as const, text: "No research tasks found." }] }
    }

    const text = allTasks
      .map(t => `[${t.status}] ${t.id} — "${t.topic}" (${t.progress}%)`)
      .join("\n")

    return { content: [{ type: "text" as const, text: `Research tasks:\n${text}` }] }
  },
)

// ── Start server ──

async function main() {
  const transport = new StdioServerTransport()
  await server.connect(transport)
}

main().catch(console.error)
