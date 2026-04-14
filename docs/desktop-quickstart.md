# Desktop Quickstart

## What This Adds

This repository now includes a stronger desktop runtime in two layers:

- `desktop/` hosts the optional Electron app
- `scripts/manual_up_desktop.ps1` prepares Redis, builds a local desktop frontend, and opens a desktop-style window
- if Electron is unavailable, the script falls back to Microsoft Edge app mode automatically

The desktop app now loads a local built frontend from `web/dist-desktop/` and starts the backend API plus Celery worker itself after launch. Desktop mode defaults to a local SQLite database file under `backend/data/desktop/`. This is much closer to a real desktop deployment shape than the earlier dev-server wrapper.

## First-Time Setup

If you want the dedicated Electron shell, run the following once:

```powershell
cd desktop
npm install
```

## Start The Desktop App

Recommended command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1
```

If you want the stronger Electron desktop executable, build the portable package with:

```powershell
cd desktop
npm run pack:portable
```

After that, the Electron executable will be available at:

`desktop/release-portable/win-portable/Algo Benchmark Platform Desktop.exe`

If Redis is already running, you can skip it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1 -SkipRedis
```

If you explicitly want desktop mode to keep using MySQL instead of the local SQLite file:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1 -UseMySQL
```

## What The Script Does

The script prepares:

- Redis when needed
- frontend desktop build output under `web/dist-desktop`
- local desktop database file at `backend/data/desktop/abp-desktop.db` by default

After that, it opens one of these desktop shells:

- Electron when `desktop/node_modules/electron/dist/electron.exe` exists
- Microsoft Edge app mode as the zero-install fallback

Electron then starts:

- Backend API on `127.0.0.1:8001`
- Celery worker process managed by the desktop app
- SQLite-backed local desktop data by default

The desktop UI itself is loaded from the local file build:

`web/dist-desktop/index.html`

## Stronger Desktop Build

The repository now also supports a stronger portable Electron build:

- build command: `desktop/npm run pack:portable`
- output directory: `desktop/release-portable/win-portable/`
- executable: `Algo Benchmark Platform Desktop.exe`

This portable Electron build is closer to a true desktop application than the browser-based fallback window.

## Current Scope

This is a much stronger desktop option for the current project stage. It is suitable for demos and local usage, but it still depends on the local runtime environment:

- Python virtual environment
- Node.js
- Redis

MySQL is optional in desktop mode and no longer required by default.

If you later want a true distributable installer, the next step would be:

- package Electron into an installer
- bundle or pre-check Python runtime dependencies
- rethink local packaging for Redis and worker dependencies
