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

export async function downloadBinaryFile(path, fallbackName) {
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
  const blob = await res.blob();
  browserDownload(blob, filename);
  return { filename, savedWithPicker: false };
}
