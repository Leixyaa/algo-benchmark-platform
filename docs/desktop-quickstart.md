# Desktop Quickstart

## What This Adds

This repository now includes a minimal Electron desktop shell:

- `desktop/` hosts the Electron app
- `scripts/manual_up_desktop.ps1` starts your existing services and then opens the desktop window

The desktop app does not rewrite your platform. It simply wraps the existing Vue frontend in a native window and keeps the current FastAPI, Celery, Redis, and MySQL workflow unchanged.

## First-Time Setup

Run the following once:

```powershell
cd desktop
npm install
```

## Start The Desktop App

Recommended command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1
```

If Redis or MySQL is already running, you can skip them:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1 -SkipRedis -SkipMySQL
```

## What The Script Does

The script reuses `scripts/manual_up.ps1` to start:

- Backend API
- Celery worker
- Web frontend
- Redis and MySQL when needed

After that, it opens an Electron desktop window that points to:

`http://127.0.0.1:5173`

## Current Scope

This is the simplest practical desktop option for the current project stage. It is ideal for demos and local usage, but it still depends on your development environment:

- Python virtual environment
- Node.js
- Redis
- MySQL

If you later want a true distributable installer, the next step would be:

- build the frontend into static assets
- serve those assets from the backend
- rethink local packaging for Redis, workers, and database dependencies
