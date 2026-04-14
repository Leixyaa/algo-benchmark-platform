const fs = require("fs");
const path = require("path");

const productName = "Algo Benchmark Platform Desktop";
const runtimeDir = path.join(__dirname, "node_modules", "electron", "dist");
const relativeOutDir = process.argv[2] || path.join("release", "win-unpacked");
const unpackedDir = path.join(__dirname, relativeOutDir);
const sourceExe = path.join(runtimeDir, "electron.exe");
const targetExe = path.join(unpackedDir, `${productName}.exe`);

function ensureExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} not found: ${filePath}`);
  }
}

function copyMissingRuntimeFiles() {
  ensureExists(runtimeDir, "Electron runtime directory");
  ensureExists(unpackedDir, "win-unpacked directory");

  for (const entry of fs.readdirSync(runtimeDir, { withFileTypes: true })) {
    const sourcePath = path.join(runtimeDir, entry.name);
    const targetPath =
      entry.name.toLowerCase() === "electron.exe"
        ? targetExe
        : path.join(unpackedDir, entry.name);

    if (entry.isDirectory()) {
      if (!fs.existsSync(targetPath)) {
        fs.cpSync(sourcePath, targetPath, { recursive: true });
      }
      continue;
    }

    if (!fs.existsSync(targetPath)) {
      fs.copyFileSync(sourcePath, targetPath);
    }
  }
}

copyMissingRuntimeFiles();
console.log(`Patched Electron runtime into ${unpackedDir}`);
