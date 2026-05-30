const form = document.querySelector("#generator-form");
const resetButton = document.querySelector("#reset-button");
const serverStatus = document.querySelector("#server-status");
const progressLabel = document.querySelector("#progress-label");
const progressCount = document.querySelector("#progress-count");
const progressBar = document.querySelector("#progress-bar");
const summaryCompany = document.querySelector("#summary-company");
const summaryPeriod = document.querySelector("#summary-period");
const summaryStatus = document.querySelector("#summary-status");
const downloadLink = document.querySelector("#download-link");
const logOutput = document.querySelector("#log-output");

let progressTimer = null;

function setProgress(percent, label) {
  progressBar.style.width = `${percent}%`;
  progressCount.textContent = `${percent}%`;
  progressLabel.textContent = label;
}

function appendLog(message) {
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  logOutput.textContent += `[${time}] ${message}\n`;
  logOutput.scrollTop = logOutput.scrollHeight;
}

function startProgress() {
  clearInterval(progressTimer);
  let value = 8;
  setProgress(value, "Fetching MOPS statements");
  progressTimer = setInterval(() => {
    value = Math.min(value + Math.ceil(Math.random() * 6), 88);
    const label = value < 38 ? "Fetching MOPS statements" : value < 68 ? "Building workbook tabs" : "Verifying workbook";
    setProgress(value, label);
  }, 900);
}

function stopProgress(success) {
  clearInterval(progressTimer);
  progressTimer = null;
  setProgress(success ? 100 : 0, success ? "Workbook ready" : "Request failed");
}

function cleanPayload(formData) {
  return {
    companyCode: String(formData.get("companyCode") || "").trim(),
    startYear: Number(formData.get("startYear")),
    endYear: Number(formData.get("endYear")),
    reportBasis: String(formData.get("reportBasis") || "C"),
  };
}

function validatePayload(payload) {
  if (!/^\d{4,6}$/.test(payload.companyCode)) {
    return "Company code should be 4 to 6 digits.";
  }
  if (!Number.isInteger(payload.startYear) || !Number.isInteger(payload.endYear)) {
    return "Start and end years must be valid calendar years.";
  }
  if (payload.startYear < 2013 || payload.endYear > new Date().getFullYear() || payload.startYear > payload.endYear) {
    return "Use a valid year range from 2013 through the current year.";
  }
  if (payload.endYear - payload.startYear > 10) {
    return "Please keep one workbook to 11 years or fewer.";
  }
  return "";
}

async function generateWorkbook(event) {
  event.preventDefault();
  const payload = cleanPayload(new FormData(form));
  const problem = validatePayload(payload);
  downloadLink.classList.add("hidden");

  if (problem) {
    appendLog(problem);
    serverStatus.textContent = "Check inputs";
    summaryStatus.textContent = "Not generated";
    setProgress(0, "Waiting for request");
    return;
  }

  serverStatus.textContent = "Working";
  summaryCompany.textContent = `${payload.companyCode}.TW`;
  summaryPeriod.textContent = `${payload.startYear}-${payload.endYear}`;
  summaryStatus.textContent = "Generating";
  logOutput.textContent = "";
  appendLog(`Starting ${payload.companyCode}.TW workbook for ${payload.startYear}-${payload.endYear}.`);
  startProgress();

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Workbook generation failed.");
    }

    stopProgress(true);
    serverStatus.textContent = "Ready";
    summaryCompany.textContent = result.companyName ? `${result.companyCode}.TW ${result.companyName}` : `${result.companyCode}.TW`;
    summaryStatus.textContent = "Ready";
    downloadLink.href = result.downloadUrl;
    downloadLink.download = result.fileName;
    downloadLink.classList.remove("hidden");
    appendLog(`Created ${result.fileName}.`);
    appendLog("Workbook includes Summary, Income Statement, Balance Sheet, Cash Flow, and Sources tabs.");
  } catch (error) {
    stopProgress(false);
    serverStatus.textContent = "Error";
    summaryStatus.textContent = "Failed";
    appendLog(error.message);
  }
}

resetButton.addEventListener("click", () => {
  form.reset();
  document.querySelector("#company-code").value = "1464";
  document.querySelector("#start-year").value = "2020";
  document.querySelector("#end-year").value = "2025";
  setProgress(0, "Waiting for request");
  summaryCompany.textContent = "-";
  summaryPeriod.textContent = "-";
  summaryStatus.textContent = "Not generated";
  downloadLink.classList.add("hidden");
  logOutput.textContent = "";
  serverStatus.textContent = "Ready";
});

form.addEventListener("submit", generateWorkbook);
