// Harness Research MCP Server — DOCX Rendering
// Pure JavaScript using npm `docx` package — works on all platforms

import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  BorderStyle,
  Table,
  TableRow,
  TableCell,
  WidthType,
  ExternalHyperlink,
  ShadingType,
} from "docx"
import fs from "node:fs"

interface ParsedSection {
  type: "heading1" | "heading2" | "heading3" | "paragraph" | "list-item" | "table"
  text: string
  rows?: string[][]
}

/** Parse HTML into simple structure for DOCX conversion */
function parseHtmlForDocx(html: string): ParsedSection[] {
  const sections: ParsedSection[] = []

  // Strip wrapping HTML/head/body
  let body = html
    .replace(/<!DOCTYPE[\s\S]*?<body[^>]*>/i, "")
    .replace(/<\/body[\s\S]*$/i, "")
    .replace(/<div class="report-container">/i, "")

  // Split by major HTML tags
  const tagRegex = /<(h[123]|p|li|table|div)[^>]*>([\s\S]*?)<\/\1>/gi
  let match: RegExpExecArray | null

  while ((match = tagRegex.exec(body)) !== null) {
    const tag = match[1].toLowerCase()
    let content = match[2]
      .replace(/<[^>]+>/g, " ")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'")
      .replace(/\s+/g, " ")
      .trim()

    if (!content) continue

    if (tag === "h1") sections.push({ type: "heading1", text: content })
    else if (tag === "h2") sections.push({ type: "heading2", text: content })
    else if (tag === "h3") sections.push({ type: "heading3", text: content })
    else if (tag === "li") sections.push({ type: "list-item", text: content })
    else if (tag === "table") {
      // Parse table rows
      const rows: string[][] = []
      const rowMatches = match[0].match(/<tr[\s\S]*?<\/tr>/gi) || []
      for (const row of rowMatches) {
        const cells = (row.match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi) || [])
          .map(c => c.replace(/<[^>]+>/g, "").trim())
        if (cells.length > 0) rows.push(cells)
      }
      if (rows.length > 0) sections.push({ type: "table", text: "", rows })
    } else {
      sections.push({ type: "paragraph", text: content })
    }
  }

  return sections
}

/** Create DOCX table from rows */
function createTable(rows: string[][], isHeader: boolean = true): Table {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map((cells, rowIdx) =>
      new TableRow({
        children: cells.map(cell =>
          new TableCell({
            children: [
              new Paragraph({
                children: [
                  new TextRun({
                    text: cell,
                    bold: isHeader && rowIdx === 0,
                    size: 18,
                    font: "Microsoft YaHei",
                  }),
                ],
              }),
            ],
            shading:
              isHeader && rowIdx === 0
                ? { type: ShadingType.SOLID, color: "1a365d", fill: "1a365d" }
                : undefined,
          }),
        ),
      }),
    ),
  })
}

/** Render HTML report to DOCX file */
export async function renderDocx(html: string, outputPath: string): Promise<void> {
  const sections = parseHtmlForDocx(html)

  const children: (Paragraph | Table)[] = []

  for (const section of sections) {
    switch (section.type) {
      case "heading1":
        children.push(
          new Paragraph({
            text: section.text,
            heading: HeadingLevel.HEADING_1,
            spacing: { before: 400, after: 200 },
          }),
        )
        break
      case "heading2":
        children.push(
          new Paragraph({
            text: section.text,
            heading: HeadingLevel.HEADING_2,
            spacing: { before: 300, after: 150 },
          }),
        )
        break
      case "heading3":
        children.push(
          new Paragraph({
            text: section.text,
            heading: HeadingLevel.HEADING_3,
            spacing: { before: 200, after: 100 },
          }),
        )
        break
      case "list-item":
        children.push(
          new Paragraph({
            children: [
              new TextRun({ text: `• ${section.text}`, size: 21, font: "Microsoft YaHei" }),
            ],
            spacing: { before: 60, after: 60 },
            indent: { left: 400 },
          }),
        )
        break
      case "table":
        if (section.rows && section.rows.length > 0) {
          children.push(createTable(section.rows))
          children.push(new Paragraph({ text: "", spacing: { after: 120 } }))
        }
        break
      default:
        children.push(
          new Paragraph({
            children: [
              new TextRun({ text: section.text, size: 21, font: "Microsoft YaHei" }),
            ],
            spacing: { before: 80, after: 80 },
          }),
        )
    }
  }

  // Add footer
  children.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `\n---\nGenerated by Harness Research MCP | ${new Date().toISOString().split("T")[0]}`,
          size: 16,
          color: "999999",
          font: "Microsoft YaHei",
        }),
      ],
      spacing: { before: 600 },
      alignment: AlignmentType.CENTER,
    }),
  )

  const doc = new Document({
    sections: [
      {
        properties: {
          page: {
            margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
          },
        },
        children,
      },
    ],
    styles: {
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          run: { size: 21, font: "Microsoft YaHei" },
          paragraph: { spacing: { line: 360 } },
        },
      ],
    },
  })

  const buffer = await Packer.toBuffer(doc)
  fs.writeFileSync(outputPath, buffer)
}
