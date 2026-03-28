<template>
  <div class="page">
    <h2 class="title">综合对比与推荐</h2>
    <div class="subtitle">面向图像与视频复原任务的指标对比、快速选型与结论导出</div>

    <el-card shadow="never" class="card">
      <div class="filters">
        <el-select v-model="task" placeholder="选择任务类型" style="width: 180px">
          <el-option v-for="t in taskOptions" :key="t" :label="t" :value="t" />
        </el-select>

        <el-select v-model="datasetId" placeholder="选择数据集" style="width: 220px">
          <el-option v-for="d in store.datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>

        <el-checkbox v-model="onlyDone">仅显示已完成</el-checkbox>

        <el-button type="primary" @click="reset">重置筛选</el-button>
        <el-button @click="clearCache">清除缓存</el-button>

        <el-button @click="presetQuality">质量优先</el-button>
        <el-button @click="presetBalanced">均衡模式</el-button>
        <el-button @click="presetSpeed">速度优先</el-button>
        <el-button type="warning" :disabled="bulkRunning" @click="bulkRunBaselines">
          {{ bulkRunning ? "批量创建中..." : "批量创建基线Run" }}
        </el-button>
        <el-checkbox v-model="bulkStrictValidate">严格校验配对</el-checkbox>
        <el-checkbox v-model="bulkOnlyBaselines">仅使用基线算法</el-checkbox>
        <el-select v-model="bulkParamScheme" style="width: 140px" size="small">
          <el-option label="默认参数" value="default" />
          <el-option label="速度参数" value="speed" />
          <el-option label="质量参数" value="quality" />
        </el-select>

        <el-button @click="exportCsv">导出原始CSV</el-button>
        <el-button @click="exportXlsx">导出原始Excel</el-button>
        <el-button type="success" @click="exportRecommendCsv">导出推荐CSV（含评分/理由）</el-button>
        <el-button type="success" @click="exportRecommendXlsx">导出推荐Excel（含评分/理由）</el-button>
        <el-button type="success" @click="exportConclusionMd">导出结论Markdown</el-button>

      </div>

      <div class="fast-select">
        <div class="fast-select-head">
          <div class="fast-select-title">核心算法快速选型（LinUCB）</div>
          <div class="fast-select-actions">
            <el-input-number v-model="fastTopK" :min="1" :max="10" :step="1" size="small" />
            <el-input-number v-model="fastAlpha" :min="0" :max="2" :step="0.05" size="small" />
            <el-button type="primary" :loading="fastLoading" @click="runFastSelect">
              {{ fastLoading ? "快速选型中..." : "快速选型 Top-K" }}
            </el-button>
            <el-button
              type="warning"
              :disabled="!fastRecommendations.length || fastCreateRunning"
              :loading="fastCreateRunning"
              @click="createRunsByFastSelect"
            >
              {{ fastCreateRunning ? "创建中..." : "按推荐一键创建Run" }}
            </el-button>
          </div>
        </div>

        <div class="fast-select-meta" v-if="fastContext">
          候选算法 {{ fastContext.candidate_count ?? "-" }} 个，历史样本 {{ fastContext.historical_run_count ?? "-" }}，
          数据配对 {{ fastContext.pair_count ?? "-" }}，alpha={{ fastContext.alpha ?? "-" }}
        </div>

        <el-table
          v-if="fastRecommendations.length"
          :data="fastRecommendations"
          stripe
          size="small"
          style="width: 100%; margin-top: 8px"
        >
          <el-table-column label="排名" width="70">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="algorithm_name" label="算法" min-width="170" />
          <el-table-column prop="score" label="UCB分数" width="110" />
          <el-table-column prop="mean_reward" label="历史均值" width="110" />
          <el-table-column prop="uncertainty" label="不确定性" width="110" />
          <el-table-column prop="sample_count" label="样本数" width="90" />
        </el-table>
      </div>

      <div class="weights">
        <div class="weights-title">评分权重设置</div>

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
            <div class="w-label">NIQE 权重</div>
            <el-input-number v-model="wNIQE" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-item">
            <div class="w-label">耗时权重</div>
            <el-input-number v-model="wTIME" :min="0" :max="10" :step="0.1" />
          </div>

          <div class="w-sum">
            权重总和：<b>{{ weightSum.toFixed(2) }}</b>
            <span style="color:#909399">建议接近 1</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="card" style="margin-top: 12px">
      <div class="recommend" v-if="recommendText">
        <div class="recommend-title">推荐结论</div>
        <div class="recommend-body">{{ recommendText }}</div>
      </div>

      <div class="chart-bar" v-if="chartItems.length">
        <div class="chart-head">
          <div class="chart-title">指标排行 Top {{ chartTopN }}</div>
          <div class="chart-actions">
            <el-select v-model="chartMetric" style="width: 200px" size="small">
              <el-option label="综合评分" value="score" />
              <el-option label="PSNR" value="psnr" />
              <el-option label="SSIM" value="ssim" />
              <el-option label="NIQE" value="niqe" />
              <el-option label="耗时(秒)" value="time" />
            </el-select>
            <el-select v-model="chartTopN" style="width: 140px" size="small">
              <el-option :label="'Top 5'" :value="5" />
              <el-option :label="'Top 10'" :value="10" />
              <el-option :label="'Top 15'" :value="15" />
            </el-select>
            <el-button size="small" @click="exportChartPng">导出图表PNG</el-button>
          </div>
        </div>

        <div class="chart-wrap">
          <canvas
            ref="chartCanvas"
            class="chart-canvas"
            @mousemove="onChartMove"
            @mouseleave="onChartLeave"
          ></canvas>
          <div
            v-if="chartTip.visible"
            class="chart-tooltip"
            :style="{ left: chartTip.x + 'px', top: chartTip.y + 'px' }"
          >
            {{ chartTip.text }}
          </div>
        </div>
      </div>

      <el-table :data="tableRows" stripe style="width: 100%; margin-top: 10px">
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column prop="task" label="任务" width="110" />
        <el-table-column prop="datasetName" label="数据集" min-width="170" />
        <el-table-column prop="algorithmName" label="算法" min-width="170" />

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" disable-transitions>
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="psnr" label="PSNR" width="90" />
        <el-table-column prop="ssim" label="SSIM" width="90" />
        <el-table-column prop="niqe" label="NIQE" width="90" />
        <el-table-column prop="elapsed" label="耗时" width="90" />

        <el-table-column prop="score" label="综合分" width="110" sortable />

        <el-table-column label="推荐理由/备注" min-width="320">
          <template #default="{ row }">
            <div style="line-height: 1.5; color: #303133">
              {{ row.reason || "-" }}
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="tableRows.length === 0" class="empty">
        暂无符合条件的运行结果
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useAppStore } from "../stores/app";
import { toTaskType } from "../stores/app";
import * as XLSX from "xlsx";

