<template>
  <div class="page">
    <h2 class="title">结果对比与快速选型</h2>

    <el-card shadow="never" class="card">
      <div class="filters">
        <el-select v-model="task" placeholder="选择任务类型" style="width: 180px">
          <el-option v-for="t in taskOptions" :key="t" :label="t" :value="t" />
        </el-select>

        <el-select v-model="datasetId" placeholder="选择数据集" style="width: 220px">
          <el-option v-for="d in store.datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>

        <el-checkbox v-model="onlyDone">只显示已完成</el-checkbox>

        <el-button type="primary" @click="reset">重置</el-button>

        <el-button @click="presetQuality">质量优先</el-button>
        <el-button @click="presetBalanced">平衡推荐</el-button>
        <el-button @click="presetSpeed">速度优先</el-button>

        <el-button @click="exportCsv">导出CSV</el-button>
        <el-button @click="exportXlsx">导出Excel</el-button>
        <el-button type="success" @click="exportRecommendCsv">导出CSV(含综合分/原因)</el-button>
        <el-button type="success" @click="exportRecommendXlsx">导出Excel(含综合分/原因)</el-button>

      </div>

      <div class="weights">
        <div class="weights-title">加权规则（自动归一化）</div>

        <div class="weights-grid">
          <div class="w-item">
            <div class="w-label">PSNR 权重</div>
            <el-input-number v-model="wPSNR" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-item">
            <div class="w-label">SSIM 权重</div>
            <el-input-number v-model="wSSIM" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-item">
            <div class="w-label">NIQE 权重（惩罚）</div>
            <el-input-number v-model="wNIQE" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-item">
            <div class="w-label">耗时 权重（惩罚）</div>
            <el-input-number v-model="wTIME" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-sum">
            当前权重和：<b>{{ weightSum.toFixed(2) }}</b>
            <span style="color:#909399">（会自动归一化，不用你手动凑 1）</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="card" style="margin-top: 12px">
      <div class="recommend" v-if="recommendText">
        <div class="recommend-title">推荐结果</div>
        <div class="recommend-body">{{ recommendText }}</div>
      </div>

      <el-table :data="tableRows" stripe style="width: 100%; margin-top: 10px">
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column prop="task" label="任务" width="110" />
        <el-table-column prop="datasetName" label="数据集" min-width="170" />
        <el-table-column prop="algorithmName" label="算法" min-width="170" />

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="isDone(row.status) ? 'success' : 'info'" disable-transitions>
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="psnr" label="PSNR" width="90" />
        <el-table-column prop="ssim" label="SSIM" width="90" />
        <el-table-column prop="niqe" label="NIQE" width="90" />
        <el-table-column prop="elapsed" label="耗时" width="90" />

        <el-table-column prop="score" label="综合分" width="110" sortable />

        <el-table-column label="推荐原因" min-width="320">
          <template #default="{ row }">
            <div style="line-height: 1.5; color: #303133">
              {{ row.reason || "-" }}
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="tableRows.length === 0" class="empty">
        当前筛选条件下没有可对比的运行记录。你可以先去“新建评测”跑几次结果。
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useAppStore } from "../stores/app";
import * as XLSX from "xlsx";

const store = useAppStore();

const task = ref("");
const datasetId = ref("");
const onlyDone = ref(true);

// 默认权重（你不用选，我给你唯一推荐配置）
// 主打画质：PSNR + SSIM；兼顾自然度与速度：NIQE、耗时作为惩罚项
const wPSNR = ref(3.5);
const wSSIM = ref(3.5);
const wNIQE = ref(2.0);
const wTIME = ref(1.0);

function presetQuality() {
  // 画质最重要：PSNR/SSIM 更大权重；NIQE 次之；耗时最少
  wPSNR.value = 4.0;
  wSSIM.value = 4.0;
  wNIQE.value = 1.5;
  wTIME.value = 0.5;
}

function presetBalanced() {
  // 默认推荐（你现在 reset 里也是这个）
  wPSNR.value = 3.5;
  wSSIM.value = 3.5;
  wNIQE.value = 2.0;
  wTIME.value = 1.0;
}

function presetSpeed() {
  // 速度优先：耗时惩罚更大，同时保持画质底线
  wPSNR.value = 2.5;
  wSSIM.value = 2.5;
  wNIQE.value = 1.5;
  wTIME.value = 3.5;
}


const weightSum = computed(() => Number(wPSNR.value) + Number(wSSIM.value) + Number(wNIQE.value) + Number(wTIME.value));

onMounted(async () => {
  if (!store.runs || store.runs.length === 0) {
    try {
      await store.fetchRuns();
    } catch (e) {
      console.warn(e);
    }
  }
});

const taskOptions = computed(() => {
  const s = new Set(store.algorithms.map((a) => a.task).filter(Boolean));
  return Array.from(s);
});

function statusText(status) {
  if (status === "done" || status === "已完成") return "已完成";
  if (status === "running" || status === "运行中") return "运行中";
  if (status === "failed" || status === "失败") return "失败";
  if (status === "queued" || status === "排队中") return "排队中";
  return status || "-";
}

