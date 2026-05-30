# Taiwan Financial Statement Excel Builder

Local app for generating Excel workbooks from Taiwan eMOPS/MOPS financial statement pages.

## Run

Recommended on Windows:

```bat
start-app.cmd
```

PowerShell alternative:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-app.ps1
```

Then open:

```text
http://localhost:4173
```

## Publish Online

This app needs backend hosting because `server.mjs` generates workbooks through `POST /api/generate`. Static hosts such as GitHub Pages can show the page but cannot run the generator.

See `DEPLOY.md` for deployment requirements.

## What It Creates

Each generated workbook includes:

- Summary
- Income Statement
- Balance Sheet
- Cash Flow
- Sources

The app accepts a Taiwan company code, year range, and report basis. Workbooks are generated under `work/generated/` and are also available through the app download link.

## Folder Map

- `index.html`, `styles.css`, `app.js` - browser interface
- `server.mjs` - local HTTP server and workbook download routes
- `financial-generator.mjs` - workbook generation logic
- `scripts/fetch_mops.py` - MOPS/eMOPS fetch helper
- `work/generated/` - generated Excel files
- `_archive/` - duplicate files kept out of the main app folder