const store = useAppStore();

const task = ref("");
const datasetId = ref("");
const onlyDone = ref(true);
const _LS_KEY = "compare_filters_v1";

const wPSNR = ref(3.5);
const wSSIM = ref(3.5);
const wNIQE = ref(2.0);
const wTIME = ref(1.0);

function clampNumber(v, min, max, fallback) {
  const x = Number(v);
  if (!Number.isFinite(x)) return fallback;
  return Math.max(min, Math.min(max, x));
}

function loadCache() {
  try {
    const raw = localStorage.getItem(_LS_KEY);
    if (!raw) return;
    const obj = JSON.parse(raw);
    if (!obj || typeof obj !== "object") return;

    if (typeof obj.task === "string") task.value = obj.task;
    if (typeof obj.datasetId === "string") datasetId.value = obj.datasetId;
    if (typeof obj.onlyDone === "boolean") onlyDone.value = obj.onlyDone;

    if (obj.wPSNR != null) wPSNR.value = clampNumber(obj.wPSNR, 0, 10, 3.5);
    if (obj.wSSIM != null) wSSIM.value = clampNumber(obj.wSSIM, 0, 10, 3.5);
    if (obj.wNIQE != null) wNIQE.value = clampNumber(obj.wNIQE, 0, 10, 2.0);
    if (obj.wTIME != null) wTIME.value = clampNumber(obj.wTIME, 0, 10, 1.0);

    if (obj.chartMetric != null) chartMetric.value = String(obj.chartMetric);
    if (obj.chartTopN != null) chartTopN.value = clampNumber(obj.chartTopN, 1, 50, 10);
  } catch {
    return;
  }
}

function saveCache() {
  try {
    const obj = {
      task: task.value,
      datasetId: datasetId.value,
      onlyDone: onlyDone.value,
      wPSNR: wPSNR.value,
      wSSIM: wSSIM.value,
      wNIQE: wNIQE.value,
      wTIME: wTIME.value,
      chartMetric: chartMetric.value,
      chartTopN: chartTopN.value,
    };
    localStorage.setItem(_LS_KEY, JSON.stringify(obj));
  } catch {
    return;
  }
}

function clearCache() {
  try {
    localStorage.removeItem(_LS_KEY);
  } catch {
    return;
  }
}

function presetQuality() {
  wPSNR.value = 4.0;
  wSSIM.value = 4.0;
  wNIQE.value = 1.5;
  wTIME.value = 0.5;
}

