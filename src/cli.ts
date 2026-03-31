// Harness Research MCP Server — CLI Entry
// Handles setup wizard and doctor commands

import { setupWizard } from "./setup/wizard.js"
import { runDoctor } from "./setup/doctor.js"

export async function run(command: string): Promise<void> {
  switch (command) {
    case "setup":
      await setupWizard()
      break
    case "doctor":
      await runDoctor()
      break
    default:
      console.log(`Unknown command: ${command}`)
      console.log("Available commands: setup, doctor, serve (default)")
      process.exit(1)
  }
}
