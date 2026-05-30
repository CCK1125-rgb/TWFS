# Deploying TWFS

TWFS is a Node.js web app with a Python helper. It cannot be published as a static-only site because the browser calls `POST /api/generate` and downloads generated `.xlsx` files from the Node server.

## Runtime Requirements

- Docker, or Render's Docker runtime
- A writable `work/generated/` directory

## Render or Railway Shape

Use a Node web service, not static hosting.

This repository includes `render.yaml`, so Render can create the web service from the repo.

Render should detect the Blueprint and build the included `Dockerfile`. The container runs:

```bash
node server.mjs
```

The container sets:

```text
HOST=0.0.0.0
PORT=10000
PYTHON=/opt/venv/bin/python
```

## Local Check

```bash
npm run check
```

On Windows, `start-app.cmd` and `start-app.ps1` still work for local use.