function presetBalanced() {
  wPSNR.value = 3.5;
  wSSIM.value = 3.5;
  wNIQE.value = 2.0;
  wTIME.value = 1.0;
}

function presetSpeed() {
  wPSNR.value = 2.5;
  wSSIM.value = 2.5;
  wNIQE.value = 1.5;
  wTIME.value = 3.5;
}


const weightSum = computed(() => Number(wPSNR.value) + Number(wSSIM.value) + Number(wNIQE.value) + Number(wTIME.value));

onMounted(async () => {
  loadCache();
  if (!store.runs || store.runs.length === 0) {
    try {
      await store.fetchRuns();
    } catch (e) {
      console.warn(e);
    }
  }
  sanitizeFilters();
  sanitizeChart();
  saveCache();
});

const taskOptions = computed(() => {
  const s = new Set(store.algorithms.map((a) => a.task).filter(Boolean));
  return Array.from(s);
});

watch([task, datasetId, onlyDone, wPSNR, wSSIM, wNIQE, wTIME], () => saveCache());

function sanitizeFilters() {
  const tasks = new Set(taskOptions.value || []);
  if (task.value && !tasks.has(task.value)) task.value = "";

  const dsIds = new Set((store.datasets || []).map((d) => d.id));
  if (datasetId.value && !dsIds.has(datasetId.value)) datasetId.value = "";
}

watch([taskOptions, () => (store.datasets || []).length], () => {
  sanitizeFilters();
  saveCache();
});

function statusText(status) {
  if (status === "done" || status === "completed" || status === "已完成") return "已完成";
  if (status === "running" || status === "运行中") return "运行中";
  if (status === "failed" || status === "失败") return "失败";
  if (status === "queued" || status === "排队中") return "排队中";
  if (status === "canceling" || status === "取消中") return "取消中";
  if (status === "canceled" || status === "已取消") return "已取消";
  return status || "-";
}

function isDone(status) {
  return status === "done" || status === "completed" || status === "已完成";
}

function statusTagType(status) {
  if (status === "done" || status === "completed" || status === "已完成") return "success";
  if (status === "running" || status === "运行中") return "warning";
  if (status === "failed" || status === "失败") return "danger";
  if (status === "queued" || status === "排队中") return "info";
  if (status === "canceling" || status === "取消中") return "warning";
  if (status === "canceled" || status === "已取消") return "info";
  return "info";
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

const bulkRunning = ref(false);
const bulkStrictValidate = ref(true);
const bulkOnlyBaselines = ref(true);
const bulkParamScheme = ref("default");
const fastTopK = ref(2);
const fastAlpha = ref(0.35);
const fastLoading = ref(false);
const fastCreateRunning = ref(false);
const fastContext = ref(null);
const fastRecommendations = ref([]);

const BASELINE_IDS_BY_TASK_TYPE = {
  denoise: ["alg_dn_cnn", "alg_denoise_bilateral", "alg_denoise_gaussian", "alg_denoise_median"],
  dehaze: ["alg_dehaze_dcp", "alg_dehaze_clahe", "alg_dehaze_gamma"],
  deblur: ["alg_deblur_unsharp", "alg_deblur_laplacian"],
  sr: ["alg_sr_bicubic", "alg_sr_lanczos", "alg_sr_nearest"],
  lowlight: ["alg_lowlight_gamma", "alg_lowlight_clahe"],
  video_denoise: ["alg_video_denoise_gaussian", "alg_video_denoise_median"],
  video_sr: ["alg_video_sr_bicubic", "alg_video_sr_lanczos"],
};

async function bulkRunBaselines() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel) return alert("请先选择任务类型");
  if (!dsId) return alert("请先选择数据集");

  const taskType = mapTaskLabelToType(taskLabel);
  if (!taskType) return alert("当前任务类型无法映射为 task_type");

  const baselineIdSet = new Set(BASELINE_IDS_BY_TASK_TYPE[taskType] || []);

  let algs = (store.algorithms || []).filter((a) => a?.task === taskLabel);
  if (bulkOnlyBaselines.value) {
    algs = algs.filter((a) => baselineIdSet.has(a.id));
  }
  if (!algs.length) return alert("当前任务没有可创建的算法");

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const batchId = `batch_${taskType}_${dsId}_${ts}_${Math.random().toString(16).slice(2, 6)}`;
  const batchName = `${taskLabel}-${dsId}-${bulkParamScheme.value}-${ts}`;

  const ok = confirm(
    `将为任务「${taskLabel}」数据集「${dsId}」创建 ${algs.length} 个 Run。\n` +
      `参数方案：${bulkParamScheme.value}；严格校验：${bulkStrictValidate.value ? "开启" : "关闭"}；仅基线：${bulkOnlyBaselines.value ? "是" : "否"}\n` +
      `批次ID：${batchId}\n确认继续吗？`
  );
  if (!ok) return;

  task.value = taskLabel;
  datasetId.value = dsId;

  if (bulkRunning.value) return;
  bulkRunning.value = true;
  const failed = [];
  const skipped = [];
  const created = [];

  const existingKey = (r) => `${r?.taskType || ""}|${r?.datasetId || ""}|${r?.algorithmId || ""}`;
  const existing = new Set((store.runs || []).map(existingKey));

  for (const a of algs) {
    const key = `${taskType}|${dsId}|${a.id}`;
    if (existing.has(key)) {
      skipped.push(`${a?.name || a?.id}`);
      continue;
    }
    try {
      const params = {};
      const scheme = bulkParamScheme.value;
      const algDefault =
        a?.defaultParams && typeof a.defaultParams === "object" && !Array.isArray(a.defaultParams) ? a.defaultParams : {};
      const algPresets =
        a?.paramPresets && typeof a.paramPresets === "object" && !Array.isArray(a.paramPresets) ? a.paramPresets : {};
      const picked =
        scheme === "speed" || scheme === "quality"
          ? (algPresets?.[scheme] && typeof algPresets[scheme] === "object" ? algPresets[scheme] : {})
          : algDefault;
      Object.assign(params, picked);
      params.batch_id = batchId;
      params.batch_name = batchName;
      params.param_scheme = scheme;

      await store.createRun({
        task: taskLabel,
        datasetId: dsId,
        algorithmId: a.id,
        metrics: ["PSNR", "SSIM", "NIQE"],
        params,
        strictValidate: bulkStrictValidate.value,
      });
      created.push(`${a?.name || a?.id}`);
    } catch (e) {
      failed.push(`${a?.name || a?.id}: ${e?.message || e}`);
    }
  }

  bulkRunning.value = false;
  const parts = [];
  if (created.length) parts.push(`已创建 ${created.length} 个`);
  if (skipped.length) parts.push(`跳过重复 ${skipped.length} 个`);
  if (failed.length) parts.push(`失败 ${failed.length} 个`);
  if (failed.length) return alert(`${parts.join("，")}\n\n失败详情：\n${failed.join("\n")}`);
  alert(`${parts.join("，")}\n\n批次ID：${batchId}\n可在 Runs/Compare 中按批次筛选查看`);
}

