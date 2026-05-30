import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const generatedDir = path.join(__dirname, "work", "generated");
const bundledPythonPath = "C:/Users/cheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";

function safeSegment(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, "_");
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.PYTHON) {
    candidates.push({ command: process.env.PYTHON, args: [] });
  }
  candidates.push(
    { command: bundledPythonPath, args: [] },
    { command: "python3", args: [] },
    { command: "python", args: [] },
    { command: "py", args: ["-3"] },
  );
  return candidates;
}

function runPythonCommand(command, commandArgs, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [...commandArgs, ...args], { cwd: __dirname, windowsHide: true });
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(new Error(stderr.trim() || stdout.trim() || `Python exited with code ${code}`));
      }
    });
  });
}

async function runPython(args) {
  const errors = [];
  for (const candidate of pythonCandidates()) {
    try {
      return await runPythonCommand(candidate.command, candidate.args, args);
    } catch (error) {
      if (error.code === "ENOENT") {
        errors.push(`${candidate.command}: not found`);
        continue;
      }
      throw error;
    }
  }
  throw new Error(`Python 3 was not found. Set the PYTHON environment variable. Tried: ${errors.join("; ")}`);
}

export async function generateFinancialWorkbook({ companyCode, startYear, endYear, reportBasis }) {
  const code = safeSegment(companyCode);
  const basis = ["A", "B", "C"].includes(reportBasis) ? reportBasis : "C";
  const runId = `${code}_${startYear}_${endYear}_${basis}_${Date.now()}`;
  const runDir = path.join(generatedDir, runId);
  await fs.mkdir(runDir, { recursive: true });

  const jsonPath = path.join(runDir, "mops_data.json");
  await runPython([
    path.join(__dirname, "scripts", "fetch_mops.py"),
    "--company-code",
    code,
    "--start-year",
    String(startYear),
    "--end-year",
    String(endYear),
    "--report-basis",
    basis,
    "--output",
    jsonPath,
  ]);

  const data = JSON.parse(await fs.readFile(jsonPath, "utf8"));
  const fileName = `${code}_TW_financial_statements_${startYear}_${endYear}.xlsx`;
  const outputPath = path.join(runDir, fileName);
  await runPython([
    path.join(__dirname, "scripts", "build_workbook.py"),
    "--input",
    jsonPath,
    "--output",
    outputPath,
  ]);

  return {
    companyCode: code,
    companyName: data.company_name,
    fileName,
    filePath: outputPath,
    runId,
  };
}
