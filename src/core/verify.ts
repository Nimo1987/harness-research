// Harness Research MCP Server — Cross-verification & Contradiction Analysis

import type { EvaluatedSource, LLMConfig, VerificationResult } from "../utils/types.js"
import { callLLM } from "./llm.js"
import { loadPrompt } from "../utils/prompts.js"
import { safeJsonParse } from "../utils/json.js"

/** Run cross-verification on evaluated sources */
export async function verify(
  sources: EvaluatedSource[],
  topic: string,
  llmConfig: LLMConfig,
): Promise<VerificationResult> {
  const factsText = sources
    .map(
      s =>
        `URL: ${s.url}\nTitle: ${s.title}\nTier: T${s.tier}\nKey facts: ${s.key_facts.join("; ")}`,
    )
    .join("\n\n")

  const verifyPrompt = loadPrompt("verify", {
    TOPIC: topic,
    FACTS: factsText,
  })

  const verifyRaw = await callLLM(llmConfig, verifyPrompt)
  return safeJsonParse<VerificationResult>(verifyRaw, {
    verified_data_points: [],
    conflicting_data_points: [],
    counterintuitive_findings: [],
  })
}