function mapTaskLabelToType(label) {
  return toTaskType(label || "");
}

async function runFastSelect() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel) return alert("请先选择任务类型");
  if (!dsId) return alert("请先选择数据集");
  const taskType = mapTaskLabelToType(taskLabel);
  if (!taskType) return alert("当前任务类型无法映射到 task_type");

  let algs = (store.algorithms || []).filter((a) => a?.task === taskLabel);
  if (bulkOnlyBaselines.value) {
    const baselineIdSet = new Set(BASELINE_IDS_BY_TASK_TYPE[taskType] || []);
    algs = algs.filter((a) => baselineIdSet.has(a.id));
  }
  if (!algs.length) return alert("当前任务没有可用候选算法");

  const topK = Math.max(1, Math.min(Number(fastTopK.value) || 2, 10));
  const alpha = Math.max(0, Math.min(Number(fastAlpha.value) || 0.35, 2));
  fastTopK.value = topK;
  fastAlpha.value = alpha;
  task.value = taskLabel;
  datasetId.value = dsId;

  try {
    fastLoading.value = true;
    const out = await store.fastSelect({
      task: taskLabel,
      datasetId: dsId,
      candidateAlgorithmIds: algs.map((x) => x.id),
      topK,
      alpha,
    });
    const list = Array.isArray(out?.recommendations) ? out.recommendations : [];
    const algById = new Map((store.algorithms || []).map((a) => [a.id, a]));
    fastRecommendations.value = list.map((x) => {
      const aid = String(x?.algorithm_id || "");
      const alg = algById.get(aid);
      return {
        algorithm_id: aid,
        algorithm_name: alg?.name || aid,
        score: Number(x?.score ?? 0).toFixed(4),
        mean_reward: Number(x?.mean_reward ?? 0).toFixed(4),
        uncertainty: Number(x?.uncertainty ?? 0).toFixed(4),
        sample_count: Number(x?.sample_count ?? 0),
      };
    });
    fastContext.value = out?.context && typeof out.context === "object" ? out.context : null;
    if (!fastRecommendations.value.length) {
      alert("快速选型已执行，但当前没有返回推荐结果");
    }
  } catch (e) {
    fastRecommendations.value = [];
    fastContext.value = null;
    alert(`快速选型失败：${e?.message || e}`);
  } finally {
    fastLoading.value = false;
  }
}

