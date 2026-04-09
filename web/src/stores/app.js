// web/src/stores/app.js
// Pinia 全局 store（前端对接后端）
// - NewRun：POST /runs 创建 run
// - Runs：轮询 GET /runs/{id}
// - Compare：展示后端 metrics（PSNR/SSIM/NIQE）

import { defineStore } from "pinia";
import { runsApi } from "../api/runs";
import { datasetsApi } from "../api/datasets";
import { algorithmsApi } from "../api/algorithms";
import { presetsApi } from "../api/presets";
import http from "../api/http";

const LS_KEY = "abp_state_v1";
const LEGACY_LS_KEY = LS_KEY;
const GUEST_SCOPE = "__guest__";

function currentAuthUsername() {
  return sessionStorage.getItem("username") || localStorage.getItem("username") || "";
}

function currentAuthToken() {
  return sessionStorage.getItem("token") || localStorage.getItem("token") || "";
}

function currentAuthRole() {
  return sessionStorage.getItem("userRole") || localStorage.getItem("userRole") || "user";
}

function setAuthSession({ username = "", token = "", role = "user" } = {}) {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  localStorage.removeItem("userRole");
  if (token) sessionStorage.setItem("token", token);
  else sessionStorage.removeItem("token");
  if (username) sessionStorage.setItem("username", username);
  else sessionStorage.removeItem("username");
  if (role) sessionStorage.setItem("userRole", role);
  else sessionStorage.removeItem("userRole");
}

function clearAuthSession() {
  sessionStorage.removeItem("token");
  sessionStorage.removeItem("username");
  sessionStorage.removeItem("userRole");
}

function _scopeName(username) {
  return String(username || "").trim() || GUEST_SCOPE;
}

function _scopedKey(username) {
  return `${LS_KEY}:${_scopeName(username)}`;
}

// ====================== 任务类型统一映射（唯一真相） ======================
export const TASK_LABEL_BY_TYPE = {
  denoise: "去噪",
  deblur: "去模糊",
  dehaze: "去雾",
  sr: "超分辨率",
  lowlight: "低照度增强",
  video_denoise: "视频去噪",
  video_sr: "视频超分",
};

export const TASK_TYPE_BY_LABEL = Object.fromEntries(
  Object.entries(TASK_LABEL_BY_TYPE).map(([k, v]) => [v, k])
);

export function toTaskLabel(taskType) {
  return TASK_LABEL_BY_TYPE[taskType] || taskType || "";
}

export function toTaskType(taskLabel) {
  return TASK_TYPE_BY_LABEL[taskLabel] || taskLabel || "";
}

function hasBadText(v) {
  if (typeof v !== "string") return false;
  if (v.includes("\uFFFD")) return true;
  if (/[?？]{2,}/.test(v)) return true;
  return false;
}

function normalizeBadString(v, fallback) {
  if (typeof v !== "string") return v;
  if (hasBadText(v)) return fallback;
  return v;
}

function normalizeTaskLabel(v) {
  if (typeof v !== "string") return v;
  const normalized = TASK_LABEL_BY_TYPE[v] || v;
  if (Object.prototype.hasOwnProperty.call(TASK_TYPE_BY_LABEL, normalized)) return normalized;
  if (hasBadText(normalized)) return "待确认";
  return normalized;
}

