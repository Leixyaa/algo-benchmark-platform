<template>
  <div class="page">
    <div class="header-section">
      <div class="header-left">
        <h2 class="page-title">平台算法智能推荐</h2>
        <p class="page-subtitle">面向平台标准算法库的多维指标分析与 LinUCB 智能推荐，支持对比展示与结论导出</p>
      </div>
        <div class="header-right">
          <el-button-group>
            <el-button icon="Refresh" @click="store.fetchRuns()" :disabled="!store.user.isLoggedIn">同步数据</el-button>
            <el-button type="danger" plain icon="Delete" @click="resetAllConfig" :disabled="!store.user.isLoggedIn">重置配置</el-button>
          </el-button-group>
        </div>
      </div>

    <div class="config-grid">
      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header-small"><el-icon><Filter /></el-icon> 结果筛选</div>
        </template>
        <div class="filter-form">
          <div class="filter-row">
            <el-select v-model="task" placeholder="任务类型" class="flex-1">
              <el-option v-for="t in taskOptions" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="datasetId" placeholder="评测数据集" class="flex-1">
              <el-option v-for="d in store.datasets" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </div>
          <div class="filter-row-secondary">
            <el-checkbox v-model="onlyDone">仅显示已完成</el-checkbox>
            <el-button link type="primary" @click="reset">重置全部条件</el-button>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header-small">
            <el-icon><Compass /></el-icon> 评分权重
            <div class="preset-links">
              <el-link type="primary" :underline="false" @click="presetQuality">质量优先</el-link>
              <el-divider direction="vertical" />
              <el-link type="primary" :underline="false" @click="presetBalanced">均衡</el-link>
              <el-divider direction="vertical" />
              <el-link type="primary" :underline="false" @click="presetSpeed">速度优先</el-link>
            </div>
          </div>
        </template>
        <div class="weight-inputs">
          <div class="weight-item">
            <span class="w-label">PSNR</span>
            <el-input-number v-model="wPSNR" :min="0" :max="10" :step="0.1" size="small" controls-position="right" />
          </div>
          <div class="weight-item">
            <span class="w-label">SSIM</span>
            <el-input-number v-model="wSSIM" :min="0" :max="10" :step="0.1" size="small" controls-position="right" />
          </div>
          <div class="weight-item">
            <span class="w-label">NIQE</span>
            <el-input-number v-model="wNIQE" :min="0" :max="10" :step="0.1" size="small" controls-position="right" />
          </div>
          <div class="weight-item">
            <span class="w-label">TIME</span>
            <el-input-number v-model="wTIME" :min="0" :max="10" :step="0.1" size="small" controls-position="right" />
          </div>
        </div>
        <div class="weight-footer">
          <span class="w-sum">权重总和: <strong>{{ weightSum.toFixed(2) }}</strong></span>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="tool-card">
      <div class="tool-tabs">
        <div class="tool-section">
          <div class="tool-title"><el-icon><Cpu /></el-icon> 平台算法智能推荐（LinUCB）</div>
          <div class="tool-actions">
            <span class="tool-label">Top-K</span>
            <el-input-number v-model="fastTopK" :min="1" :max="10" size="small" :disabled="!store.user.isLoggedIn" />
            <span class="tool-label">探索系数</span>
            <el-input-number v-model="fastAlpha" :min="0" :max="2" :step="0.1" size="small" :disabled="!store.user.isLoggedIn" />
            <el-button type="primary" icon="MagicStick" :loading="fastLoading" @click="runFastSelect" :disabled="!store.user.isLoggedIn">分析平台推荐</el-button>
            <el-button type="warning" plain icon="VideoPlay" :disabled="!store.user.isLoggedIn || !fastRecommendations.length" @click="createRunsByFastSelect">按推荐创建平台任务</el-button>
          </div>
        </div>
        <el-divider direction="vertical" />
        <div class="tool-section">
          <div class="tool-title"><el-icon><List /></el-icon> 批量基线</div>
          <div class="tool-actions">
            <el-select v-model="bulkParamScheme" size="small" style="width: 100px" :disabled="!store.user.isLoggedIn">
              <el-option label="默认" value="default" />
              <el-option label="速度" value="speed" />
              <el-option label="质量" value="quality" />
            </el-select>
            <el-button type="warning" icon="Files" :disabled="!store.user.isLoggedIn || bulkRunning" @click="bulkRunBaselines">批量运行</el-button>
          </div>
        </div>
      </div>

      <div v-if="fastRecommendations.length" class="fast-res-container">
        <el-table :data="fastRecommendations" size="small" class="mini-table">
          <el-table-column label="推荐排名" width="80" align="center">
            <template #default="{ $index }">
              <span class="rank-badge" :class="'rank-' + ($index + 1)">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="algorithm_name" label="推荐算法" />
          <el-table-column prop="algorithm_scope" label="算法范围" width="110" align="center" />
          <el-table-column prop="score" label="UCB 得分" width="100" />
          <el-table-column prop="mean_reward" label="历史均值" width="100" />
          <el-table-column prop="sample_count" label="样本数" width="80" />
        </el-table>
        <div class="fast-meta" v-if="fastContext">
          基于 {{ fastContext.historical_run_count }} 组历史数据分析，当前 alpha={{ fastContext.alpha }}，候选范围：平台标准算法库
        </div>
        <div v-if="recommendationDifferenceText" class="fast-note">
          {{ recommendationDifferenceText }}
        </div>
      </div>
    </el-card>

    <div class="results-layout">
      <div class="recommendation-panel" v-if="bestResultRow">
        <div class="recommend-card">
          <div class="recommend-badge">当前真实评测最优</div>
          <div class="recommend-content">
            <h3 class="rec-algo">{{ bestResultRow?.algorithmName }}</h3>
            <p class="rec-reason">{{ bestResultSummary }}</p>
            <div class="rec-metrics">
              <div class="rec-m-item">PSNR <span>{{ bestResultRow?.psnr }}</span></div>
              <div class="rec-m-item">SSIM <span>{{ bestResultRow?.ssim }}</span></div>
              <div class="rec-m-item">NIQE <span>{{ bestResultRow?.niqe }}</span></div>
              <div class="rec-m-item score">综合评分 <span>{{ bestResultRow?.score }}</span></div>
            </div>
          </div>
          <div class="export-actions">
            <el-dropdown split-button type="success" @click="exportConclusionMd" :disabled="!store.user.isLoggedIn">
              导出对比结论
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="exportRecommendXlsx" :disabled="!store.user.isLoggedIn">导出对比 Excel</el-dropdown-item>
                  <el-dropdown-item @click="exportRecommendCsv" :disabled="!store.user.isLoggedIn">导出对比 CSV</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>

      <el-card shadow="never" class="chart-card-wrapper" v-if="chartItems.length">
        <template #header>
          <div class="chart-header">
            <div class="chart-title-box">
              <el-icon><Histogram /></el-icon>
              <span>指标排行榜（Top {{ chartTopN }}）</span>
            </div>
            <div class="chart-controls">
              <el-radio-group v-model="chartMetric" size="small" class="metric-radio" :disabled="!store.user.isLoggedIn">
                <el-radio-button label="score">评分</el-radio-button>
                <el-radio-button label="psnr">PSNR</el-radio-button>
                <el-radio-button label="ssim">SSIM</el-radio-button>
                <el-radio-button label="niqe">NIQE</el-radio-button>
                <el-radio-button label="time">耗时</el-radio-button>
              </el-radio-group>
              <el-button size="small" icon="Camera" @click="exportChartPng" :disabled="!store.user.isLoggedIn">导出图表</el-button>
            </div>
          </div>
        </template>
        <div class="chart-container">
          <canvas ref="chartCanvas" class="main-canvas" @mousemove="onChartMove" @mouseleave="onChartLeave"></canvas>
          <div v-if="chartTip.visible" class="canvas-tooltip" :style="{ left: chartTip.x + 'px', top: chartTip.y + 'px' }">
            {{ chartTip.text }}
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="table-card-wrapper">
        <template #header>
          <div class="table-header">
            <span class="table-title">对比明细清单</span>
            <div class="table-actions">
              <el-button size="small" icon="Download" @click="exportXlsx" :disabled="!store.user.isLoggedIn">原始数据 Excel</el-button>
            </div>
          </div>
        </template>
        <el-table :data="tableRows" stripe class="compare-table" height="500">
          <el-table-column prop="algorithmName" label="算法名称" min-width="150" fixed="left" />
          <el-table-column prop="score" label="综合分" width="100" sortable align="center">
            <template #default="{ row }">
              <span class="table-score">{{ row.score > -Infinity ? row.score : '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="psnr" label="PSNR" width="90" align="center" />
          <el-table-column prop="ssim" label="SSIM" width="90" align="center" />
          <el-table-column prop="niqe" label="NIQE" width="90" align="center" />
          <el-table-column prop="elapsed" label="耗时" width="90" align="center" />
          <el-table-column label="推荐分析" min-width="250">
            <template #default="{ row }">
              <span class="table-reason">{{ row.reason || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="运行时间" width="160" />
        </el-table>
        <div v-if="tableRows.length === 0" class="empty-state">
          <el-empty description="暂无符合条件的对比结果" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useAppStore } from "../stores/app";
import { toTaskType } from "../stores/app";
import { ElMessage, ElMessageBox } from "element-plus";
import { authFetch } from "../api/http";
import * as XLSX from "xlsx";

const store = useAppStore();
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001";

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

function resetAllConfig() {
  reset();
  chartMetric.value = "score";
  chartTopN.value = 10;
  fastRecommendations.value = [];
  fastContext.value = null;
  clearCache();
  saveCache();
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
  if (store.user.isLoggedIn && (!store.runs || store.runs.length === 0)) {
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
  const s = String(status ?? "").trim().toLowerCase();
  if (["done", "completed", "success", "已完成"].includes(s)) return "已完成";
  if (["running", "运行中"].includes(s)) return "运行中";
  if (["failed", "error", "失败"].includes(s)) return "失败";
  if (["queued", "pending", "排队中"].includes(s)) return "排队中";
  if (["canceling", "cancelling", "取消中"].includes(s)) return "取消中";
  if (["canceled", "cancelled", "已取消"].includes(s)) return "已取消";
  return status || "-";
}

function isDone(status) {
  return statusText(status) === "已完成";
}

function statusTagType(status) {
  const text = statusText(status);
  if (text === "已完成") return "success";
  if (text === "运行中") return "warning";
  if (text === "失败") return "danger";
  if (text === "排队中") return "info";
  if (text === "取消中") return "warning";
  if (text === "已取消") return "info";
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

function getRunDataMode(run) {
  return String(run?.raw?.params?.data_mode || run?.raw?.record?.data_mode || "").trim();
}

function isRealComparableRun(run) {
  const mode = getRunDataMode(run);
  return mode === "real_dataset" || mode === "paired_images" || mode === "paired_videos";
}

function compareAuthenticityLabel(run) {
  const mode = getRunDataMode(run);
  if (mode === "real_dataset") return "真实数据评测";
  if (mode === "paired_images") return "真实图像配对";
  if (mode === "paired_videos") return "真实视频配对";
  if (mode === "synthetic_no_dataset") return "演示兜底结果";
  if (mode === "dataset_read_failed_or_empty") return "读取失败兜底";
  return "执行口径未标注";
}

function matchesTask(runOrAlg, taskLabel, taskType) {
  const rawTask = String(runOrAlg?.task || "").trim();
  const rawTaskType = String(runOrAlg?.taskType || "").trim();
  return rawTask === taskLabel || rawTask === taskType || rawTaskType === taskType;
}

function getDatasetSupportInfo(dsId, taskType) {
  const ds = (store.datasets || []).find((x) => String(x?.id || "") === String(dsId || ""));
  const meta = ds?.raw?.meta && typeof ds.raw.meta === "object" ? ds.raw.meta : {};
  const supported = Array.isArray(meta?.supported_task_types) ? meta.supported_task_types.map((x) => String(x || "")) : [];
  const pairsByTask = meta?.pairs_by_task && typeof meta.pairs_by_task === "object" ? meta.pairs_by_task : {};
  const pairCount = Number(pairsByTask?.[taskType] ?? 0);
  const supportedByList = supported.includes(taskType);
  return {
    ok: supportedByList || pairCount > 0,
    pairCount,
    datasetName: ds?.name || dsId || "-",
  };
}

function isPlatformAlgorithm(alg) {
  return String(alg?.uploaderId || "") === "system";
}

const HIDDEN_PLATFORM_ALGORITHM_IDS = new Set([
  "alg_dn_cnn_light",
  "alg_dn_cnn_strong",
  "alg_denoise_bilateral_soft",
  "alg_denoise_bilateral_strong",
  "alg_denoise_gaussian_light",
  "alg_denoise_gaussian_strong",
  "alg_denoise_median_light",
  "alg_denoise_median_strong",
  "alg_dehaze_dcp_fast",
  "alg_dehaze_dcp_strong",
  "alg_dehaze_clahe_mild",
  "alg_dehaze_clahe_strong",
  "alg_dehaze_gamma_mild",
  "alg_dehaze_gamma_strong",
  "alg_deblur_unsharp_light",
  "alg_deblur_unsharp_strong",
  "alg_deblur_laplacian_light",
  "alg_deblur_laplacian_strong",
  "alg_sr_nearest",
  "alg_sr_linear",
  "alg_sr_bicubic_sharp",
  "alg_sr_lanczos_sharp",
  "alg_lowlight_gamma_soft",
  "alg_lowlight_gamma_strong",
  "alg_lowlight_clahe_soft",
  "alg_lowlight_clahe_strong",
  "alg_video_denoise_gaussian_light",
  "alg_video_denoise_gaussian_strong",
  "alg_video_denoise_median_light",
  "alg_video_denoise_median_strong",
  "alg_video_sr_nearest",
  "alg_video_sr_linear",
  "alg_video_sr_bicubic_sharp",
  "alg_video_sr_lanczos_sharp",
]);

function isVisiblePlatformAlgorithm(alg) {
  if (!isPlatformAlgorithm(alg)) return false;
  if (alg?.raw?.is_active === false) return false;
  const hasCommunitySource = String(alg?.sourceUploaderId || "").trim() || String(alg?.sourceAlgorithmId || "").trim();
  if (hasCommunitySource) return true;
  return !HIDDEN_PLATFORM_ALGORITHM_IDS.has(String(alg?.id || ""));
}

function getPlatformAlgorithmsForTask(taskLabel, taskType) {
  return (store.algorithms || []).filter(
    (a) => isVisiblePlatformAlgorithm(a) && matchesTask(a, taskLabel, taskType)
  );
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
  denoise: [
    "alg_dn_cnn", "alg_dn_cnn_light", "alg_dn_cnn_strong",
    "alg_denoise_bilateral", "alg_denoise_bilateral_soft", "alg_denoise_bilateral_strong",
    "alg_denoise_gaussian", "alg_denoise_gaussian_light", "alg_denoise_gaussian_strong",
    "alg_denoise_median", "alg_denoise_median_light", "alg_denoise_median_strong",
  ],
  dehaze: [
    "alg_dehaze_dcp", "alg_dehaze_dcp_fast", "alg_dehaze_dcp_strong",
    "alg_dehaze_clahe", "alg_dehaze_clahe_mild", "alg_dehaze_clahe_strong",
    "alg_dehaze_gamma", "alg_dehaze_gamma_mild", "alg_dehaze_gamma_strong",
  ],
  deblur: [
    "alg_deblur_unsharp", "alg_deblur_unsharp_light", "alg_deblur_unsharp_strong",
    "alg_deblur_laplacian", "alg_deblur_laplacian_light", "alg_deblur_laplacian_strong",
  ],
  sr: [
    "alg_sr_nearest", "alg_sr_linear", "alg_sr_bicubic",
    "alg_sr_bicubic_sharp", "alg_sr_lanczos", "alg_sr_lanczos_sharp",
  ],
  lowlight: [
    "alg_lowlight_gamma", "alg_lowlight_gamma_soft", "alg_lowlight_gamma_strong",
    "alg_lowlight_clahe", "alg_lowlight_clahe_soft", "alg_lowlight_clahe_strong",
    "alg_lowlight_hybrid",
  ],
  video_denoise: [
    "alg_video_denoise_gaussian", "alg_video_denoise_gaussian_light", "alg_video_denoise_gaussian_strong",
    "alg_video_denoise_median", "alg_video_denoise_median_light", "alg_video_denoise_median_strong",
  ],
  video_sr: [
    "alg_video_sr_nearest", "alg_video_sr_linear", "alg_video_sr_bicubic",
    "alg_video_sr_bicubic_sharp", "alg_video_sr_lanczos", "alg_video_sr_lanczos_sharp",
  ],
};

const BASELINE_ID_SET = new Set(Object.values(BASELINE_IDS_BY_TASK_TYPE).flat());

function isBaselineAlgorithmId(algorithmId) {
  return BASELINE_ID_SET.has(String(algorithmId || ""));
}

function normalizeRunParams(params) {
  const src = params && typeof params === "object" && !Array.isArray(params) ? params : {};
  const out = {};
  const ignoreKeys = new Set([
    "batch_id",
    "batch_name",
    "source",
    "fast_top_k",
    "fast_alpha",
    "metrics",
    "real_algo",
    "data_mode",
    "data_used",
    "read_ok",
    "read_fail",
    "input_dir",
    "pair_total",
    "pair_used",
    "algo_elapsed_mean",
    "algo_elapsed_sum",
    "metric_elapsed_mean",
    "metric_elapsed_sum",
    "metric_psnr_ssim_elapsed_mean",
    "metric_psnr_ssim_elapsed_sum",
    "metric_niqe_elapsed_mean",
    "metric_niqe_elapsed_sum",
    "niqe_fallback",
  ]);
  for (const [key, value] of Object.entries(src)) {
    if (ignoreKeys.has(key)) continue;
    out[key] = value;
  }
  return out;
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function buildRunFingerprint(taskType, datasetIdValue, algorithmId, params = {}) {
  const normalized = normalizeRunParams(params);
  return `${taskType}|${datasetIdValue}|${algorithmId}|${stableStringify(normalized)}`;
}

function existingRunFingerprints() {
  return new Set(
    (store.runs || []).map((r) =>
      buildRunFingerprint(r?.taskType || "", r?.datasetId || "", r?.algorithmId || "", r?.raw?.params || {})
    )
  );
}


function mapTaskLabelToType(label) {
  return toTaskType(label || "");
}



function buildExportQuery(fmt) {
  const params = new URLSearchParams();
  params.set("format", fmt);

  if (onlyDone.value) params.set("status", "done");
  if (task.value) params.set("task_type", mapTaskLabelToType(task.value));
  if (datasetId.value) params.set("dataset_id", datasetId.value);

  return params.toString();
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
    "执行口径": compareAuthenticityLabel(r),
    "data_mode": getRunDataMode(r),
    "状态": statusText(r.status),
    "PSNR": r.psnr ?? "",
    "SSIM": r.ssim ?? "",
    "NIQE": r.niqe ?? "",
    "耗时": r.elapsed ?? "",
    "综合分": Number.isFinite(r.score) ? r.score : "",
    "实际算法": r.raw?.params?.real_algo ?? "",
    "样本数": r.raw?.params?.data_used ?? "",
    "读取成功": r.raw?.params?.read_ok ?? "",
    "读取失败": r.raw?.params?.read_fail ?? "",
    "推荐理由/备注": r.reason ?? "",
    "RunID": r.id ?? "",
  }));
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

  if (task.value) {
    const taskType = mapTaskLabelToType(task.value);
    runs = runs.filter((r) => matchesTask(r, task.value, taskType));
  }
  if (datasetId.value) runs = runs.filter((r) => r.datasetId === datasetId.value);
  if (onlyDone.value) runs = runs.filter((r) => isDone(r.status));
  runs = runs.filter((r) => isRealComparableRun(r));

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

      if (r1 === 1) parts.push("PSNR 表现最佳");
      else if (r1 === 2) parts.push("PSNR 表现靠前");
      if (r2 === 1) parts.push("SSIM 表现最佳");
      else if (r2 === 2) parts.push("SSIM 表现靠前");
      if (r3 === 1) parts.push("NIQE 表现最佳（越低越好）");
      else if (r3 === 2) parts.push("NIQE 表现靠前");
      if (r4 === 1) parts.push("耗时表现最佳");
      else if (r4 === 2) parts.push("耗时表现靠前");

      if (parts.length === 0) {
        parts.push("综合表现均衡");
      }

      const main = [
        { k: "PSNR", w: W.psnr },
        { k: "SSIM", w: W.ssim },
        { k: "NIQE", w: W.niqe },
        { k: "耗时", w: W.time },
      ].sort((a, b) => b.w - a.w);

      reason = `${parts.join("，")}；主要权重为 ${main[0].k}(${(main[0].w * 100).toFixed(
        0
      )}%) 和 ${main[1].k}(${(main[1].w * 100).toFixed(0)}%)`;
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

const bestResultRow = computed(() => (tableRows.value.length ? tableRows.value[0] : null));

const bestResultSummary = computed(() => {
  const top = bestResultRow.value;
  if (!top) return "";
  return `这是当前筛选条件下基于真实评测结果计算得到的综合最优方案。${top.reason ? ` ${top.reason}` : ""}`;
});

const recommendationDifferenceText = computed(() => {
  const fastTop = fastRecommendations.value?.[0];
  const best = bestResultRow.value;
  if (!fastTop || !best) return "";
  if (String(fastTop.algorithm_name || "") === String(best.algorithmName || "")) {
    return "当前平台算法推荐第一与真实评测最优一致。";
  }
  return `当前平台算法推荐第一为 ${fastTop.algorithm_name}，但当前真实评测最优为 ${best.algorithmName}。前者基于历史反馈与探索项，后者基于当前真实评测综合结果。`;
});

const recommendText = computed(() => {
  if (tableRows.value.length === 0) return "";
  const top = tableRows.value[0];
  if (!Number.isFinite(top.score)) return "";

  return [
    `推荐算法：${top.algorithmName}`,
    `推荐理由：${top.reason}`,
    `结论口径：${compareAuthenticityLabel(top)}`,
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
  const useUnitScale = chartMetric.value === "score" || chartMetric.value === "ssim";
  const maxV = useUnitScale ? 1 : values.length ? Math.max(...values) : 1;
  const minV = useUnitScale ? 0 : values.length ? Math.min(...values) : 0;
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
    const txt = useUnitScale ? v.toFixed(2) : chartMetric.value === "ssim" ? v.toFixed(3) : v.toFixed(2);
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
    const clamped = Math.max(minV, Math.min(maxV, v));
    const nv = (clamped - minV) / span;
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
    time: "耗时",
  };
  const extra = chartMetric.value === "score" ? "（0~1，越高越好）" : "";
  ctx.fillText(`图表指标：${titleMap[chartMetric.value] || chartMetric.value}${extra}`, padL, 0);
}

watch([tableRows, chartMetric, chartTopN], async () => {
  await nextTick();
  drawChart();
});

onMounted(async () => {
  await nextTick();
  drawChart();
});

async function bulkRunBaselines() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel) return ElMessage.warning("请先选择任务类型");
  if (!dsId) return ElMessage.warning("请先选择数据集");

  const taskType = mapTaskLabelToType(taskLabel);
  if (!taskType) return ElMessage.error("当前任务类型无法映射到 task_type");
  const support = getDatasetSupportInfo(dsId, taskType);
  if (!support.ok) {
    return ElMessage.warning(`数据集“${support.datasetName}”当前未扫描出任务“${taskLabel}”可用配对，建议先回到数据集页扫描确认`);
  }

  const baselineIdSet = new Set(BASELINE_IDS_BY_TASK_TYPE[taskType] || []);
  let algs = (store.algorithms || []).filter((a) => matchesTask(a, taskLabel, taskType));
  if (bulkOnlyBaselines.value) {
    algs = algs.filter((a) => baselineIdSet.has(a.id));
  }
  if (!algs.length) return ElMessage.warning("当前任务没有可创建的算法");

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const batchId = `batch_${taskType}_${dsId}_${ts}_${Math.random().toString(16).slice(2, 6)}`;
  const batchName = `${taskLabel}-${dsId}-${bulkParamScheme.value}-${ts}`;

  try {
    await ElMessageBox.confirm(
      `将为任务“${taskLabel}”、数据集“${dsId}”创建 ${algs.length} 个 Run。\n参数方案：${bulkParamScheme.value}；严格校验：${bulkStrictValidate.value ? "开启" : "关闭"}；仅基线：${bulkOnlyBaselines.value ? "是" : "否"}。\n批次 ID：${batchId}`,
      "批量运行确认",
      { type: "warning", confirmButtonText: "开始创建", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }

  task.value = taskLabel;
  datasetId.value = dsId;

  if (bulkRunning.value) return;
  bulkRunning.value = true;
  const failed = [];
  const skipped = [];
  const created = [];
  const existing = existingRunFingerprints();

  for (const a of algs) {
    try {
      const params = {};
      const scheme = bulkParamScheme.value;
      const algDefault =
        a?.defaultParams && typeof a.defaultParams === "object" && !Array.isArray(a.defaultParams) ? a.defaultParams : {};
      const algPresets =
        a?.paramPresets && typeof a.paramPresets === "object" && !Array.isArray(a.paramPresets) ? a.paramPresets : {};
      const picked =
        scheme === "speed" || scheme === "quality"
          ? algPresets?.[scheme] && typeof algPresets[scheme] === "object"
            ? algPresets[scheme]
            : {}
          : algDefault;
      Object.assign(params, picked);
      params.batch_id = batchId;
      params.batch_name = batchName;
      params.param_scheme = scheme;

      const fingerprint = buildRunFingerprint(taskType, dsId, a.id, params);
      if (existing.has(fingerprint)) {
        skipped.push(`${a?.name || a?.id}`);
        continue;
      }

      await store.createRun({
        task: taskLabel,
        datasetId: dsId,
        algorithmId: a.id,
        metrics: ["PSNR", "SSIM", "NIQE"],
        params,
        strictValidate: bulkStrictValidate.value,
      });
      existing.add(fingerprint);
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
  if (failed.length) {
    await ElMessageBox.alert(`${parts.join("，")}\n\n失败详情：\n${failed.join("\n")}`, "批量运行结果", { type: "error" });
    return;
  }
  ElMessage.success(`${parts.join("，")}，批次 ID：${batchId}`);
}

async function runFastSelect() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel) return ElMessage.warning("请先选择任务类型");
  if (!dsId) return ElMessage.warning("请先选择数据集");
  const taskType = mapTaskLabelToType(taskLabel);
  if (!taskType) return ElMessage.error("当前任务类型无法映射到 task_type");
  const support = getDatasetSupportInfo(dsId, taskType);
  if (!support.ok) {
    return ElMessage.warning(`数据集“${support.datasetName}”当前未扫描出任务“${taskLabel}”可用配对，无法进行正式推荐`);
  }

  const algs = getPlatformAlgorithmsForTask(taskLabel, taskType);
  if (!algs.length) return ElMessage.warning("当前任务下暂无可推荐的平台算法");

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
        algorithm_scope: "平台算法",
        score: Number(x?.score ?? 0).toFixed(4),
        mean_reward: Number(x?.mean_reward ?? 0).toFixed(4),
        uncertainty: Number(x?.uncertainty ?? 0).toFixed(4),
        sample_count: Number(x?.sample_count ?? 0),
      };
    });
    fastContext.value = out?.context && typeof out.context === "object" ? out.context : null;
    if (!fastRecommendations.value.length) {
      ElMessage.warning("平台算法推荐已执行，但当前没有返回推荐结果");
    }
  } catch (e) {
    fastRecommendations.value = [];
    fastContext.value = null;
    ElMessage.error(`平台算法推荐失败：${e?.message || e}`);
  } finally {
    fastLoading.value = false;
  }
}

async function createRunsByFastSelect() {
  const taskLabel = task.value || taskOptions.value?.[0] || "";
  const dsId = datasetId.value || store.datasets?.[0]?.id || "";
  if (!taskLabel || !dsId) return ElMessage.warning("请先选择任务和数据集");
  if (!fastRecommendations.value.length) return ElMessage.warning("请先执行平台算法推荐");
  if (fastCreateRunning.value) return;

  const taskType = mapTaskLabelToType(taskLabel);
  const support = getDatasetSupportInfo(dsId, taskType);
  if (!support.ok) {
    return ElMessage.warning(`数据集“${support.datasetName}”当前未扫描出任务“${taskLabel}”可用配对，无法创建正式推荐任务`);
  }
  await store.fetchRuns().catch(() => {});
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const batchId = `batch_fast_${taskType}_${dsId}_${ts}_${Math.random().toString(16).slice(2, 6)}`;
    const batchName = `platform-recommend-${taskLabel}-${dsId}-${ts}`;
  const existing = existingRunFingerprints();

  fastCreateRunning.value = true;
  const failed = [];
  let skipped = 0;
  let created = 0;
  for (const rec of fastRecommendations.value) {
    const aid = rec.algorithm_id;
    const params = {
      batch_id: batchId,
      batch_name: batchName,
      source: "fast_select",
      fast_top_k: fastTopK.value,
      fast_alpha: fastAlpha.value,
    };
    const fingerprint = buildRunFingerprint(taskType, dsId, aid, params);
    if (existing.has(fingerprint)) {
      skipped += 1;
      continue;
    }
    try {
      await store.createRun({
        task: taskLabel,
        datasetId: dsId,
        algorithmId: aid,
        metrics: ["PSNR", "SSIM", "NIQE"],
        params,
        strictValidate: bulkStrictValidate.value,
      });
      existing.add(fingerprint);
      created += 1;
    } catch (e) {
      failed.push(`${aid}: ${e?.message || e}`);
    }
  }
  fastCreateRunning.value = false;
  if (failed.length) {
    await ElMessageBox.alert(`已创建 ${created} 个平台推荐 Run，跳过重复 ${skipped} 个，失败 ${failed.length} 个。\n\n${failed.join("\n")}`, "平台推荐创建结果", {
      type: "error",
    });
    return;
  }
  ElMessage.success(`已按平台推荐结果创建 ${created} 个 Run，跳过重复 ${skipped} 个，批次 ID：${batchId}`);
}

async function exportRawRuns(fmt, filename) {
  const res = await authFetch(`/runs/export?${buildExportQuery(fmt)}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `导出失败(${res.status})`);
  }
  const blob = await res.blob();
  downloadBlob(blob, filename);
}

async function exportCsv() {
  try {
    await exportRawRuns("csv", "runs_export.csv");
  } catch (e) {
    ElMessage.error(`导出失败：${e?.message || e}`);
  }
}

async function exportXlsx() {
  try {
    await exportRawRuns("xlsx", "runs_export.xlsx");
  } catch (e) {
    ElMessage.error(`导出失败：${e?.message || e}`);
  }
}

function exportRecommendCsv() {
  const rows = buildExportRows();
  if (!rows.length) return ElMessage.warning("当前没有可导出的推荐结果");

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
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadBlob(blob, `compare_recommend_${ts}.csv`);
}

function exportRecommendXlsx() {
  const rows = buildExportRows();
  if (!rows.length) return ElMessage.warning("当前没有可导出的推荐结果");

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
  const rows = buildExportRows();
  if (!rows.length) return ElMessage.warning("当前没有可导出的推荐结果");

  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const mdLines = [];
  mdLines.push(`# 对比推荐结论 ${ts}`);
  mdLines.push("");
  mdLines.push(`- 任务：${task.value || "-"}`);
  mdLines.push(`- 数据集：${datasetId.value || "-"}`);
  mdLines.push(`- 仅已完成：${onlyDone.value ? "是" : "否"}`);
  mdLines.push(`- 推荐口径：仅纳入真实配对数据评测结果（已排除演示兜底与读取失败兜底）`);
  mdLines.push(`- 说明：平台算法推荐结果反映历史反馈推荐；当前真实评测最优反映本次筛选结果，两者允许不完全一致。`);
  mdLines.push(`- 权重：PSNR=${wPSNR.value}，SSIM=${wSSIM.value}，NIQE=${wNIQE.value}，耗时=${wTIME.value}`);
  mdLines.push("");
  if (fastRecommendations.value.length) {
    mdLines.push("## 平台算法推荐结果");
    for (const [i, item] of fastRecommendations.value.entries()) {
      mdLines.push(`${i + 1}. ${item.algorithm_name}（${item.algorithm_scope}，UCB=${item.score}，样本数=${item.sample_count}）`);
    }
    mdLines.push("");
  }
  if (bestResultRow.value) {
    mdLines.push("## 当前真实评测最优");
    mdLines.push(`${bestResultRow.value.algorithmName}：${bestResultSummary.value}`);
    mdLines.push("");
  }
  if (recommendText.value) {
    mdLines.push("## 平台推荐说明");
    mdLines.push(recommendText.value);
    mdLines.push("");
  }
  mdLines.push("## 对比结果明细");
  mdLines.push("");
  const headers = Object.keys(rows[0]);
  mdLines.push(`| ${headers.join(" | ")} |`);
  mdLines.push(`| ${headers.map(() => "---").join(" | ")} |`);
  for (const row of rows) {
    mdLines.push(`| ${headers.map((h) => String(row[h] ?? "").replace(/\|/g, "\\|")).join(" | ")} |`);
  }
  const blob = new Blob([mdLines.join("\n")], { type: "text/markdown;charset=utf-8;" });
  downloadBlob(blob, `compare_conclusion_${ts}.md`);
}

function exportChartPng() {
  const c = chartCanvas.value;
  if (!c) return ElMessage.warning("当前没有可导出的图表画布");
  const dataUrl = c.toDataURL("image/png");
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadDataUrl(dataUrl, `compare_chart_${chartMetric.value}_${ts}.png`);
}
</script>

<style scoped>
.page {
  padding: 24px;
  background-color: #f5f7fb;
  min-height: 100%;
}

/* Header */
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1a2f62;
}

.page-subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 14px;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.config-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.card-header-small {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #475569;
}

.filter-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-row {
  display: flex;
  gap: 12px;
}

.flex-1 { flex: 1; }

.filter-row-secondary {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preset-links {
  margin-left: auto;
  font-weight: normal;
}

.weight-inputs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.weight-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 8px;
}

.w-label { font-size: 12px; color: #64748b; font-weight: 600; }

.weight-footer {
  margin-top: 12px;
  text-align: right;
  font-size: 13px;
  color: #64748b;
}

/* Tool Card */
.tool-card {
  margin-bottom: 20px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.tool-tabs {
  display: flex;
  align-items: center;
  gap: 20px;
}

.tool-section {
  flex: 1;
}

.tool-title {
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tool-label { font-size: 12px; color: #94a3b8; }

.tool-actions :deep(.el-checkbox) {
  margin-right: 2px;
}

.fast-res-container {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.mini-table {
  border: 1px solid #f1f5f9;
  border-radius: 8px;
}

.rank-badge {
  display: inline-block;
  width: 20px;
  height: 20px;
  line-height: 20px;
  border-radius: 4px;
  background: #f1f5f9;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.rank-1 { background: #fef3c7; color: #92400e; }
.rank-2 { background: #e2e8f0; color: #475569; }

.fast-meta {
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
}

.fast-note {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}

/* Results Layout */
.results-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.recommendation-panel {
  width: 100%;
}

.recommend-card {
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  padding: 24px;
  color: #1f2937;
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.recommend-badge {
  position: absolute;
  top: 0;
  left: 0;
  background: #2f6bff;
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 12px;
  border-bottom-right-radius: 12px;
  text-transform: uppercase;
}

.rec-algo {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
}

.rec-reason {
  margin: 8px 0 16px;
  font-size: 14px;
  color: #64748b;
  max-width: 600px;
}

.rec-metrics {
  display: flex;
  gap: 20px;
}

.rec-m-item {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: #64748b;
}

.rec-m-item span {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
  margin-top: 4px;
}

.rec-m-item.score span {
  color: #2f6bff;
}

/* Chart */
.chart-card-wrapper {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #1e293b;
}

.chart-controls {
  display: flex;
  gap: 16px;
  align-items: center;
}

.chart-container {
  position: relative;
  width: 100%;
  padding: 10px 0;
}

.main-canvas {
  width: 100%;
  height: 320px;
  cursor: crosshair;
}

.canvas-tooltip {
  position: absolute;
  background: rgba(15, 23, 42, 0.9);
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  pointer-events: none;
  z-index: 10;
  white-space: nowrap;
}

/* Table */
.table-card-wrapper {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-title { font-weight: 700; color: #1e293b; }

.table-score {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #2563eb;
}

.table-reason {
  font-size: 13px;
  color: #64748b;
  line-height: 1.4;
}

.empty-state {
  padding: 40px 0;
}

:deep(.el-card__header) {
  padding: 12px 20px;
  background-color: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 8px;
}

@media (max-width: 1024px) {
  .config-grid { grid-template-columns: 1fr; }
  .recommend-card { flex-direction: column; align-items: flex-start; gap: 20px; }
  .export-actions { width: 100%; }
}
</style>
