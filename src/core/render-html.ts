// Harness Research MCP Server — HTML Rendering
// Pure TypeScript, zero native dependencies, works on all platforms

import fs from "node:fs"
import path from "node:path"
import { RESOURCE_DIR } from "../utils/config.js"
import { escapeHtml } from "../utils/json.js"
import type { EvaluatedSource } from "../utils/types.js"

/** Generate references HTML section */
export function generateReferencesHtml(sources: EvaluatedSource[]): string {
  const sorted = [...sources].sort((a, b) => {
    if (a.tier !== b.tier) return a.tier - b.tier
    return (b.craapScore || 0) - (a.craapScore || 0)
  })

  let html = `<h2>Research Methodology & References</h2>\n`
  html += `<p>Primary references after multi-source cross-verification and CRAAP evaluation:</p>\n`
  html += `<ol class="references">\n`
  for (let i = 0; i < sorted.length; i++) {
    const s = sorted[i]
    html += `<li>[${i + 1}] <span class="tier-badge t${s.tier}">T${s.tier}</span> ${escapeHtml(s.title)} — `
    html += `<a href="${escapeHtml(s.url)}">${escapeHtml(s.url)}</a>`
    if (s.published_date) html += ` <span class="ref-meta">(${s.published_date})</span>`
    html += `</li>\n`
  }
  html += `</ol>\n`
  return html
}

/** Merge all HTML sections into a complete report */
export function mergeHtml(
  title: string,
  sections: {
    execSummary: string
    chapters: string[]
    references: string
  },
): string {
  const date = new Date().toISOString().split("T")[0]
  const stylesPath = path.join(RESOURCE_DIR, "styles.css")
  const styles = fs.existsSync(stylesPath) ? fs.readFileSync(stylesPath, "utf-8") : ""

  let content = ""
  content += `<h1 class="report-title">${escapeHtml(title)}</h1>\n`
  content += `<div class="report-meta">AI-Assisted Deep Research Report | ${date} | Harness Research</div>\n`
  content += sections.execSummary + "\n"
  for (const ch of sections.chapters) {
    content += ch + "\n"
  }
  content += sections.references + "\n"

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>${escapeHtml(title)}</title>
  <style>${styles}</style>
</head>
<body>
  <div class="report-container">
    ${content}
  </div>
</body>
</html>`
}

/** Sanitize HTML — replace Python BeautifulSoup with cheerio */
export async function sanitizeHtml(html: string): Promise<string> {
  try {
    const { load } = await import("cheerio")
    const $ = load(html)

    // Remove script/style injection
    $("script").remove()
    $("iframe").remove()

    // Clean markdown residue inside HTML
    $("body *").each((_, el) => {
      const $el = $(el)
      const text = $el.html() || ""
      if (text.includes("```")) {
        $el.html(text.replace(/```[\s\S]*?```/g, ""))
      }
    })

    // Remove empty paragraphs
    $("p").each((_, el) => {
      const $el = $(el)
      if (!$el.text().trim()) $el.remove()
    })

    return $.html()
  } catch {
    // Fallback: basic regex cleanup if cheerio fails
    return html
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
      .replace(/```[\s\S]*?```/g, "")
  }
}

/** Convert HTML to Markdown (for text-based output) */
export function htmlToMarkdown(html: string): string {
  let md = html
  md = md.replace(/<!DOCTYPE[\s\S]*?<div class="report-container">\s*/i, "")
  md = md.replace(/<\/div>\s*<\/body>\s*<\/html>\s*$/i, "")
  md = md.replace(/<h1[^>]*class="report-title"[^>]*>([\s\S]*?)<\/h1>/gi, "# $1\n\n")
  md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, "# $1\n\n")
  md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, "## $1\n\n")
  md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, "### $1\n\n")
  md = md.replace(/<div class="report-meta">([\s\S]*?)<\/div>/gi, "*$1*\n\n---\n\n")
  md = md.replace(/<strong>([\s\S]*?)<\/strong>/gi, "**$1**")
  md = md.replace(/<em>([\s\S]*?)<\/em>/gi, "*$1*")
  md = md.replace(/<sup>\[(\d+)\]<\/sup>/gi, "[$1]")
  md = md.replace(/<sup>([\s\S]*?)<\/sup>/gi, "^($1)")
  md = md.replace(/<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, "[$2]($1)")
  md = md.replace(/<span class="confidence[^"]*">([\s\S]*?)<\/span>/gi, " $1 ")
  md = md.replace(/<span class="tier-badge[^"]*">([\s\S]*?)<\/span>/gi, "[$1]")
  md = md.replace(/<div class="counterintuitive-finding">[\s\S]*?<span class="finding-label">[\s\S]*?<\/span>([\s\S]*?)<\/div>/gi, "\n> **Counterintuitive Finding**: $1\n\n")
  md = md.replace(/<div class="contradiction-signal">[\s\S]*?<span class="signal-label">[\s\S]*?<\/span>([\s\S]*?)<\/div>/gi, "\n> **Contradiction Signal**: $1\n\n")
  md = md.replace(/<div class="source-note">([\s\S]*?)<\/div>/gi, "\n*$1*\n\n")
  md = md.replace(/<caption>([\s\S]*?)<\/caption>/gi, "\n**$1**\n\n")
  md = md.replace(/<table[\s\S]*?<\/table>/gi, (tableHtml) => {
    const rows: string[][] = []
    const rowMatches = tableHtml.match(/<tr[\s\S]*?<\/tr>/gi) || []
    for (const row of rowMatches) {
      const cells = (row.match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi) || [])
        .map(c => c.replace(/<[^>]+>/g, "").trim())
      if (cells.length > 0) rows.push(cells)
    }
    if (rows.length === 0) return ""
    const colWidths = rows[0].map((_, i) =>
      Math.max(...rows.map(r => (r[i] || "").length), 3),
    )
    let table = "\n"
    for (let i = 0; i < rows.length; i++) {
      table += "| " + rows[i].map((c, j) => c.padEnd(colWidths[j] || 3)).join(" | ") + " |\n"
      if (i === 0) {
        table += "| " + colWidths.map(w => "-".repeat(w)).join(" | ") + " |\n"
      }
    }
    return table + "\n"
  })
  md = md.replace(/<li>([\s\S]*?)<\/li>/gi, "- $1\n")
  md = md.replace(/<\/?[uo]l[^>]*>/gi, "\n")
  md = md.replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, "$1\n\n")
  md = md.replace(/<[^>]+>/g, "")
  md = md.replace(/\n{4,}/g, "\n\n\n")
  md = md.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  md = md.replace(/&quot;/g, '"').replace(/&#039;/g, "'")
  return md.trim() + "\n"
}