function repairLoadedState(state) {
  if (!state || typeof state !== "object") return { state, changed: false };

  let changed = false;
  const next = { ...state };

  if (Array.isArray(next.datasets)) {
    next.datasets = next.datasets.map((d) => {
      if (!d || typeof d !== "object") return d;
      const name2 = normalizeBadString(d.name, "（名称乱码，请编辑）");
      const type2 = normalizeBadString(d.type, "（类型乱码，请编辑）");
      const size2 = normalizeBadString(d.size, "（大小乱码，请编辑）");
      if (name2 === d.name && type2 === d.type && size2 === d.size) return d;
      changed = true;
      return { ...d, name: name2, type: type2, size: size2 };
    });
  }

  if (Array.isArray(next.algorithms)) {
    next.algorithms = next.algorithms.map((a) => {
      if (!a || typeof a !== "object") return a;
      const name = typeof a.name === "string" ? a.name : "";
      const isDncnn = a.id === "alg_dn_cnn" || name.toLowerCase().includes("dncnn");
      const isDcp = a.id === "alg_dehaze_dcp" || name.toLowerCase().includes("dcp");

      if (isDncnn) {
        const needsFix = hasBadText(a.task) || hasBadText(a.name);
        if (!needsFix) return a;
        changed = true;
        return { ...a, task: "去噪", name: "DnCNN(示例)" };
      }
      if (isDcp) {
        const needsFix = hasBadText(a.task) || hasBadText(a.name);
        if (!needsFix) return a;
        changed = true;
        return { ...a, task: "去雾", name: "DCP暗通道先验(真实)" };
      }

      const task2 = normalizeTaskLabel(a.task);
      const name2 = normalizeBadString(a.name, "（算法名乱码，请编辑）");
      const impl2 = normalizeBadString(a.impl, "（实现方式乱码）");
      const ver2 = normalizeBadString(a.version, "（版本乱码）");
      if (task2 === a.task && name2 === a.name && impl2 === a.impl && ver2 === a.version) return a;
      changed = true;
      return { ...a, task: task2, name: name2, impl: impl2, version: ver2 };
    });
  }

  if (Array.isArray(next.runs)) {
    next.runs = next.runs.map((r) => {
      if (!r || typeof r !== "object") return r;
      const raw = r.raw;
      if (!raw || typeof raw !== "object") return r;
      const params = raw.params;
      if (!params || typeof params !== "object") return r;
      if (!Object.prototype.hasOwnProperty.call(params, "niqe_fallback")) return r;
      const raw2 = { ...raw, params: { ...params } };
      delete raw2.params.niqe_fallback;
      changed = true;
      return { ...r, raw: raw2 };
    });
  }

  return { state: next, changed };
}

function loadState(username) {
  try {
    const key = _scopedKey(username ?? currentAuthUsername());
    let raw = localStorage.getItem(key);
    if (!raw && _scopeName(username ?? currentAuthUsername()) === GUEST_SCOPE) {
      raw = localStorage.getItem(LEGACY_LS_KEY);
    }
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const repaired = repairLoadedState(parsed);
    if (repaired.changed) {
      localStorage.setItem(key, JSON.stringify({ ...repaired.state, _savedAt: Date.now() }));
    }
    return repaired.state;
  } catch {
    return null;
  }
}

function saveState(partial, username) {
  try {
    const key = _scopedKey(username ?? currentAuthUsername());
    const prev = loadState(username) || {};
    const next = { ...prev, ...partial, _savedAt: Date.now() };
    localStorage.setItem(key, JSON.stringify(next));
  } catch {
    // ignore
  }
}


// ====================== 状态/映射工具 ======================

function normalizeStatusCN(status) {
  const s = String(status ?? "").toLowerCase();
  if (["done", "completed", "success", "已完成"].includes(s)) return "已完成";
  if (["running", "运行中"].includes(s)) return "运行中";
  if (["queued", "pending", "排队中"].includes(s)) return "排队中";
  if (["failed", "error", "失败"].includes(s)) return "失败";
  if (["canceling", "cancelling", "取消中"].includes(s)) return "取消中";
  if (["canceled", "cancelled", "已取消"].includes(s)) return "已取消";
  return String(status ?? "");
}

function formatTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(unixSeconds * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function nowStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function ensureBaselineAlgorithms(algs) {
  const list = Array.isArray(algs) ? algs.slice() : [];
  return list;
  const byId = new Set(list.map((a) => a?.id).filter(Boolean));
  const add = (x) => {
    if (!x?.id) return;
    if (byId.has(x.id)) return;
    byId.add(x.id);
    list.push(x);
  };

  const createdAt = nowStr();

  add({
    id: "alg_dn_cnn",
    task: "去噪",
    name: "FastNLMeans(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { nlm_h: 10, nlm_hColor: 10, nlm_templateWindowSize: 7, nlm_searchWindowSize: 21 },
  });
  add({
    id: "alg_denoise_bilateral",
    task: "去噪",
    name: "Bilateral(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { bilateral_d: 7, bilateral_sigmaColor: 35, bilateral_sigmaSpace: 35 },
  });
  add({
    id: "alg_denoise_gaussian",
    task: "去噪",
    name: "Gaussian(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { gaussian_sigma: 1.0 },
  });
  add({
    id: "alg_denoise_median",
    task: "去噪",
    name: "Median(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { median_ksize: 3 },
  });

  add({
    id: "alg_dehaze_dcp",
    task: "去雾",
    name: "DCP暗通道先验(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { dcp_patch: 15, dcp_omega: 0.95, dcp_t0: 0.1 },
  });
  add({
    id: "alg_dehaze_clahe",
    task: "去雾",
    name: "CLAHE(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { clahe_clip_limit: 2.0 },
  });
  add({
    id: "alg_dehaze_gamma",
    task: "去雾",
    name: "Gamma(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { gamma: 0.75 },
  });

  add({
    id: "alg_deblur_unsharp",
    task: "去模糊",
    name: "UnsharpMask(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { unsharp_sigma: 1.0, unsharp_amount: 1.6 },
  });
  add({
    id: "alg_deblur_laplacian",
    task: "去模糊",
    name: "LaplacianSharpen(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { laplacian_strength: 0.7 },
  });

  add({ id: "alg_sr_bicubic", task: "超分辨率", name: "Bicubic(基线)", impl: "OpenCV", version: "v1", createdAt, defaultParams: {} });
  add({ id: "alg_sr_lanczos", task: "超分辨率", name: "Lanczos(基线)", impl: "OpenCV", version: "v1", createdAt, defaultParams: {} });
  add({ id: "alg_sr_nearest", task: "超分辨率", name: "Nearest(基线)", impl: "OpenCV", version: "v1", createdAt, defaultParams: {} });

  add({
    id: "alg_lowlight_gamma",
    task: "低照度增强",
    name: "Gamma(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { lowlight_gamma: 0.6 },
  });
  add({
    id: "alg_lowlight_clahe",
    task: "低照度增强",
    name: "CLAHE(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { clahe_clip_limit: 2.5 },
  });
  add({
    id: "alg_video_denoise_gaussian",
    task: "视频去噪",
    name: "VideoGaussian(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { gaussian_sigma: 1.0 },
  });
  add({
    id: "alg_video_denoise_median",
    task: "视频去噪",
    name: "VideoMedian(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: { median_ksize: 3 },
  });
  add({
    id: "alg_video_sr_bicubic",
    task: "视频超分",
    name: "VideoBicubic(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: {},
  });
  add({
    id: "alg_video_sr_lanczos",
    task: "视频超分",
    name: "VideoLanczos(基线)",
    impl: "OpenCV",
    version: "v1",
    createdAt,
    defaultParams: {},
  });

  return list;
}

function mapDatasetOut(x) {
  return {
    id: x.dataset_id,
    name: x.name,
    type: x.type,
    size: x.size,
    description: x.description || "",
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    allowUse: Boolean(x.allow_use),
    allowDownload: Boolean(x.allow_download),
    createdAt: formatTs(x.created_at),
    uploaderId: String(x.owner_id || ""),
    sourceUploaderId: String(x.source_owner_id || x?.meta?.downloaded_from_owner_id || ""),
    sourceDatasetId: String(x.source_dataset_id || x?.meta?.downloaded_from_dataset_id || ""),
    raw: x,
  };
}

function mapAlgorithmOut(x) {
  return {
    id: x.algorithm_id,
    task: normalizeTaskLabel(x.task),
    name: x.name,
    impl: x.impl,
    version: x.version,
    description: x.description || "",
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    allowUse: Boolean(x.allow_use),
    allowDownload: Boolean(x.allow_download),
    createdAt: formatTs(x.created_at),
    defaultParams: x.default_params ?? {},
    paramPresets: x.param_presets ?? {},
    uploaderId: String(x.owner_id || ""),
    sourceUploaderId: String(x.source_owner_id || ""),
    sourceAlgorithmId: String(x.source_algorithm_id || ""),
    raw: x,
  };
}

function isTerminal(statusCN) {
  return statusCN === "已完成" || statusCN === "失败" || statusCN === "已取消";
}

// runId -> timerId
const _pollTimers = new Map();

// ====================== Store ======================

export const useAppStore = defineStore("app", {
  state: () => {
    const loaded = loadState(currentAuthUsername());
      return {
        // 用户状态
        user: {
          username: currentAuthUsername(),
          token: currentAuthToken(),
          role: currentAuthRole(),
          isLoggedIn: !!currentAuthToken(),
        },
        notices: [],
        // 数据资产
        datasets: (loaded?.datasets?.length ? loaded.datasets : []),
        algorithms: ensureBaselineAlgorithms(loaded?.algorithms?.length ? loaded.algorithms : []),
      presets: loaded?.presets || [],
      runs: loaded?.runs || [],
      // 全局控制
      loading: false,
    };
  },

  actions: {
    // --- 用户 Actions ---
    async login(username, password) {
      try {
        const res = await http.post("/login", { username, password });
        this.stopPollingAll();
        this.datasets = [];
        this.algorithms = [];
        this.presets = [];
        this.runs = [];
        this.user.username = res.username;
        this.user.token = res.access_token;
        this.user.role = res.role || "user";
        this.user.isLoggedIn = true;
        setAuthSession({ username: res.username, token: res.access_token, role: res.role || "user" });
        const loaded = loadState(res.username) || {};
        this.datasets = loaded?.datasets?.length ? loaded.datasets : [];
        this.algorithms = ensureBaselineAlgorithms(loaded?.algorithms?.length ? loaded.algorithms : []);
        this.presets = loaded?.presets || [];
        this.runs = loaded?.runs || [];
          await Promise.all([
            this.fetchDatasets(),
            this.fetchAlgorithms(),
          ]);
          await this.fetchUnreadNotices();
          return true;
        } catch (e) {
          throw e;
        }
      },
    async register(username, password) {
      try {
        await http.post("/register", { username, password });
        return true;
      } catch (e) {
        throw e;
      }
    },
    async loginAdmin(username, password) {
      try {
        const res = await http.post("/admin/login", { username, password });
        this.stopPollingAll();
        this.datasets = [];
        this.algorithms = [];
        this.presets = [];
        this.runs = [];
        this.user.username = res.username;
        this.user.token = res.access_token;
        this.user.role = res.role || "admin";
        this.user.isLoggedIn = true;
        setAuthSession({ username: res.username, token: res.access_token, role: res.role || "admin" });
        const loaded = loadState(res.username) || {};
        this.datasets = loaded?.datasets?.length ? loaded.datasets : [];
        this.algorithms = ensureBaselineAlgorithms(loaded?.algorithms?.length ? loaded.algorithms : []);
        this.presets = loaded?.presets || [];
        this.runs = loaded?.runs || [];
          await Promise.all([
            this.fetchDatasets(),
            this.fetchAlgorithms(),
          ]);
          await this.fetchUnreadNotices();
          return true;
        } catch (e) {
          throw e;
        }
      },
    logout() {
      this.stopPollingAll();
      this.user.username = "";
      this.user.token = "";
        this.user.role = "user";
        this.user.isLoggedIn = false;
        this.notices = [];
        clearAuthSession();
        const loaded = loadState(GUEST_SCOPE) || {};
        this.datasets = loaded?.datasets?.length ? loaded.datasets : [];
        this.algorithms = ensureBaselineAlgorithms(loaded?.algorithms?.length ? loaded.algorithms : []);
        this.presets = loaded?.presets || [];
        this.runs = loaded?.runs || [];
      },

      async fetchUnreadNotices() {
        if (!this.user.isLoggedIn) {
          this.notices = [];
          return [];
        }
        const items = await http.get("/me/notices", { unread_only: true });
        this.notices = Array.isArray(items) ? items : [];
        return this.notices;
      },

      async markNoticeRead(noticeId) {
        if (!noticeId) return;
        await http.post(`/me/notices/${noticeId}/read`);
        this.notices = (this.notices || []).filter((item) => String(item?.notice_id || "") !== String(noticeId));
      },

    // ====================== Catalog：数据集/算法（后端持久化） ======================
    async fetchDatasets(limit = 200) {
      const list = await datasetsApi.listDatasets({ limit });
      const currentUsername = String(this.user?.username || "");
      const mapped = (list ?? [])
        .filter((x) => {
          if (!currentUsername) return false;
          return String(x?.owner_id || "") === currentUsername;
        })
        .map((x) => mapDatasetOut(x));
      this.datasets = mapped;
      saveState({ datasets: this.datasets });
      return this.datasets;
    },

    async fetchAlgorithms(limit = 500) {
      const list = await algorithmsApi.listAlgorithms({ limit });
      const mapped = (list ?? []).map((x) => mapAlgorithmOut(x));
      this.algorithms = ensureBaselineAlgorithms(mapped);
      saveState({ algorithms: this.algorithms });
      return this.algorithms;
    },

    async fetchPresets(limit = 200) {
      const list = await presetsApi.listPresets({ limit });
      const mapped = (list ?? []).map((x) => ({
        id: x.preset_id,
        name: x.name,
        taskType: x.task_type,
        datasetId: x.dataset_id,
        algorithmId: x.algorithm_id,
        metrics: Array.isArray(x.metrics) ? x.metrics : [],
        params: x.params ?? {},
        createdAt: formatTs(x.created_at),
        updatedAt: formatTs(x.updated_at),
        raw: x,
      }));
      this.presets = mapped;
      saveState({ presets: this.presets });
      return this.presets;
    },

    async createDataset(payload) {
      const out = await datasetsApi.createDataset({
        name: payload?.name,
        type: payload?.type,
        size: payload?.size,
        description: payload?.description,
        visibility: payload?.visibility,
        allow_use: payload?.allowUse,
        allow_download: payload?.allowDownload,
      });
      const ds = mapDatasetOut(out);
      const idx = this.datasets.findIndex((d) => d.id === ds.id);
      if (idx === -1) this.datasets.unshift(ds);
      else this.datasets[idx] = { ...this.datasets[idx], ...ds };
      saveState({ datasets: this.datasets });
      return ds;
    },

    async updateDataset(id, patch) {
      const out = await datasetsApi.patchDataset(id, {
        name: patch?.name,
        type: patch?.type,
        size: patch?.size,
        description: patch?.description,
        visibility: patch?.visibility,
        allow_use: patch?.allowUse,
        allow_download: patch?.allowDownload,
      });
      const ds = mapDatasetOut(out);
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx >= 0) this.datasets[idx] = { ...this.datasets[idx], ...ds };
      saveState({ datasets: this.datasets });
      return ds;
    },

    async changeDatasetId(id, newDatasetId) {
      const out = await datasetsApi.changeDatasetId(id, newDatasetId);
      const ds = mapDatasetOut(out);
      this.datasets = (this.datasets || []).filter((d) => d.id !== id && d.id !== ds.id);
      this.datasets.unshift(ds);
      saveState({ datasets: this.datasets });
      return ds;
    },

    async removeDataset(id, options) {
      await datasetsApi.deleteDataset(id, options);
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx >= 0) this.datasets.splice(idx, 1);
      saveState({ datasets: this.datasets });
    },

    async scanDataset(id) {
      const out = await datasetsApi.scanDataset(id);
      const ds = mapDatasetOut(out);
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx >= 0) this.datasets[idx] = { ...this.datasets[idx], ...ds };
      saveState({ datasets: this.datasets });
      return ds;
    },

    async importDatasetZip(id, { filename, dataB64, overwrite = false }) {
      const out = await datasetsApi.importZip(id, {
        filename,
        data_b64: dataB64,
        overwrite: Boolean(overwrite),
      });
      const ds = mapDatasetOut(out);
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx === -1) this.datasets.unshift(ds);
      else this.datasets[idx] = { ...this.datasets[idx], ...ds };
      saveState({ datasets: this.datasets });
      return ds;
    },

    async createAlgorithm(payload) {
      const out = await algorithmsApi.createAlgorithm({
        task: payload?.task,
        name: payload?.name,
        impl: payload?.impl,
        version: payload?.version,
        description: payload?.description,
        default_params: payload?.defaultParams ?? {},
        visibility: payload?.visibility,
        allow_use: payload?.allowUse,
        allow_download: payload?.allowDownload,
      });
      const alg = mapAlgorithmOut(out);
      const idx = this.algorithms.findIndex((a) => a.id === alg.id);
      if (idx === -1) this.algorithms.unshift(alg);
      else this.algorithms[idx] = { ...this.algorithms[idx], ...alg };
      this.algorithms = ensureBaselineAlgorithms(this.algorithms);
      saveState({ algorithms: this.algorithms });
      return alg;
    },

    async createPreset(payload) {
      const out = await presetsApi.createPreset({
        preset_id: payload?.id,
        name: payload?.name,
        task_type: payload?.taskType || toTaskType(payload?.task),
        dataset_id: payload?.datasetId,
        algorithm_id: payload?.algorithmId,
        metrics: Array.isArray(payload?.metrics) ? payload.metrics : [],
        params: payload?.params ?? {},
      });
      const p = {
        id: out.preset_id,
        name: out.name,
        taskType: out.task_type,
        datasetId: out.dataset_id,
        algorithmId: out.algorithm_id,
        metrics: Array.isArray(out.metrics) ? out.metrics : [],
        params: out.params ?? {},
        createdAt: formatTs(out.created_at),
        updatedAt: formatTs(out.updated_at),
        raw: out,
      };
      const idx = this.presets.findIndex((x) => x.id === p.id);
      if (idx === -1) this.presets.unshift(p);
      else this.presets[idx] = { ...this.presets[idx], ...p };
      saveState({ presets: this.presets });
      return p;
    },

    async removePreset(id) {
      await presetsApi.deletePreset(id);
      const idx = this.presets.findIndex((x) => x.id === id);
      if (idx >= 0) this.presets.splice(idx, 1);
      saveState({ presets: this.presets });
    },

    async updateAlgorithm(id, patch) {
      const out = await algorithmsApi.patchAlgorithm(id, {
        task: patch?.task,
        name: patch?.name,
        impl: patch?.impl,
        version: patch?.version,
        description: patch?.description,
        default_params: patch?.defaultParams,
        param_presets: patch?.paramPresets,
        visibility: patch?.visibility,
        allow_use: patch?.allowUse,
        allow_download: patch?.allowDownload,
      });
      const alg = mapAlgorithmOut(out);
      const idx = this.algorithms.findIndex((a) => a.id === id);
      if (idx >= 0) this.algorithms[idx] = { ...this.algorithms[idx], ...alg };
      this.algorithms = ensureBaselineAlgorithms(this.algorithms);
      saveState({ algorithms: this.algorithms });
      return alg;
    },

    async removeAlgorithm(id) {
      await algorithmsApi.deleteAlgorithm(id);
      const idx = this.algorithms.findIndex((a) => a.id === id);
      if (idx >= 0) this.algorithms.splice(idx, 1);
      this.algorithms = ensureBaselineAlgorithms(this.algorithms);
      saveState({ algorithms: this.algorithms });
    },

    async resetUserAlgorithms() {
      await algorithmsApi.resetUserAlgorithms();
      await this.fetchAlgorithms();
      saveState({ algorithms: this.algorithms });
      return this.algorithms;
    },


    // ====================== 阶段C：后端对接（创建/拉取/轮询） ======================

    /**
     * 创建真实 Run（后端写 Redis + 投递 Celery）
     * @param {{task:string,datasetId:string,algorithmId:string,metrics?:string[],params?:object}} payload
     * @returns {Promise<string>} runId
     */
    async createRun(payload) {
      const task_type = toTaskType(payload.task);
      const userParams =
        payload?.params && typeof payload.params === "object" && !Array.isArray(payload.params)
          ? payload.params
          : {};
      const params = { ...userParams, metrics: payload.metrics ?? [] };
      const strict_validate = Boolean(payload?.strictValidate);

      const out = await runsApi.createRun({
        task_type,
        dataset_id: payload.datasetId,
        algorithm_id: payload.algorithmId,
        params,
        strict_validate,
      });

      const run = this._mapRunOut(out);
      this._upsertRun(run);

      // 创建后立即轮询直到 done/failed
      this.startPolling(run.id);

      return run.id;
    },

    /**
     * 拉取 Run 列表（刷新页面不丢失）
     * @param {number} limit
     */
    async fetchRuns(limit = 200) {
      if (!this.user.isLoggedIn) {
        // 未登录用户清空任务列表
        this.runs = [];
        saveState({ runs: this.runs });
        return;
      }
      try {
        const list = await runsApi.listRuns({ limit });
        const mapped = (list ?? []).map((x) => this._mapRunOut(x));

        // 覆盖式同步：以 Redis 为准
        this.runs = mapped;
        saveState({ runs: this.runs });
        // 对未结束的 run 自动补轮询
        for (const r of this.runs) {
          if (!isTerminal(r.status)) this.startPolling(r.id);
        }
      } catch (error) {
        if (error?.response?.status === 401) {
          // 认证失败，清空任务列表
          this.runs = [];
          saveState({ runs: this.runs });
        }
        throw error;
      }
    },

    /**
     * 拉取单个 Run（轮询/详情用）
     * @param {string} runId
     */
    async fetchRun(runId) {
      const out = await runsApi.getRun(runId);
      const run = this._mapRunOut(out);
      this._upsertRun(run);
      return run;
    },

    async cancelRun(runId) {
      const prev = this.runs.find((r) => r.id === runId);
      if (prev && (prev.status === "已完成" || prev.status === "失败" || prev.status === "已取消")) return;

      this._upsertRun({ id: runId, status: "取消中" });
      try {
        const out = await runsApi.cancelRun(runId);
        if (out?.status) {
          const statusCN = normalizeStatusCN(out.status);
          this._upsertRun({ id: runId, status: statusCN });
          if (statusCN === "已取消") this.stopPolling(runId);
        }
      } catch (e) {
        this._upsertRun({ id: runId, status: prev?.status ?? "运行中" });
        throw e;
      }
    },

    async fastSelect(payload = {}) {
      const taskType =
        String(payload.task_type || "").trim() ||
        toTaskType(String(payload.task || "").trim());
      if (!taskType) {
        throw new Error("task_type_required");
      }
      const datasetId = String(payload.dataset_id || payload.datasetId || "").trim();
      const allowEmptyDatasetId = Boolean(payload.allow_empty_dataset_id ?? payload.allowEmptyDatasetId ?? false);
      if (!datasetId && !allowEmptyDatasetId) {
        throw new Error("dataset_id_required");
      }
      const out = await runsApi.fastSelect({
        task_type: taskType,
        dataset_id: datasetId || null,
        candidate_algorithm_ids: Array.isArray(payload.candidate_algorithm_ids)
          ? payload.candidate_algorithm_ids
          : (Array.isArray(payload.candidateAlgorithmIds) ? payload.candidateAlgorithmIds : []),
        top_k: Number(payload.top_k ?? payload.topK ?? 3),
        alpha: Number(payload.alpha ?? 0.35),
        lambda_reg: payload.lambda_reg ?? payload.lambdaReg,
        recency_half_life_hours: payload.recency_half_life_hours ?? payload.recencyHalfLifeHours,
        cold_start_bonus: payload.cold_start_bonus ?? payload.coldStartBonus,
        low_support_penalty: payload.low_support_penalty ?? payload.lowSupportPenalty,
        min_support: payload.min_support ?? payload.minSupport,
      });
      return out;
    },

    /**
     * 启动轮询（默认 800ms）
     * - run 进入终态（已完成/失败）会自动 stop
     * - 网络/后端短暂重启：不立即 stop，让下一轮继续尝试
     */
    startPolling(runId, intervalMs = 800) {
      if (_pollTimers.has(runId)) return;

      const timerId = setInterval(async () => {
        try {
          const run = await this.fetchRun(runId);
          if (isTerminal(run.status)) this.stopPolling(runId);
        } catch (e) {
          // ignore
        }
      }, intervalMs);

      _pollTimers.set(runId, timerId);
    },

    stopPolling(runId) {
      const t = _pollTimers.get(runId);
      if (t) clearInterval(t);
      _pollTimers.delete(runId);
    },

    stopPollingAll() {
      for (const [rid, t] of _pollTimers.entries()) {
        clearInterval(t);
        _pollTimers.delete(rid);
      }
    },

    // ====================== 内部：Run 映射 & upsert ======================

    _mapRunOut(out) {
      const statusCN = normalizeStatusCN(out?.status);
      const metrics = out?.metrics ?? {};

      const taskType = String(out?.task_type ?? "");
      const rawParams =
        out?.params && typeof out.params === "object" && !Array.isArray(out.params)
          ? { ...out.params }
          : out?.params;
      if (rawParams && typeof rawParams === "object" && !Array.isArray(rawParams)) {
        delete rawParams.niqe_fallback;
      }
      const raw = out ? { ...out, params: rawParams } : out;

      return {
        id: out.run_id,

        // ? 同时保留英文与中文，后续筛选/导出不再乱
        taskType,
        task: toTaskLabel(taskType),

        datasetId: out.dataset_id,
        algorithmId: out.algorithm_id,


        status: statusCN,
        createdAt: formatTs(out.created_at),

        // 表格直接用：扁平字段
        psnr: metrics.PSNR ?? metrics.psnr ?? null,
        ssim: metrics.SSIM ?? metrics.ssim ?? null,
        niqe: metrics.NIQE ?? metrics.niqe ?? null,
        elapsed: out.elapsed != null ? `${out.elapsed}s` : "-",

        error: out?.error ?? null,

        // 保留原始字段（未来导出/详情用）
        raw,
      };
    },

    _upsertRun(run) {
      const idx = this.runs.findIndex((r) => r.id === run.id);
      if (idx === -1) {
        this.runs.unshift(run);
        return;
      }
      this.runs[idx] = { ...this.runs[idx], ...run };
    },
  },
});
