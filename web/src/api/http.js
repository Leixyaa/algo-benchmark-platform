// web/src/api/http.js
// ???? HTTP ?????JSON ????/??????????

const API_BASE = "http://127.0.0.1:8000";

/**
 * @param {string} path ???? "/runs"
 * @param {{method?: string, query?: Record<string, any>, body?: any}} opts
 */
export async function request(path, { method = "GET", query, body } = {}) {
  const url = new URL(API_BASE + path);
  if (query && typeof query === "object") {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }

  const res = await fetch(url.toString(), {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let data = null;
    let detail = "";
    try {
      data = await res.json();
      detail = data?.detail ? JSON.stringify(data.detail) : JSON.stringify(data);
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = "";
      }
    }

    const msg = `[${res.status}] ${method} ${path}${detail ? ` - ${detail}` : ""}`;
    const err = new Error(msg);
    err.status = res.status;
    if (data && typeof data === "object") {
      err.data = data;
      err.detail = data.detail;
    }
    throw err;
  }

  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}