function isDone(status) {
  return status === "已完成" || status === "done";
}

function reset() {
  task.value = "";
  datasetId.value = "";
  onlyDone.value = true;
  wPSNR.value = 3.5;
  wSSIM.value = 3.5;
  wNIQE.value = 2.0;
  wTIME.value = 1.0;
}

function mapTaskLabelToType(label) {
  const m = {
    去噪: "denoise",
    去模糊: "deblur",
    去雾: "dehaze",
    超分辨率: "sr",
    低照度增强: "lowlight",
    视频去噪: "video_denoise",
    视频超分: "video_sr",
  };
  return m[label] || "";
}

function buildExportUrl(fmt) {
  const params = new URLSearchParams();
  params.set("format", fmt);

  if (onlyDone.value) params.set("status", "done");
  if (task.value) params.set("task_type", mapTaskLabelToType(task.value));
  if (datasetId.value) params.set("dataset_id", datasetId.value);

  return `http://127.0.0.1:8000/runs/export?${params.toString()}`;
}

function exportCsv() {
  window.open(buildExportUrl("csv"), "_blank");
}

function exportXlsx() {
  window.open(buildExportUrl("xlsx"), "_blank");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function buildExportRows() {
  // 用当前表格数据（已应用筛选、排序、综合分、原因）
  return (tableRows.value || []).map((r) => ({
    创建时间: r.createdAt ?? "",
    任务: r.task ?? "",
    数据集: r.datasetName ?? "",
    算法: r.algorithmName ?? "",
    状态: statusText(r.status),
    PSNR: r.psnr ?? "",
    SSIM: r.ssim ?? "",
    NIQE: r.niqe ?? "",
    耗时: r.elapsed ?? "",
    综合分: Number.isFinite(r.score) ? r.score : "",
    推荐原因: r.reason ?? "",
    RunID: r.id ?? "",
  }));
}

function exportRecommendCsv() {
  const rows = buildExportRows();
  if (!rows.length) return alert("当前没有可导出的记录");

  const headers = Object.keys(rows[0]);
  const escape = (v) => {
    const s = String(v ?? "");
    // 含逗号/引号/换行 -> 用双引号包裹，并转义双引号
    if (/[,"\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };

  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];

  // Excel 友好：加 BOM
  const csvText = "\uFEFF" + lines.join("\n");
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadBlob(blob, `compare_recommend_${ts}.csv`);
}

function exportRecommendXlsx() {
  const rows = buildExportRows();
  if (!rows.length) return alert("当前没有可导出的记录");

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "compare");

  const out = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  const blob = new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadBlob(blob, `compare_recommend_${ts}.xlsx`);
}


// ---------- 评分：归一化 + 加权（可解释） ----------

function toNumber(v) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

// elapsed 形如 "1.234s" 或 "-"，转成秒
function parseElapsedSeconds(elapsed) {
  if (elapsed == null) return null;
  if (typeof elapsed === "number") return elapsed;
  const s = String(elapsed);
  const m = s.match(/([\d.]+)/);
  if (!m) return null;
  const x = Number(m[1]);
  return Number.isFinite(x) ? x : null;
}

function minMax(values) {
  const nums = values.filter((x) => Number.isFinite(x));
  if (nums.length === 0) return { min: null, max: null };
  return { min: Math.min(...nums), max: Math.max(...nums) };
}

function norm01(x, min, max) {
  if (!Number.isFinite(x) || !Number.isFinite(min) || !Number.isFinite(max)) return null;
  if (max === min) return 1.0; // 全一样就给满分，避免 NaN
  return (x - min) / (max - min);
}

const tableRows = computed(() => {
  const dsMap = new Map(store.datasets.map((d) => [d.id, d]));
  const algMap = new Map(store.algorithms.map((a) => [a.id, a]));

  let runs = store.runs.slice();

  if (task.value) runs = runs.filter((r) => r.task === task.value);
  if (datasetId.value) runs = runs.filter((r) => r.datasetId === datasetId.value);
  if (onlyDone.value) runs = runs.filter((r) => isDone(r.status));

  // 先提取数值数组，做归一化区间
  const psnrs = runs.map((r) => toNumber(r.psnr)).filter((x) => x != null);
  const ssims = runs.map((r) => toNumber(r.ssim)).filter((x) => x != null);
  const niqes = runs.map((r) => toNumber(r.niqe)).filter((x) => x != null);
  const times = runs.map((r) => parseElapsedSeconds(r.elapsed)).filter((x) => x != null);

  const mmPSNR = minMax(psnrs);
  const mmSSIM = minMax(ssims);
  const mmNIQE = minMax(niqes);
  const mmTIME = minMax(times);

  // 权重自动归一化
  const sum = weightSum.value > 0 ? weightSum.value : 1;
  const W = {
    psnr: Number(wPSNR.value) / sum,
    ssim: Number(wSSIM.value) / sum,
    niqe: Number(wNIQE.value) / sum,
    time: Number(wTIME.value) / sum,
  };

  // 做排名对比用（解释原因）
  function rankBy(key, betterHigh = true) {
    const arr = runs
      .map((r) => {
        let v = null;
        if (key === "psnr") v = toNumber(r.psnr);
        if (key === "ssim") v = toNumber(r.ssim);
        if (key === "niqe") v = toNumber(r.niqe);
        if (key === "time") v = parseElapsedSeconds(r.elapsed);
        return { id: r.id, v };
      })
      .filter((x) => x.v != null);

    arr.sort((a, b) => (betterHigh ? b.v - a.v : a.v - b.v));
    const pos = new Map();
    arr.forEach((x, i) => pos.set(x.id, i + 1));
    return pos;
  }

  const rankPSNR = rankBy("psnr", true);
  const rankSSIM = rankBy("ssim", true);
  const rankNIQE = rankBy("niqe", false);
  const rankTIME = rankBy("time", false);

  const rows = runs.map((r) => {
    const ds = dsMap.get(r.datasetId);
    const alg = algMap.get(r.algorithmId);

    const psnr = toNumber(r.psnr);
    const ssim = toNumber(r.ssim);
    const niqe = toNumber(r.niqe);
    const tsec = parseElapsedSeconds(r.elapsed);

    const nPSNR = norm01(psnr, mmPSNR.min, mmPSNR.max); // 越大越好
    const nSSIM = norm01(ssim, mmSSIM.min, mmSSIM.max); // 越大越好
    const nNIQE = norm01(niqe, mmNIQE.min, mmNIQE.max); // 越小越好 -> 用 (1-n)
    const nTIME = norm01(tsec, mmTIME.min, mmTIME.max); // 越小越好 -> 用 (1-n)

    // 缺指标：不给分，排最后
    const okAll = [nPSNR, nSSIM, nNIQE, nTIME].every((x) => x != null);

    let score = -Infinity;
    if (okAll) {
      const s =
        W.psnr * nPSNR +
        W.ssim * nSSIM +
        W.niqe * (1 - nNIQE) +
        W.time * (1 - nTIME);
      score = Number(s.toFixed(4));
    }

    // 解释原因：挑出贡献最大/排名最好项
    let reason = "";
    if (okAll) {
      const parts = [];

      const r1 = rankPSNR.get(r.id);
      const r2 = rankSSIM.get(r.id);
      const r3 = rankNIQE.get(r.id);
      const r4 = rankTIME.get(r.id);

      // 优先讲“排名第一/前二”的指标
      if (r1 === 1) parts.push("PSNR最高");
      else if (r1 === 2) parts.push("PSNR第2");
      if (r2 === 1) parts.push("SSIM最高");
      else if (r2 === 2) parts.push("SSIM第2");
      if (r3 === 1) parts.push("NIQE最低(更自然)");
      else if (r3 === 2) parts.push("NIQE第2低");
      if (r4 === 1) parts.push("耗时最短");
      else if (r4 === 2) parts.push("耗时第2短");

      // 如果没有特别突出的，就讲“均衡”
      if (parts.length === 0) {
        parts.push("多指标表现均衡");
      }

      // 再补一句：按权重强调主导因素
      const main = [
        { k: "PSNR", w: W.psnr },
        { k: "SSIM", w: W.ssim },
        { k: "NIQE", w: W.niqe },
        { k: "耗时", w: W.time },
      ].sort((a, b) => b.w - a.w);

      reason = `${parts.join("，")}；权重侧重：${main[0].k}(${(main[0].w * 100).toFixed(
        0
      )}%) + ${main[1].k}(${(main[1].w * 100).toFixed(0)}%)`;
    }

    return {
      ...r,
      datasetName: ds ? ds.name : r.datasetId,
      algorithmName: alg ? alg.name : r.algorithmId,
      score,
      reason,
    };
  });

  rows.sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
  return rows;
});

const recommendText = computed(() => {
  if (tableRows.value.length === 0) return "";
  const top = tableRows.value[0];
  if (!Number.isFinite(top.score)) return "";

  return [
    `当前筛选条件下，推荐优先选择：${top.algorithmName}。`,
    `原因：${top.reason}`,
    `指标：PSNR=${top.psnr}，SSIM=${top.ssim}，NIQE=${top.niqe}，耗时=${top.elapsed || "—"}。`,
  ].join(" ");
});
</script>

<style scoped>
.page { padding: 12px; }
.title { margin: 0 0 10px 0; font-size: 18px; font-weight: 600; }
.card { border-radius: 10px; }
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.weights { margin-top: 12px; padding-top: 10px; border-top: 1px solid #ebeef5; }
.weights-title { font-weight: 600; margin-bottom: 8px; }
.weights-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 10px 16px;
  align-items: end;
}
.w-item { display: flex; gap: 10px; align-items: center; }
.w-label { width: 140px; color: #606266; }
.w-sum { grid-column: 1 / -1; color: #606266; }

.recommend {
  padding: 10px 12px;
  border: 1px dashed #dcdfe6;
  border-radius: 10px;
}
.recommend-title { font-weight: 600; margin-bottom: 6px; }
.recommend-body { line-height: 1.6; }
.empty { margin-top: 12px; color: #909399; }
</style>
