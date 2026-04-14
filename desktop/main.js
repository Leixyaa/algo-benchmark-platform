const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const API_URL = process.env.ABP_DESKTOP_API_URL || "http://127.0.0.1:8001/docs";
const STARTUP_TIMEOUT_MS = 120000;
const RETRY_INTERVAL_MS = 1500;
const PRODUCT_NAME = "Algo Benchmark Platform Desktop";

function detectRepoRoot() {
  const candidates = [
    process.env.ABP_DESKTOP_REPO_ROOT,
    path.resolve(__dirname, ".."),
    path.resolve(process.execPath, "..", "..", ".."),
    path.resolve(process.execPath, "..", "..", "..", ".."),
  ].filter(Boolean);

  for (const candidate of candidates) {
    const backendCandidate = path.join(candidate, "backend");
    const webCandidate = path.join(candidate, "web");
    if (fs.existsSync(backendCandidate) && fs.existsSync(webCandidate)) {
      return candidate;
    }
  }

  return path.resolve(__dirname, "..");
}

const REPO_ROOT = detectRepoRoot();
const GUIDE_PATH = path.join(REPO_ROOT, "docs", "desktop-quickstart.md");
const FRONTEND_INDEX = path.join(REPO_ROOT, "web", "dist-desktop", "index.html");
const BACKEND_DIR = path.join(REPO_ROOT, "backend");
const PYTHON_EXE = path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");
const LOG_DIR = path.join(REPO_ROOT, "logs", "desktop");
const DESKTOP_DATA_DIR = path.join(BACKEND_DIR, "data", "desktop");
const SQLITE_DB_PATH = path.join(DESKTOP_DATA_DIR, "abp-desktop.db");
const WORKER_COUNT = Math.max(1, Number.parseInt(process.env.ABP_DESKTOP_WORKER_COUNT || "1", 10) || 1);
const DB_MODE = (process.env.ABP_DESKTOP_DB_MODE || "sqlite").toLowerCase();
const MYSQL_PORT = process.env.ABP_DESKTOP_MYSQL_PORT || "3306";
const MYSQL_DATABASE = process.env.ABP_DESKTOP_MYSQL_DATABASE || "algo_benchmark";
const MYSQL_ROOT_PASSWORD = process.env.ABP_MYSQL_ROOT_PASSWORD || "abp_mysql_123456";
const managedProcesses = [];

let mainWindow;

function ensureLogDir() {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

function ensureDesktopDataDir() {
  fs.mkdirSync(DESKTOP_DATA_DIR, { recursive: true });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 760,
    autoHideMenuBar: true,
    backgroundColor: "#f4f6fb",
    title: PRODUCT_NAME,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "splash.html"));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForUrl(url, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url, { method: "GET" });
      if (response.ok) {
        return true;
      }
    } catch (error) {
      // The local service may still be starting up.
    }
    await sleep(RETRY_INTERVAL_MS);
  }
  return false;
}

function buildBackendEnv() {
  ensureDesktopDataDir();
  const databaseUrl =
    DB_MODE === "mysql"
      ? `mysql+pymysql://root:${encodeURIComponent(MYSQL_ROOT_PASSWORD)}@127.0.0.1:${MYSQL_PORT}/${MYSQL_DATABASE}?charset=utf8mb4`
      : `sqlite:///${SQLITE_DB_PATH.replace(/\\/g, "/")}`;
  return {
    ...process.env,
    ABP_SQL_STORE_URL: process.env.ABP_SQL_STORE_URL || databaseUrl,
    ABP_SQL_FALLBACK_REDIS: process.env.ABP_SQL_FALLBACK_REDIS || "1",
  };
}

function spawnManagedProcess(name, command, args, cwd, env) {
  ensureLogDir();
  const stdoutPath = path.join(LOG_DIR, `${name}.out.log`);
  const stderrPath = path.join(LOG_DIR, `${name}.err.log`);
  const stdoutFd = fs.openSync(stdoutPath, "a");
  const stderrFd = fs.openSync(stderrPath, "a");
  const child = spawn(command, args, {
    cwd,
    env,
    detached: false,
    stdio: ["ignore", stdoutFd, stderrFd],
    windowsHide: true,
  });
  managedProcesses.push({ name, child });
  return child;
}

async function ensureLocalServices() {
  if (!fs.existsSync(PYTHON_EXE)) {
    throw new Error(`Python venv not found: ${PYTHON_EXE}`);
  }

  const apiReady = await waitForUrl(API_URL, 2500);
  if (apiReady) {
    return;
  }

  const env = buildBackendEnv();
  spawnManagedProcess(
    "backend-api",
    PYTHON_EXE,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    BACKEND_DIR,
    env
  );

  for (let i = 0; i < WORKER_COUNT; i += 1) {
    spawnManagedProcess(
      `worker-${i + 1}`,
      PYTHON_EXE,
      ["-m", "celery", "-A", "app.celery_app:celery_app", "worker", "-P", "solo", "-l", "info", "-n", `desktop_worker_${i + 1}`],
      BACKEND_DIR,
      env
    );
  }

  const ready = await waitForUrl(API_URL, STARTUP_TIMEOUT_MS);
  if (!ready) {
    throw new Error("Backend API did not become ready on http://127.0.0.1:8001.");
  }
}

function stopManagedProcesses() {
  for (const proc of managedProcesses) {
    if (!proc.child || proc.child.killed || proc.child.exitCode !== null) {
      continue;
    }
    try {
      spawnSync("taskkill", ["/PID", String(proc.child.pid), "/T", "/F"], {
        windowsHide: true,
        stdio: "ignore",
      });
    } catch (error) {
      // Ignore cleanup failures on exit.
    }
  }
}

async function boot() {
  if (!fs.existsSync(FRONTEND_INDEX)) {
    throw new Error(`Desktop frontend build not found: ${FRONTEND_INDEX}`);
  }

  await ensureLocalServices();
  await mainWindow.loadFile(FRONTEND_INDEX);
}

async function showBootError(error) {
  const { response } = await dialog.showMessageBox(mainWindow, {
    type: "warning",
    buttons: ["Open guide", "Retry", "Exit"],
    defaultId: 1,
    cancelId: 2,
    title: "Desktop app startup failed",
    message: error.message || "Desktop app could not start correctly.",
    detail:
      "Use scripts/manual_up_desktop.ps1 to prepare desktop dependencies, then retry.",
  });

  if (response === 0) {
    await shell.openPath(GUIDE_PATH);
    app.quit();
    return;
  }

  if (response === 1) {
    await bootSequence();
    return;
  }

  app.quit();
}

async function bootSequence() {
  try {
    await boot();
  } catch (error) {
    await showBootError(error);
  }
}

app.whenReady().then(async () => {
  createWindow();
  await bootSequence();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      void bootSequence();
    }
  });
});

app.on("before-quit", () => {
  stopManagedProcesses();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
