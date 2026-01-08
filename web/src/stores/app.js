import { defineStore } from "pinia";

function normalizeStatus(status) {
  const s = String(status ?? "").toLowerCase();
  if (["done", "completed", "success", "已完成"].includes(s)) return "已完成";
  if (["running", "运行中"].includes(s)) return "运行中";
  if (["queued", "pending", "排队中"].includes(s)) return "排队中";
  if (["failed", "error", "失败"].includes(s)) return "失败";
  return String(status ?? "");
}


function nowStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export const useAppStore = defineStore("app", {
  state: () => ({
    datasets: [
      { id: "ds_demo", name: "Demo-样例数据集", type: "图像", size: "10 张", createdAt: nowStr() },
    ],
    algorithms: [
      { id: "alg_dn_cnn", task: "去噪", name: "DnCNN(示例)", impl: "PyTorch", version: "v1", createdAt: nowStr() },
    ],
    tasks: [],
    runs: [], 
  }),
  actions: {
    addDataset(ds) {
      this.datasets.unshift({ ...ds, createdAt: nowStr() });
    },
    addAlgorithm(alg) {
      this.algorithms.unshift({ ...alg, createdAt: nowStr() });
    },
    createTask(t) {
      const task = {
        id: `task_${Date.now()}`,
        status: "排队中",
        createdAt: nowStr(),
        ...t,
      };
      this.tasks.unshift(task);

      setTimeout(() => {
        task.status = "运行中";
      }, 600);

      setTimeout(() => {
        task.status = "已完成";
        task.elapsed = "12.3s";
      }, 1800);

      return task.id;
    },
    removeDataset(id) {
      this.datasets = this.datasets.filter((d) => d.id !== id);
    },
    updateDataset(id, patch) {
      const idx = this.datasets.findIndex((d) => d.id === id);
      if (idx === -1) return;
      this.datasets[idx] = { ...this.datasets[idx], ...patch };
    },
    removeAlgorithm(id) {
      this.algorithms = this.algorithms.filter((a) => a.id !== id);
    },
    createRun(payload) {
      const ts = nowStr();
      const run = {
        id: `run_${Date.now()}`,
        status: "排队中",
        createdAt: ts,
        // 下面这些先给默认值，方便 Compare/导出用
        elapsed: "-",
        metrics: null, // { psnr: xx, ssim: xx, niqe: xx } 后面再接真实计算
        ...payload,
      };

      this.runs.unshift(run);

      // 模拟队列推进
      setTimeout(() => {
        this.updateRunStatus(run.id, "运行中");
      }, 600);

      setTimeout(() => {
        this.updateRunStatus(run.id, "已完成");
        // 给个演示用耗时+指标
        run.elapsed = "12.3s";
        run.metrics = { psnr: 28.6, ssim: 0.86, niqe: 4.2 };
      }, 1800);

      return run.id;
    },


    updateRunStatus(id, status) {
      const idx = this.runs.findIndex((r) => r.id === id);
      if (idx === -1) return;
      this.runs[idx].status = normalizeStatus(status);
    },
    attachRunResult(id, patch) {
      const idx = this.runs.findIndex((r) => r.id === id);
      if (idx === -1) return;
      this.runs[idx] = { ...this.runs[idx], ...patch };
    },


  },
});
