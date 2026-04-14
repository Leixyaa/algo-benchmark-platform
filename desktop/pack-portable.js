const fs = require("fs");
const path = require("path");
const asar = require("@electron/asar");

const productName = "Algo Benchmark Platform Desktop";
const rootDir = __dirname;
const runtimeDir = path.join(rootDir, "node_modules", "electron", "dist");
const outDir = path.join(rootDir, "release-portable", "win-portable");
const resourcesDir = path.join(outDir, "resources");
const appStageDir = path.join(rootDir, ".portable-app");
const appAsarPath = path.join(resourcesDir, "app.asar");

function resetDir(target) {
  fs.rmSync(target, { recursive: true, force: true });
  fs.mkdirSync(target, { recursive: true });
}

function copyRuntime() {
  for (const entry of fs.readdirSync(runtimeDir, { withFileTypes: true })) {
    const sourcePath = path.join(runtimeDir, entry.name);
    const targetName = entry.name.toLowerCase() === "electron.exe" ? `${productName}.exe` : entry.name;
    const targetPath = path.join(outDir, targetName);
    if (entry.isDirectory()) {
      fs.cpSync(sourcePath, targetPath, { recursive: true });
    } else {
      fs.copyFileSync(sourcePath, targetPath);
    }
  }
}

function stageAppFiles() {
  resetDir(appStageDir);
  for (const name of ["main.js", "splash.html", "package.json"]) {
    fs.copyFileSync(path.join(rootDir, name), path.join(appStageDir, name));
  }
}

async function createPortablePackage() {
  if (!fs.existsSync(path.join(runtimeDir, "electron.exe"))) {
    throw new Error(`Electron runtime is missing: ${path.join(runtimeDir, "electron.exe")}`);
  }

  resetDir(outDir);
  fs.mkdirSync(resourcesDir, { recursive: true });
  copyRuntime();
  stageAppFiles();
  await asar.createPackage(appStageDir, appAsarPath);
  fs.rmSync(appStageDir, { recursive: true, force: true });

  const readme = `# ${productName}\n\nThis is a portable Electron desktop build.\n\nStart:\n- Double-click "${productName}.exe"\n\nNotes:\n- It still reads the project backend/web resources from the repository root.\n- Build the latest desktop frontend before packaging.\n`;
  fs.writeFileSync(path.join(outDir, "README.txt"), readme, "utf8");
  console.log(`Portable Electron package created at ${outDir}`);
}

createPortablePackage().catch((error) => {
  console.error(error);
  process.exit(1);
});
