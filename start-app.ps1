$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundledNode = "C:\Users\cheng\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$node = if (Test-Path $bundledNode) { $bundledNode } else { "node" }

Set-Location $workspace
Write-Host "Starting Taiwan financial statement Excel builder..."
Write-Host "Open http://localhost:4173 in your browser."
& $node server.mjs