async function createRunsByFastSelect() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel || !dsId) return alert("请先选择任务和数据集");
  if (!fastRecommendations.value.length) return alert("请先执行快速选型");
  if (fastCreateRunning.value) return;

  const taskType = mapTaskLabelToType(taskLabel);
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const batchId = `batch_fast_${taskType}_${dsId}_${ts}_${Math.random().toString(16).slice(2, 6)}`;
  const batchName = `fast-select-${taskLabel}-${dsId}-${ts}`;

  const existingKey = (r) => `${r?.taskType || ""}|${r?.datasetId || ""}|${r?.algorithmId || ""}`;
  const existing = new Set((store.runs || []).map(existingKey));

  fastCreateRunning.value = true;
  const failed = [];
  let created = 0;
  for (const rec of fastRecommendations.value) {
    const aid = rec.algorithm_id;
    const key = `${taskType}|${dsId}|${aid}`;
    if (existing.has(key)) continue;
    try {
      await store.createRun({
        task: taskLabel,
        datasetId: dsId,
        algorithmId: aid,
        metrics: ["PSNR", "SSIM", "NIQE"],
        params: {
          batch_id: batchId,
          batch_name: batchName,
          source: "fast_select",
          fast_top_k: fastTopK.value,
          fast_alpha: fastAlpha.value,
        },
        strictValidate: bulkStrictValidate.value,
      });
      created += 1;
    } catch (e) {
      failed.push(`${aid}: ${e?.message || e}`);
    }
  }
  fastCreateRunning.value = false;
  if (failed.length) {
    return alert(`已创建 ${created} 个推荐Run，失败 ${failed.length} 个\n\n${failed.join("\n")}`);
  }
  alert(`已按快速选型结果创建 ${created} 个Run\n批次ID：${batchId}`);
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
  return (tableRows.value || []).map((r) => ({
    "创建时间": r.createdAt ?? "",
    "任务": r.task ?? "",
    "数据集": r.datasetName ?? "",
    "算法": r.algorithmName ?? "",
    "状态": statusText(r.status),
    "PSNR": r.psnr ?? "",
    "SSIM": r.ssim ?? "",
    "NIQE": r.niqe ?? "",
    "耗时": r.elapsed ?? "",
    "综合分": Number.isFinite(r.score) ? r.score : "",
    "推荐理由/备注": r.reason ?? "",
    "RunID": r.id ?? "",
  }));
}

