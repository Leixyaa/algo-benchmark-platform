const { app, BrowserWindow, dialog, shell } = require("electron");
const path = require("path");

const WEB_URL = process.env.ABP_DESKTOP_URL || "http://127.0.0.1:5173";
const STARTUP_TIMEOUT_MS = 120000;
const RETRY_INTERVAL_MS = 1500;
const GUIDE_PATH = path.join(app.getAppPath(), "..", "docs", "desktop-quickstart.md");

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 760,
    autoHideMenuBar: true,
    backgroundColor: "#f4f6fb",
    title: "Algo Benchmark Platform Desktop",
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "splash.html"));
}

async function waitForWebReady(url, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url, { method: "GET" });
      if (response.ok) {
        return true;
      }
    } catch (error) {
      // The local web service may still be starting up.
    }
    await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL_MS));
  }
  return false;
}

async function boot() {
  const ready = await waitForWebReady(WEB_URL, STARTUP_TIMEOUT_MS);
  if (ready) {
    await mainWindow.loadURL(WEB_URL);
    return;
  }

  const { response } = await dialog.showMessageBox(mainWindow, {
    type: "warning",
    buttons: ["Open guide", "Retry", "Exit"],
    defaultId: 1,
    cancelId: 2,
    title: "Desktop app could not reach local services",
    message: "Web UI is not available yet.",
    detail:
      "Run scripts/manual_up_desktop.ps1 first, or start backend, worker, and web services before opening the desktop app.",
  });

  if (response === 0) {
    await shell.openPath(GUIDE_PATH);
    app.quit();
    return;
  }

  if (response === 1) {
    await boot();
    return;
  }

  app.quit();
}

app.whenReady().then(async () => {
  createWindow();
  await boot();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      void boot();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
