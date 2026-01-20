// web/src/api/http.js
// 极简 HTTP 封装：只处理 JSON 请求/响应 + 统一错误。
// 目的：让 Pinia store / 视图层不关心 fetch 细节，专注业务状态。

const API_BASE = "http://127.0.0.1:8000"; // 后端端口固定 8000（严格不改）

/**
 * @param {string} path 例如 "/runs"
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

  // FastAPI 默认：非 2xx 会带 detail。这里统一抛一个可读错误。
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
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
    throw err;
  }

  // /health 之类始终 JSON；为了稳妥，如果没 body 就返回 null
  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}