function exportRecommendCsv() {
  const rows = buildExportRows();
  if (!rows.length) return alert("当前没有可导出的推荐结果");

  const headers = Object.keys(rows[0]);
  const escape = (v) => {
    const s = String(v ?? "");
    if (/[,"\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };

  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];

  const csvText = "\uFEFF" + lines.join("\n");
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadBlob(blob, `compare_recommend_${ts}.csv`);
}

function exportRecommendXlsx() {
  const rows = buildExportRows();
  if (!rows.length) return alert("当前没有可导出的推荐结果");

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

function exportConclusionMd() {
  const rows = tableRows.value || [];
  if (!rows.length) return alert("当前没有可导出的推荐结果");

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const mdLines = [];
  mdLines.push(`# 对比推荐结论 ${ts}`);
  mdLines.push("");
  mdLines.push(`- 任务：${task.value || "-"}`);
  mdLines.push(`- 数据集：${datasetId.value || "-"}`);
  mdLines.push(`- 仅已完成：${onlyDone.value ? "是" : "否"}`);
  mdLines.push(`- 权重：PSNR=${wPSNR.value}，SSIM=${wSSIM.value}，NIQE=${wNIQE.value}，耗时=${wTIME.value}`);
  mdLines.push("");
  if (recommendText.value) {
    mdLines.push("## 推荐结论");
    mdLines.push(recommendText.value);
    mdLines.push("");
  }
  mdLines.push("## Top 10 明细");
  mdLines.push("");
  mdLines.push("| 排名 | 算法 | PSNR | SSIM | NIQE | 耗时 | 综合分 | 推荐理由 | RunID |");
  mdLines.push("| --- | --- | --- | --- | --- | --- | --- | --- | --- |");
  for (let i = 0; i < Math.min(10, rows.length); i++) {
    const r = rows[i];
    mdLines.push(
      `| ${i + 1} | ${r.algorithmName || "-"} | ${r.psnr ?? "-"} | ${r.ssim ?? "-"} | ${r.niqe ?? "-"} | ${r.elapsed ?? "-"} | ${Number.isFinite(r.score) ? r.score : "-"} | ${(r.reason || "-").replace(/\n/g, " ")} | ${r.id || "-"} |`
    );
  }
  mdLines.push("");

  const blob = new Blob([mdLines.join("\n")], { type: "text/markdown;charset=utf-8" });
  downloadBlob(blob, `compare_conclusion_${ts}.md`);
}

function toNumber(v) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

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
  if (max === min) return 1.0;
  return (x - min) / (max - min);
}

const tableRows = computed(() => {
  const dsMap = new Map(store.datasets.map((d) => [d.id, d]));
  const algMap = new Map(store.algorithms.map((a) => [a.id, a]));

  let runs = store.runs.slice();

  if (task.value) runs = runs.filter((r) => r.task === task.value);
  if (datasetId.value) runs = runs.filter((r) => r.datasetId === datasetId.value);
  if (onlyDone.value) runs = runs.filter((r) => isDone(r.status));

  const psnrs = runs.map((r) => toNumber(r.psnr)).filter((x) => x != null);
  const ssims = runs.map((r) => toNumber(r.ssim)).filter((x) => x != null);
  const niqes = runs.map((r) => toNumber(r.niqe)).filter((x) => x != null);
  const times = runs.map((r) => parseElapsedSeconds(r.elapsed)).filter((x) => x != null);

  const mmPSNR = minMax(psnrs);
  const mmSSIM = minMax(ssims);
  const mmNIQE = minMax(niqes);
  const mmTIME = minMax(times);

  const sum = weightSum.value > 0 ? weightSum.value : 1;
  const W = {
    psnr: Number(wPSNR.value) / sum,
    ssim: Number(wSSIM.value) / sum,
    niqe: Number(wNIQE.value) / sum,
    time: Number(wTIME.value) / sum,
  };

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

    const nPSNR = norm01(psnr, mmPSNR.min, mmPSNR.max);
    const nSSIM = norm01(ssim, mmSSIM.min, mmSSIM.max);
    const nNIQE = norm01(niqe, mmNIQE.min, mmNIQE.max);
    const nTIME = norm01(tsec, mmTIME.min, mmTIME.max);

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

    let reason = "";
    if (okAll) {
      const parts = [];

      const r1 = rankPSNR.get(r.id);
      const r2 = rankSSIM.get(r.id);
      const r3 = rankNIQE.get(r.id);
      const r4 = rankTIME.get(r.id);

      if (r1 === 1) parts.push("PSNR 排名第1");
      else if (r1 === 2) parts.push("PSNR 排名第2");
      if (r2 === 1) parts.push("SSIM 排名第1");
      else if (r2 === 2) parts.push("SSIM 排名第2");
      if (r3 === 1) parts.push("NIQE 排名第1（越低越好）");
      else if (r3 === 2) parts.push("NIQE 排名第2");
      if (r4 === 1) parts.push("耗时排名第1");
      else if (r4 === 2) parts.push("耗时排名第2");

      if (parts.length === 0) {
        parts.push("综合表现稳定");
      }

      const main = [
        { k: "PSNR", w: W.psnr },
        { k: "SSIM", w: W.ssim },
        { k: "NIQE", w: W.niqe },
        { k: "耗时", w: W.time },
      ].sort((a, b) => b.w - a.w);

      reason = `${parts.join("，")}；主要受 ${main[0].k}(${(main[0].w * 100).toFixed(
        0
      )}%) 与 ${main[1].k}(${(main[1].w * 100).toFixed(0)}%) 权重影响`;
    }
    if (!reason) {
      const errText = r.errorText || r.error || "";
      if (errText) reason = errText;
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
    `推荐算法：${top.algorithmName}`,
    `推荐理由：${top.reason}`,
    `指标摘要：PSNR=${top.psnr}，SSIM=${top.ssim}，NIQE=${top.niqe}，耗时=${top.elapsed || "-"}`,
  ].join(" ");
});

const chartCanvas = ref(null);
const chartMetric = ref("score");
const chartTopN = ref(10);

let _chartHit = [];
const chartTip = ref({ visible: false, x: 0, y: 0, text: "" });

function _fmtValue(v) {
  if (!Number.isFinite(v)) return "-";
  if (chartMetric.value === "ssim") return v.toFixed(4);
  if (chartMetric.value === "time") return `${v.toFixed(3)}s`;
  if (chartMetric.value === "score") return v.toFixed(3);
  return v.toFixed(3);
}

function onChartLeave() {
  chartTip.value = { ...chartTip.value, visible: false };
}

function onChartMove(e) {
  const canvas = chartCanvas.value;
  if (!canvas) return;
  const wrap = canvas.parentElement;
  if (!wrap) return;
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  const hit = (_chartHit || []).find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  if (!hit) return onChartLeave();

  const wRect = wrap.getBoundingClientRect();
  const lx = Math.max(8, Math.min(wRect.width - 8, x + 12));
  const ly = Math.max(8, Math.min(wRect.height - 8, y + 12));
  chartTip.value = {
    visible: true,
    x: lx,
    y: ly,
    text: `${hit.name}：${hit.valueTxt}`,
  };
}

function sanitizeChart() {
  const allowed = new Set(["score", "psnr", "ssim", "niqe", "time"]);
  if (!allowed.has(chartMetric.value)) chartMetric.value = "score";
  const n = Number(chartTopN.value);
  if (![5, 10, 15].includes(n)) chartTopN.value = 10;
}

watch([chartMetric, chartTopN], () => saveCache());

const chartItems = computed(() => {
  const n = Math.max(1, Number(chartTopN.value) || 10);
  const rows = tableRows.value || [];

  const betterHigh = chartMetric.value === "niqe" || chartMetric.value === "time" ? false : true;

  const items = rows
    .map((r) => {
      const baseName = String(r.algorithmName ?? r.algorithmId ?? r.id ?? "");
      const id4 = String(r.id ?? "").slice(-4);
      const name = id4 ? `${baseName} #${id4}` : baseName;
      let v = null;
      if (chartMetric.value === "score") v = Number.isFinite(r.score) ? Number(r.score) : null;
      if (chartMetric.value === "psnr") v = toNumber(r.psnr);
      if (chartMetric.value === "ssim") v = toNumber(r.ssim);
      if (chartMetric.value === "niqe") v = toNumber(r.niqe);
      if (chartMetric.value === "time") v = parseElapsedSeconds(r.elapsed);
      return { name, value: v, raw: r };
    })
    .filter((x) => x.value != null);

  items.sort((a, b) => (betterHigh ? b.value - a.value : a.value - b.value));
  return items.slice(0, n);
});

function downloadDataUrl(dataUrl, filename) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function exportChartPng() {
  const c = chartCanvas.value;
  if (!c) return alert("当前图表未生成，无法导出");
  const dataUrl = c.toDataURL("image/png");
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadDataUrl(dataUrl, `compare_chart_${chartMetric.value}_${ts}.png`);
}

function drawChart() {
  const canvas = chartCanvas.value;
  if (!canvas) return;

  const items = chartItems.value || [];
  const wrap = canvas.parentElement;
  const cssW = Math.max(320, Math.floor(wrap?.clientWidth || 680));
  const cssH = items.length >= 10 ? 340 : 310;

  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  ctx.clearRect(0, 0, cssW, cssH);

  const padL = 56;
  const padR = 14;
  const padT = 18;
  const padB = 86;
  const plotW = cssW - padL - padR;
  const plotH = cssH - padT - padB;

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, cssW, cssH);

  ctx.strokeStyle = "#e5e7eb";
  ctx.lineWidth = 1;
  ctx.strokeRect(padL, padT, plotW, plotH);

  const values = items.map((x) => x.value).filter((x) => Number.isFinite(x));
  const maxV = values.length ? Math.max(...values) : 1;
  const minV = values.length ? Math.min(...values) : 0;
  const span = maxV - minV || 1;

  const grid = 4;
  ctx.font = "12px var(--el-font-family, system-ui)";
  ctx.fillStyle = "#6b7280";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= grid; i++) {
    const t = i / grid;
    const y = padT + plotH - t * plotH;
    ctx.strokeStyle = i === 0 ? "#e5e7eb" : "#f3f4f6";
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(padL + plotW, y);
    ctx.stroke();

    const v = minV + t * span;
    const txt = chartMetric.value === "ssim" ? v.toFixed(3) : v.toFixed(2);
    ctx.fillText(txt, padL - 6, y);
  }

  if (!items.length) {
    ctx.fillStyle = "#9ca3af";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("暂无图表数据", cssW / 2, cssH / 2);
    return;
  }

  const n = items.length;
  const gap = n >= 12 ? 6 : 10;
  const bw = Math.max(10, Math.floor((plotW - gap * (n - 1)) / n));
  const totalBarsW = bw * n + gap * (n - 1);
  const startX = padL + Math.max(0, Math.floor((plotW - totalBarsW) / 2));

  _chartHit = [];

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = "#374151";
  ctx.font = "11px var(--el-font-family, system-ui)";

  for (let i = 0; i < n; i++) {
    const it = items[i];
    const x = startX + i * (bw + gap);
    const v = Number(it.value);
    const nv = (v - minV) / span;
    const h = Math.max(1, Math.round(nv * plotH));
    const y = padT + plotH - h;

    const r = Math.min(6, Math.floor(bw / 3), Math.floor(h / 3));
    ctx.fillStyle = "#3b82f6";
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + bw - r, y);
    ctx.quadraticCurveTo(x + bw, y, x + bw, y + r);
    ctx.lineTo(x + bw, y + h);
    ctx.lineTo(x, y + h);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    ctx.fill();

    const valueTxt = _fmtValue(v);
    _chartHit.push({ x, y, w: bw, h, name: String(it.name || ""), valueTxt });
    if (bw >= 26 && h >= 16) {
      ctx.fillStyle = h >= 30 ? "#ffffff" : "#111827";
      ctx.textBaseline = h >= 30 ? "middle" : "bottom";
      ctx.font = "11px var(--el-font-family, system-ui)";
      const vy = h >= 30 ? y + 12 : y - 4;
      ctx.fillText(valueTxt, x + bw / 2, vy);
    }

    ctx.fillStyle = "#374151";
    ctx.textBaseline = "top";
    ctx.font = "10px var(--el-font-family, system-ui)";
    const label = String(it.name || "").slice(0, 18);
    const lx = x + bw / 2;
    const ly = padT + plotH + 12;
    ctx.save();
    ctx.translate(lx, ly);
    ctx.rotate(-Math.PI / 4);
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(label, 0, 0);
    ctx.restore();
  }

  ctx.fillStyle = "#111827";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.font = "12px var(--el-font-family, system-ui)";
  const titleMap = {
    score: "综合评分",
    psnr: "PSNR",
    ssim: "SSIM",
    niqe: "NIQE",
    time: "耗时(秒)",
  };
  const extra = chartMetric.value === "score" ? "（0~1，越大越好）" : "";
  ctx.fillText(`当前指标：${titleMap[chartMetric.value] || chartMetric.value}${extra}`, padL, 0);
}

