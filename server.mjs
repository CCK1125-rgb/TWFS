import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { generateFinancialWorkbook } from "./financial-generator.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || "0.0.0.0";
const generatedRoot = path.join(__dirname, "work", "generated");

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

async function readRequestJson(req) {
  let body = "";
  for await (const chunk of req) {
    body += chunk;
    if (body.length > 20_000) {
      throw new Error("Request body is too large.");
    }
  }
  return JSON.parse(body || "{}");
}

function validateGeneratePayload(payload) {
  const companyCode = String(payload.companyCode || "").trim();
  const startYear = Number(payload.startYear);
  const endYear = Number(payload.endYear);
  const reportBasis = String(payload.reportBasis || "C").trim().toUpperCase();
  const currentYear = new Date().getFullYear();

  if (!/^\d{4,6}$/.test(companyCode)) {
    throw new Error("Company code should be 4 to 6 digits.");
  }
  if (!Number.isInteger(startYear) || !Number.isInteger(endYear)) {
    throw new Error("Start and end years must be valid calendar years.");
  }
  if (startYear < 2013 || endYear > currentYear || startYear > endYear) {
    throw new Error(`Use a valid year range from 2013 through ${currentYear}.`);
  }
  if (endYear - startYear > 10) {
    throw new Error("Please keep one workbook to 11 years or fewer.");
  }
  if (!["A", "B", "C"].includes(reportBasis)) {
    throw new Error("Report basis must be A, B, or C.");
  }
  return { companyCode, startYear, endYear, reportBasis };
}

async function serveStatic(res, pathname) {
  const fileName = pathname === "/" ? "index.html" : pathname.slice(1);
  const filePath = path.normalize(path.join(__dirname, fileName));
  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  try {
    const ext = path.extname(filePath);
    const content = await fs.readFile(filePath);
    res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
}

async function serveDownload(res, pathname) {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length !== 3) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  const [, runId, fileName] = parts;
  const filePath = path.normalize(path.join(generatedRoot, runId, fileName));
  if (!filePath.startsWith(generatedRoot) || !fileName.endsWith(".xlsx")) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  try {
    const content = await fs.readFile(filePath);
    res.writeHead(200, {
      "Content-Type": mimeTypes[".xlsx"],
      "Content-Disposition": `attachment; filename="${fileName}"`,
    });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  try {
    if (req.method === "POST" && url.pathname === "/api/generate") {
      const payload = validateGeneratePayload(await readRequestJson(req));
      const workbook = await generateFinancialWorkbook(payload);
      sendJson(res, 200, {
        companyCode: workbook.companyCode,
        companyName: workbook.companyName,
        fileName: workbook.fileName,
        downloadUrl: `/downloads/${workbook.runId}/${workbook.fileName}`,
      });
      return;
    }

    if (req.method === "GET" && url.pathname.startsWith("/downloads/")) {
      await serveDownload(res, url.pathname);
      return;
    }

    if (req.method === "GET") {
      await serveStatic(res, url.pathname);
      return;
    }

    res.writeHead(405);
    res.end("Method not allowed");
  } catch (error) {
    sendJson(res, 400, { error: error.message || "Unexpected error." });
  }
});

server.listen(port, host, () => {
  console.log(`Financial statement app running at http://${host}:${port}`);
});
