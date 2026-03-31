import { defineConfig } from "tsup"

export default defineConfig({
  entry: {
    index: "src/index.ts",
    cli: "src/cli.ts",
  },
  format: ["esm"],
  target: "node18",
  outDir: "dist",
  clean: true,
  splitting: false,
  sourcemap: true,
  dts: false,
  shims: true,
  external: [
    "@modelcontextprotocol/sdk",
    "cheerio",
    "docx",
    "yaml",
    "zod",
    "puppeteer",
  ],
  banner: {
    js: "// Harness Research MCP Server v2.0.0",
  },
})
