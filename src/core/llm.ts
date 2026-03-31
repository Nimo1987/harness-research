// Harness Research MCP Server — LLM Abstraction Layer

import type { LLMConfig } from "../utils/types.js"
import { sleep } from "../utils/json.js"
import { LLM_TIMEOUT } from "../utils/config.js"

/** Create LLM config from provider/model selection */
export function createLLMConfig(provider?: string, model?: string): LLMConfig {
  if (provider === "openrouter") {
    return {
      provider: "openrouter",
      model: model || "anthropic/claude-sonnet-4",
      apiKey: process.env.OPENROUTER_API_KEY || "",
      baseUrl: "https://openrouter.ai/api/v1",
    }
  }
  return {
    provider: "kimi",
    model: model || "kimi-k2.5",
    apiKey: process.env.KIMI_API_KEY || "",
    baseUrl: process.env.KIMI_BASE_URL || "https://api.moonshot.ai/v1",
  }
}

/** Call LLM with retry logic */
export async function callLLM(
  config: LLMConfig,
  prompt: string,
  temperature: number = 0.3
): Promise<string> {
  const url = `${config.baseUrl.replace(/\/$/, "")}/chat/completions`

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${config.apiKey}`,
          ...(config.provider === "openrouter" ? {
            "HTTP-Referer": "https://github.com/Nimo1987/harness-research",
            "X-Title": "Harness Research",
          } : {}),
        },
        body: JSON.stringify({
          model: config.model,
          messages: [{ role: "user", content: prompt }],
          temperature: config.provider === "kimi" ? 1 : temperature,
          max_tokens: 8192,
        }),
        signal: AbortSignal.timeout(LLM_TIMEOUT),
      })

      if (resp.status === 429) {
        const waitSec = attempt * 30
        await sleep(waitSec * 1000)
        continue
      }

      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(`LLM API ${resp.status}: ${text.slice(0, 200)}`)
      }

      const data = (await resp.json()) as any
      return data.choices?.[0]?.message?.content || ""
    } catch (e: any) {
      if (attempt === 3) throw e
      if (e.name === "TimeoutError") {
        await sleep(5000)
        continue
      }
      throw e
    }
  }
  throw new Error("LLM call failed after 3 retries")
}
