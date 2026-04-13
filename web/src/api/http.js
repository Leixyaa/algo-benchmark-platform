// web/src/api/http.js
// 通用 HTTP 请求封装：自动拼 query，JSON 请求与错误透传

export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001";
const IS_DESKTOP = import.meta.env.VITE_DESKTOP === "1";

function getAuthValue(key) {
  return sessionStorage.getItem(key) || localStorage.getItem(key) || "";
}

function clearAuthStorage() {
  sessionStorage.removeItem("token");
  sessionStorage.removeItem("username");
  sessionStorage.removeItem("userRole");
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  localStorage.removeItem("userRole");
}

/**
 * @param {string} path 例如 "/runs"
 * @param {{method?: string, query?: Record<string, any>, body?: any}} opts
 */
export async function request(path, { method = "GET", query, body } = {}) {
  const res = await authFetch(path, {
    method,
    query,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
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

function buildUrl(path, query) {
  const url = new URL(API_BASE + path);
  if (query && typeof query === "object") {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url;
}

function handleUnauthorized(res) {
  if (res.status !== 401) return;
  const hadToken = !!getAuthValue("token");
  clearAuthStorage();
  if (!hadToken) {
    return;
  }
  if (IS_DESKTOP) {
    if (!window.location.hash.startsWith("#/login")) {
      window.location.hash = "#/login";
    }
    return;
  }
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

export async function authFetch(path, { method = "GET", query, headers = {}, body } = {}) {
  const url = buildUrl(path, query);
  const mergedHeaders = { ...headers };
  const token = getAuthValue("token");
  if (token) {
    mergedHeaders.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(url.toString(), {
    method,
    headers: mergedHeaders,
    body,
  });
  handleUnauthorized(res);
  return res;
}

// 导出便捷方法
export default {
  get: (path, query) => request(path, { method: "GET", query }),
  post: (path, body) => request(path, { method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};
