// Harness Research MCP Server — PDF Rendering
// Uses Puppeteer (headless Chromium) — macOS only, optional dependency

import fs from "node:fs"

/** Check if PDF rendering is available (puppeteer installed + macOS) */
export async function isPdfAvailable(): Promise<boolean> {
  if (process.platform !== "darwin") return false
  try {
    await import("puppeteer")
    return true
  } catch {
    return false
  }
}

/** Render HTML file to PDF using Puppeteer */
export async function renderPdf(htmlPath: string, pdfPath: string): Promise<boolean> {
  try {
    const puppeteer = await import("puppeteer")
    const browser = await puppeteer.default.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    })

    const page = await browser.newPage()

    const htmlContent = fs.readFileSync(htmlPath, "utf-8")
    await page.setContent(htmlContent, { waitUntil: "networkidle0", timeout: 60000 })

    await page.pdf({
      path: pdfPath,
      format: "A4",
      printBackground: true,
      margin: { top: "20mm", right: "15mm", bottom: "20mm", left: "15mm" },
      displayHeaderFooter: true,
      headerTemplate: "<div></div>",
      footerTemplate: `
        <div style="font-size:8px; text-align:center; width:100%; color:#999;">
          Harness Research Report — Page <span class="pageNumber"></span> of <span class="totalPages"></span>
        </div>`,
    })

    await browser.close()
    return fs.existsSync(pdfPath)
  } catch (e) {
    console.error("PDF rendering failed:", e)
    return false
  }
}
