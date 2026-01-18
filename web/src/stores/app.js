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

function loadState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
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
  return statusCN === "已完成" || statusCN === "失败";
}

// runId -> timerId
const _pollTimers = new Map();

// ====================== Store ======================

export const useAppStore = defineStore("app", {
  state: () => ({
    // 你后面会把 dataset/algorithm 做成真正的管理功能；目前保留 Demo 数据以便流程可跑。
    datasets: (loadState()?.datasets?.length ? loadState().datasets : [
      { id: "ds_demo", name: "Demo-样例数据集", type: "图像", size: "10 张", createdAt: nowStr() },
    ]),

    algorithms: (loadState()?.algorithms?.length ? loadState().algorithms : [
      { id: "alg_dn_cnn", task: "去噪", name: "DnCNN(示例)", impl: "PyTorch", version: "v1", createdAt: nowStr() },
      { id: "alg_dehaze_dcp", task: "去雾", name: "DCP暗通道先验(真实)", impl: "OpenCV", version: "v1", createdAt: nowStr() },
    ]),

    

    // 兼容保留：有些页面可能还在引用 tasks；阶段C 先不动它
    tasks: [],

    // 核心：runs 由后端 Redis/Celery 驱动
    runs: loadState()?.runs || [],
  }),

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
