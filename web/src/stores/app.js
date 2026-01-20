// web/src/stores/app.js
// Pinia 全局 store（阶段C：前端对接后端最小闭环）
// - NewRun：POST /runs 创建真实 run
// - Runs：轮询 GET /runs/{id} 显示 queued/running/done（统一中文）
// - Compare：展示后端 metrics（PSNR/SSIM/NIQE）
//
// 说明：
// 1) 本阶段不做导出、不做真实算法，只把前后端 + Celery/Redis 的闭环跑通。
// 2) 轮询计时器不放进 Pinia state，避免热更新/序列化导致奇怪问题。

import { defineStore } from "pinia";
import { runsApi } from "../api/runs";

const LS_KEY = "abp_state_v1";

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
  if (/\?{3,}/.test(v)) return true;
  return false;
}

function normalizeBadString(v, fallback) {
  if (typeof v !== "string") return v;
  if (hasBadText(v)) return fallback;
  return v;
}

function repairLoadedState(state) {
  if (!state || typeof state !== "object") return { state, changed: false };

  let changed = false;
  const next = { ...state };

  if (Array.isArray(next.datasets)) {
    next.datasets = next.datasets.map((d) => {
      if (!d || typeof d !== "object") return d;
      const isDemo = d.id === "ds_demo" || (typeof d.name === "string" && d.name.startsWith("Demo-"));
      if (isDemo) {
        const needsFix = hasBadText(d.name) || hasBadText(d.type) || hasBadText(d.size);
        if (!needsFix) return d;
        changed = true;
        return { ...d, name: "Demo-样例数据集", type: "图像", size: "10 张" };
      }

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

      const task2 = normalizeBadString(a.task, "（任务乱码，请编辑）");
      const name2 = normalizeBadString(a.name, "（算法名乱码，请编辑）");
      const impl2 = normalizeBadString(a.impl, "（实现方式乱码）");
      const ver2 = normalizeBadString(a.version, "（版本乱码）");
      if (task2 === a.task && name2 === a.name && impl2 === a.impl && ver2 === a.version) return a;
      changed = true;
      return { ...a, task: task2, name: name2, impl: impl2, version: ver2 };
    });
  }

  return { state: next, changed };
}

function loadState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const repaired = repairLoadedState(parsed);
    if (repaired.changed) {
      localStorage.setItem(LS_KEY, JSON.stringify({ ...repaired.state, _savedAt: Date.now() }));
    }
    return repaired.state;
  } catch {
    return null;
  }
}

function saveState(partial) {
  try {
    const prev = loadState() || {};
    const next = { ...prev, ...partial, _savedAt: Date.now() };
    localStorage.setItem(LS_KEY, JSON.stringify(next));
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

function isTerminal(statusCN) {
  return statusCN === "已完成" || statusCN === "失败" || statusCN === "已取消";
}

// runId -> timerId
const _pollTimers = new Map();

// ====================== Store ======================

export const useAppStore = defineStore("app", {
  state: () => {
    const loaded = loadState();
    return ({
    // 你后面会把 dataset/algorithm 做成真正的管理功能；目前保留 Demo 数据以便流程可跑。
    datasets: (loaded?.datasets?.length ? loaded.datasets : [
      { id: "ds_demo", name: "Demo-样例数据集", type: "图像", size: "10 张", createdAt: nowStr() },
    ]),

    algorithms: (loaded?.algorithms?.length ? loaded.algorithms : [
      { id: "alg_dn_cnn", task: "去噪", name: "DnCNN(示例)", impl: "PyTorch", version: "v1", createdAt: nowStr() },
      { id: "alg_dehaze_dcp", task: "去雾", name: "DCP暗通道先验(真实)", impl: "OpenCV", version: "v1", createdAt: nowStr() },
    ]),

    

    // 兼容保留：有些页面可能还在引用 tasks；阶段C 先不动它
    tasks: [],

    // 核心：runs 由后端 Redis/Celery 驱动
    runs: loaded?.runs || [],
  });
  },

  actions: {
    // ====================== Demo 管理（保留） ======================
    addDataset(ds) {
      this.datasets.unshift({ ...ds, createdAt: nowStr() });
      saveState({ datasets: this.datasets });
    },

    addAlgorithm(alg) {
      this.algorithms.unshift({ ...alg, createdAt: nowStr() });
      saveState({ algorithms: this.algorithms });
    },

    removeDataset(id) {
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx >= 0) {
        this.datasets.splice(idx, 1);
        saveState({ datasets: this.datasets });
      }
    },

    removeAlgorithm(id) {
      const idx = this.algorithms.findIndex((a) => a.id === id);
      if (idx >= 0) {
        this.algorithms.splice(idx, 1);
        saveState({ algorithms: this.algorithms });
      }
    },

    updateDataset(id, patch) {
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx >= 0) {
        this.datasets[idx] = { ...this.datasets[idx], ...patch };
        saveState({ datasets: this.datasets });
      }
    },

    updateAlgorithm(id, patch) {
      const idx = this.algorithms.findIndex((a) => a.id === id);
      if (idx >= 0) {
        this.algorithms[idx] = { ...this.algorithms[idx], ...patch };
        saveState({ algorithms: this.algorithms });
      }
    },


    // ====================== 阶段C：后端对接（创建/拉取/轮询） ======================

    /**
     * 创建真实 Run（后端写 Redis + 投递 Celery）
     * @param {{task:string,datasetId:string,algorithmId:string,metrics?:string[]}} payload
     * @returns {Promise<string>} runId
     */
    async createRun(payload) {
      const task_type = toTaskType(payload.task);
      const params = { metrics: payload.metrics ?? [] };

      const out = await runsApi.createRun({
        task_type,
        dataset_id: payload.datasetId,
        algorithm_id: payload.algorithmId,
        params,
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
      const list = await runsApi.listRuns({ limit });
      const mapped = (list ?? []).map((x) => this._mapRunOut(x));

      // 覆盖式同步：以 Redis 为准
      this.runs = mapped;
      saveState({ runs: this.runs });
      // 对未结束的 run 自动补轮询
      for (const r of this.runs) {
        if (!isTerminal(r.status)) this.startPolling(r.id);
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
        raw: out,
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
