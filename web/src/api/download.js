import { authFetch } from "./http";

function parseFilename(contentDisposition, fallbackName) {
  const text = String(contentDisposition || "");
  const utf8Match = text.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const plainMatch = text.match(/filename=\"?([^\";]+)\"?/i);
  if (plainMatch?.[1]) return plainMatch[1];
  return fallbackName;
}

function browserDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function readResponseBlob(res, onProgress) {
  const total = Number(res.headers.get("content-length") || 0);
  if (!res.body?.getReader) {
    const blob = await res.blob();
    if (typeof onProgress === "function") {
      onProgress({ loaded: blob.size, total: total || blob.size, percent: 100 });
    }
    return blob;
  }

  const reader = res.body.getReader();
  const chunks = [];
  let loaded = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;
    chunks.push(value);
    loaded += value.byteLength;
    if (typeof onProgress === "function") {
      onProgress({
        loaded,
        total,
        percent: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : null,
      });
    }
  }

  if (typeof onProgress === "function") {
    onProgress({ loaded, total: total || loaded, percent: 100 });
  }
  return new Blob(chunks);
}

export async function downloadBinaryFile(path, fallbackName, options = {}) {
  const { onProgress } = options || {};
  const res = await authFetch(path, { method: "GET" });
  if (!res.ok) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      detail = "";
    }
    throw new Error(`[${res.status}] GET ${path}${detail ? ` - ${detail}` : ""}`);
  }
  const filename = parseFilename(res.headers.get("content-disposition"), fallbackName);
  const blobFallback = res.clone();
  let blob;
  try {
    blob = await readResponseBlob(res, onProgress);
  } catch {
    blob = await blobFallback.blob();
    if (typeof onProgress === "function") {
      onProgress({ loaded: blob.size, total: blob.size, percent: 100 });
    }
  }
  browserDownload(blob, filename);
  return { filename, savedWithPicker: false };
}
