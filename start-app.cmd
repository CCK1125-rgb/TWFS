@echo off
setlocal

cd /d "%~dp0"
set "BUNDLED_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if exist "%BUNDLED_NODE%" (
  set "NODE_EXE=%BUNDLED_NODE%"
) else (
  set "NODE_EXE=node"
)

echo Starting Taiwan financial statement Excel builder...
echo Open http://localhost:4173 in your browser.
"%NODE_EXE%" server.mjs

endlocal