watch([tableRows, chartMetric, chartTopN], async () => {
  await nextTick();
  drawChart();
});

onMounted(async () => {
  await nextTick();
  drawChart();
});
</script>

<style scoped>
.page { padding: 12px; }
.title { margin: 0 0 6px 0; font-size: 22px; font-weight: 700; color: #1b2f62; }
.subtitle { margin-bottom: 12px; color: #4f628f; font-size: 14px; }
.card {
  border-radius: 14px;
  border: 1px solid #d8e3ff;
  box-shadow: 0 14px 28px rgba(26, 78, 190, 0.1);
}
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.chart-bar { margin-top: 10px; padding-top: 10px; border-top: 1px solid #dbe6ff; }
.chart-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.chart-title { font-weight: 700; color: #294179; }
.chart-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.chart-wrap { margin-top: 10px; width: 100%; position: relative; }
.chart-canvas { width: 100%; height: 310px; border-radius: 10px; border: 1px solid #d8e3ff; background: #fff; }
.chart-tooltip {
  position: absolute;
  transform: translate(-8px, -8px);
  max-width: 420px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: rgba(17, 24, 39, 0.92);
  color: #ffffff;
  font-size: 12px;
  line-height: 1.3;
  pointer-events: none;
  white-space: nowrap;
}

.weights { margin-top: 12px; padding-top: 10px; border-top: 1px solid #dbe6ff; }
.fast-select {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #dbe6ff;
}
.fast-select-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.fast-select-title { font-weight: 700; color: #264181; }
.fast-select-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fast-select-meta { margin-top: 8px; color: #36527f; font-size: 13px; }
.weights-title { font-weight: 700; margin-bottom: 8px; color: #264181; }
.weights-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 10px 16px;
  align-items: end;
}
.w-item { display: flex; gap: 10px; align-items: center; }
.w-label { width: 140px; color: #334c7a; font-weight: 600; }
.w-sum { grid-column: 1 / -1; color: #2e4775; }

.recommend {
  padding: 10px 12px;
  border: 1px dashed #c7d9ff;
  border-radius: 10px;
  background: #f7fbff;
}
.recommend-title { font-weight: 700; margin-bottom: 6px; color: #21407c; }
.recommend-body { line-height: 1.6; color: #263a67; }
.empty { margin-top: 12px; color: #5f7098; }

:deep(.el-table) {
  --el-table-text-color: #243965;
  --el-table-header-text-color: #23478f;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px #c9d8ff inset;
}

:deep(.el-checkbox__label) {
  color: #2d4574;
}
</style>
