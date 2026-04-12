<template>
  <div class="page">
    <section class="hero-panel">
      <div class="hero-copy">
        <div class="hero-kicker">Platform Compare</div>
        <h2 class="page-title">平台算法对比分析</h2>
        <p class="page-subtitle">围绕真实评测结果做筛选、排序、导出与结论整理，保留统一口径的指标对比，不再提供智能选型入口。</p>
        <div class="hero-meta">
          <div class="meta-pill">
            <span class="meta-label">当前任务</span>
            <strong>{{ selectedTaskSummary }}</strong>
          </div>
          <div class="meta-pill">
            <span class="meta-label">当前数据集</span>
            <strong>{{ selectedDatasetSummary }}</strong>
          </div>
          <div class="meta-pill">
            <span class="meta-label">排序方式</span>
            <strong>{{ selectedRankMetricLabel }}</strong>
          </div>
          <div class="meta-pill">
            <span class="meta-label">真实结果</span>
            <strong>{{ tableRows.length }} 条</strong>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <el-button class="soft-btn" @click="refreshAll" :disabled="!store.user.isLoggedIn">同步数据</el-button>
        <el-button class="danger-soft-btn" @click="resetAllConfig" :disabled="!store.user.isLoggedIn">重置配置</el-button>
      </div>
    </section>

    <div class="config-grid">
      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">Filter</div>
              <div class="card-title">结果筛选</div>
            </div>
            <p class="card-desc">先选择任务、数据集和排序口径，再看推荐结论会更清晰。</p>
          </div>
        </template>
        <div class="filter-form">
          <el-select v-model="task" placeholder="任务类型" class="flex-item">
            <el-option v-for="item in taskOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="datasetId" placeholder="评测数据集" class="flex-item">
            <el-option v-for="item in store.datasets" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-select v-model="chartMetric" placeholder="排序方式" class="flex-item">
            <el-option v-for="item in availableRankMetrics" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <div class="filter-row-secondary">
            <el-checkbox v-model="onlyDone">仅显示已完成</el-checkbox>
            <div class="filter-footer-actions">
              <span class="inline-tip">当前满足筛选条件的真实结果：{{ tableRows.length }} 条</span>
              <el-button plain class="ghost-btn" @click="reset">重置筛选</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header">
            <div>
              <div class="card-eyebrow">Weight</div>
              <div class="card-title">综合权重设置</div>
            </div>
            <p class="card-desc">默认综合分只计算质量指标，自定义指标与耗时仍可单独查看与排序。</p>
          </div>
        </template>
        <div class="weight-note">默认综合分只使用质量指标：PSNR / SSIM / NIQE。耗时保持单独展示与单指标排序。</div>
        <div class="weight-grid">
          <div class="weight-item"><span class="weight-label">PSNR</span><el-input-number v-model="wPSNR" :min="0" :max="10" :step="0.1" size="small" controls-position="right" /></div>
          <div class="weight-item"><span class="weight-label">SSIM</span><el-input-number v-model="wSSIM" :min="0" :max="10" :step="0.1" size="small" controls-position="right" /></div>
          <div class="weight-item"><span class="weight-label">NIQE</span><el-input-number v-model="wNIQE" :min="0" :max="10" :step="0.1" size="small" controls-position="right" /></div>
        </div>
        <div class="weight-actions">
          <el-button plain class="preset-btn" @click="presetQuality">质量优先</el-button>
          <el-button plain class="preset-btn" @click="presetBalanced">均衡方案</el-button>
          <el-button plain class="preset-btn" @click="presetPerception">感知优先</el-button>
          <span class="weight-sum">权重总和：{{ weightSum.toFixed(2) }}</span>
        </div>
        <div class="weight-breakdown">
          <span v-for="item in weightBreakdown" :key="item.key" class="weight-chip">{{ item.label }} {{ item.percent }}%</span>
        </div>
      </el-card>
    </div>

    <div class="results-layout">
      <div v-if="bestResultRow" class="recommend-card">
        <div class="recommend-top">
          <div class="recommend-badge">当前最优</div>
          <div class="recommend-sort-tag">按{{ selectedRankMetricLabel }} 排序</div>
        </div>
        <h3 class="rec-title">{{ bestResultRow.algorithmName }}</h3>
        <p class="rec-summary">{{ bestResultSummary }}</p>
        <div class="rec-metrics">
          <div class="rec-metric"><span class="rec-metric-label">PSNR</span><strong>{{ bestResultRow.psnr ?? '-' }}</strong></div>
          <div class="rec-metric"><span class="rec-metric-label">SSIM</span><strong>{{ bestResultRow.ssim ?? '-' }}</strong></div>
          <div class="rec-metric"><span class="rec-metric-label">NIQE</span><strong>{{ bestResultRow.niqe ?? '-' }}</strong></div>
          <div class="rec-metric"><span class="rec-metric-label">{{ selectedRankMetricLabel }}</span><strong>{{ formatSortableMetricValue(bestResultRow) }}</strong></div>
        </div>
        <div class="export-actions">
          <el-button type="success" class="success-btn" @click="exportConclusionMd" :disabled="!store.user.isLoggedIn">导出结论 Markdown</el-button>
          <el-button plain class="soft-btn" @click="exportRecommendXlsx" :disabled="!store.user.isLoggedIn">导出对比 Excel</el-button>
          <el-button plain class="soft-btn" @click="exportRecommendCsv" :disabled="!store.user.isLoggedIn">导出对比 CSV</el-button>
        </div>
      </div>

      <el-card shadow="never" class="chart-card-wrapper">
        <template #header>
          <div class="chart-header">
            <div>
              <div class="card-eyebrow">Chart</div>
              <span class="chart-title">指标排行榜（Top {{ chartTopN }}）</span>
            </div>
            <div class="chart-actions">
              <el-select v-model="chartTopN" size="small" class="topn-select">
                <el-option :value="5" label="Top 5" />
                <el-option :value="10" label="Top 10" />
                <el-option :value="15" label="Top 15" />
              </el-select>
              <el-button plain class="soft-btn" size="small" @click="exportChartPng" :disabled="!store.user.isLoggedIn">导出图表</el-button>
            </div>
          </div>
        </template>
        <div class="chart-container">
          <canvas ref="chartCanvas" class="main-canvas" @mousemove="onChartMove" @mouseleave="onChartLeave"></canvas>
          <div v-if="chartTip.visible" class="canvas-tooltip" :style="{ left: chartTip.x + 'px', top: chartTip.y + 'px' }">{{ chartTip.text }}</div>
        </div>
      </el-card>

      <el-card shadow="never" class="table-card-wrapper">
        <template #header>
          <div class="table-header">
            <div>
              <div class="card-eyebrow">Details</div>
              <span class="table-title">对比详细清单</span>
            </div>
            <div class="table-actions">
              <span class="sort-hint">当前排序：{{ selectedRankMetricLabel }}</span>
              <el-button plain class="soft-btn" size="small" @click="exportXlsx" :disabled="!store.user.isLoggedIn">导出原始数据 Excel</el-button>
            </div>
          </div>
        </template>
        <div class="table-note">默认综合分只计算质量指标 PSNR / SSIM / NIQE；耗时与自定义指标可通过上方“排序方式”切换查看。</div>
        <el-table :data="tableRows" stripe class="compare-table" height="500">
          <el-table-column prop="algorithmName" label="算法名称" min-width="160" fixed="left" />
          <el-table-column :label="selectedRankMetricLabel" width="120" align="center">
            <template #default="{ row }"><span class="table-score">{{ formatSortableMetricValue(row) }}</span></template>
          </el-table-column>
          <el-table-column prop="psnr" label="PSNR" width="90" align="center" />
          <el-table-column prop="ssim" label="SSIM" width="90" align="center" />
          <el-table-column prop="niqe" label="NIQE" width="90" align="center" />
          <el-table-column prop="elapsed" label="耗时" width="90" align="center" />
          <el-table-column label="推荐分析" min-width="260">
            <template #default="{ row }"><span class="table-reason">{{ row.reason || '-' }}</span></template>
          </el-table-column>
          <el-table-column prop="createdAt" label="运行时间" width="160" />
        </el-table>
        <div v-if="tableRows.length === 0" class="empty-state"><el-empty description="无符合条件的对比结果" /></div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { TASK_LABEL_BY_TYPE, toTaskType, useAppStore } from "../stores/app";
import * as XLSX from "xlsx";

const store = useAppStore();
const task = ref("");
const datasetId = ref("");
const onlyDone = ref(true);
const chartMetric = ref("score");
const chartTopN = ref(10);
const wPSNR = ref(3.5);
const wSSIM = ref(3.5);
const wNIQE = ref(2.0);
const chartCanvas = ref(null);
const chartTip = ref({ visible: false, x: 0, y: 0, text: "" });
let chartHits = [];
const CACHE_KEY = "compare_filters_v2";
const PLATFORM_DEFAULT_METRICS = ["PSNR", "SSIM", "NIQE"];

const datasetMap = computed(() => new Map((store.datasets || []).map((item) => [item.id, item])));
const taskOptions = computed(() => Array.from(new Set((store.algorithms || []).map((item) => item.task).filter(Boolean))));
const availableRankMetrics = computed(() => {
  const base = [
    { value: "score", label: "默认综合分", direction: "higher_better" },
    { value: "psnr", label: "PSNR", direction: "higher_better" },
    { value: "ssim", label: "SSIM", direction: "higher_better" },
    { value: "niqe", label: "NIQE", direction: "lower_better" },
    { value: "time", label: "耗时", direction: "lower_better" },
  ];
  const seen = new Set(base.map((item) => item.value));
  for (const item of store.metricsCatalog || []) {
    const metricKey = String(item?.metricKey || "").trim();
    if (!metricKey || PLATFORM_DEFAULT_METRICS.includes(metricKey.toUpperCase()) || seen.has(metricKey)) continue;
    base.push({ value: metricKey, label: item.displayName || item.name || metricKey, direction: String(item.direction || "higher_better") });
    seen.add(metricKey);
  }
  return base;
});
const selectedRankMetricMeta = computed(() => availableRankMetrics.value.find((item) => item.value === chartMetric.value) || availableRankMetrics.value[0]);
const selectedRankMetricLabel = computed(() => selectedRankMetricMeta.value?.label || "默认综合分");
const selectedTaskSummary = computed(() => task.value || "全部任务");
const selectedDatasetSummary = computed(() => datasetId.value ? datasetMap.value.get(datasetId.value)?.name || datasetId.value : "全部数据集");
const weightSum = computed(() => Number(wPSNR.value) + Number(wSSIM.value) + Number(wNIQE.value));
const weightBreakdown = computed(() => {
  const sum = weightSum.value || 1;
  return [
    { key: "psnr", label: "PSNR", percent: Math.round((Number(wPSNR.value) / sum) * 100) },
    { key: "ssim", label: "SSIM", percent: Math.round((Number(wSSIM.value) / sum) * 100) },
    { key: "niqe", label: "NIQE", percent: Math.round((Number(wNIQE.value) / sum) * 100) },
  ];
});
function loadCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (typeof data.task === "string") task.value = data.task;
    if (typeof data.datasetId === "string") datasetId.value = data.datasetId;
    if (typeof data.onlyDone === "boolean") onlyDone.value = data.onlyDone;
    if (data.chartMetric != null) chartMetric.value = String(data.chartMetric);
    if (data.chartTopN != null) chartTopN.value = Number(data.chartTopN) || 10;
    if (data.wPSNR != null) wPSNR.value = Number(data.wPSNR) || 3.5;
    if (data.wSSIM != null) wSSIM.value = Number(data.wSSIM) || 3.5;
    if (data.wNIQE != null) wNIQE.value = Number(data.wNIQE) || 2.0;
  } catch {}
}

function saveCache() {
  localStorage.setItem(CACHE_KEY, JSON.stringify({
    task: task.value,
    datasetId: datasetId.value,
    onlyDone: onlyDone.value,
    chartMetric: chartMetric.value,
    chartTopN: chartTopN.value,
    wPSNR: wPSNR.value,
    wSSIM: wSSIM.value,
    wNIQE: wNIQE.value,
  }));
}

function reset() {
  task.value = "";
  datasetId.value = "";
  onlyDone.value = true;
  chartMetric.value = "score";
}

function resetAllConfig() {
  reset();
  chartTopN.value = 10;
  wPSNR.value = 3.5;
  wSSIM.value = 3.5;
  wNIQE.value = 2.0;
  saveCache();
}

function presetQuality() { wPSNR.value = 4.0; wSSIM.value = 3.8; wNIQE.value = 1.2; }
function presetBalanced() { wPSNR.value = 3.5; wSSIM.value = 3.5; wNIQE.value = 2.0; }
function presetPerception() { wPSNR.value = 2.8; wSSIM.value = 2.8; wNIQE.value = 4.2; }
function refreshAll() { return Promise.allSettled([store.fetchRuns(), store.fetchAlgorithms(), store.fetchDatasets(), store.fetchMetrics()]); }

function mapTaskLabelToType(taskLabel) {
  const entry = Object.entries(TASK_LABEL_BY_TYPE).find(([, label]) => label === taskLabel);
  return entry?.[0] || toTaskType(taskLabel || "");
}

function isDone(status) {
  const s = String(status || "").toLowerCase();
  return ["done", "completed", "success", "已完成"].includes(s);
}

function getRunDataMode(run) { return String(run?.raw?.params?.data_mode || run?.raw?.record?.data_mode || "").trim(); }
function isRealComparableRun(run) { return getRunDataMode(run) === "real_dataset"; }
function compareAuthenticityLabel(run) { return isRealComparableRun(run) ? "真实数据评测" : "非真实评测结果"; }
function toNumber(v) { const x = Number(v); return Number.isFinite(x) ? x : null; }
function parseElapsedSeconds(elapsed) {
  if (elapsed == null) return null;
  if (typeof elapsed === "number") return elapsed;
  const m = String(elapsed).match(/([\d.]+)/);
  if (!m) return null;
  const x = Number(m[1]);
  return Number.isFinite(x) ? x : null;
}
function minMax(values) {
  const nums = values.filter((x) => Number.isFinite(x));
  if (!nums.length) return { min: null, max: null };
  return { min: Math.min(...nums), max: Math.max(...nums) };
}
function comparableTaskKey(run) {
  return String(run?.taskType || mapTaskLabelToType(run?.task) || run?.task || "").trim();
}
function comparableGroupKey(run) {
  return `${comparableTaskKey(run)}::${String(run?.datasetId || "").trim()}`;
}
function buildScoringContext(runs, targetRun) {
  const key = comparableGroupKey(targetRun);
  const comparableRuns = (runs || []).filter((run) => comparableGroupKey(run) === key);
  const psnrs = comparableRuns.map((run) => toNumber(run.psnr)).filter((x) => x != null);
  const ssims = comparableRuns.map((run) => toNumber(run.ssim)).filter((x) => x != null);
  const niqes = comparableRuns.map((run) => toNumber(run.niqe)).filter((x) => x != null);
  return {
    mmPSNR: minMax(psnrs),
    mmSSIM: minMax(ssims),
    mmNIQE: minMax(niqes),
    sampleCount: comparableRuns.length,
  };
}
function norm01(x, min, max) {
  if (!Number.isFinite(x) || !Number.isFinite(min) || !Number.isFinite(max)) return null;
  if (max === min) return 1;
  return (x - min) / (max - min);
}
function metricDirection(metricKey) {
  const found = availableRankMetrics.value.find((item) => item.value === metricKey);
  return String(found?.direction || "higher_better");
}
function getCustomMetricValue(run, metricKey) {
  const key = String(metricKey || "").trim().toUpperCase();
  const list = Array.isArray(run?.customMetrics) ? run.customMetrics : [];
  const found = list.find((item) => String(item?.key || "").trim().toUpperCase() === key);
  return toNumber(found?.value);
}
function getSortMetricValue(run, metricKey) {
  const key = String(metricKey || "");
  if (key === "score") return Number.isFinite(run?.score) ? Number(run.score) : null;
  if (key === "psnr") return toNumber(run?.psnr);
  if (key === "ssim") return toNumber(run?.ssim);
  if (key === "niqe") return toNumber(run?.niqe);
  if (key === "time") return parseElapsedSeconds(run?.elapsed);
  return getCustomMetricValue(run, key);
}
function formatSortMetricValue(value, metricKey) {
  if (!Number.isFinite(value)) return "-";
  if (metricKey === "time") return `${Number(value).toFixed(3)}s`;
  if (metricKey === "ssim") return Number(value).toFixed(4);
  return Number(value).toFixed(4);
}
function formatSortableMetricValue(row) { return formatSortMetricValue(row?.sortMetricValue, chartMetric.value); }

const tableRows = computed(() => {
  const dsMap = datasetMap.value;
  const algMap = new Map((store.algorithms || []).map((item) => [item.id, item]));
  let runs = [...(store.runs || [])];
  if (task.value) {
    const taskType = mapTaskLabelToType(task.value);
    runs = runs.filter((run) => String(run.task || "") === task.value || String(run.taskType || "") === taskType);
  }
  if (datasetId.value) runs = runs.filter((run) => run.datasetId === datasetId.value);
  if (onlyDone.value) runs = runs.filter((run) => isDone(run.status));
  runs = runs.filter((run) => isRealComparableRun(run));

  const sum = weightSum.value > 0 ? weightSum.value : 1;
  const W = { psnr: Number(wPSNR.value) / sum, ssim: Number(wSSIM.value) / sum, niqe: Number(wNIQE.value) / sum };
  const ctxCache = new Map();

  const rows = runs.map((run) => {
    const ds = dsMap.get(run.datasetId);
    const alg = algMap.get(run.algorithmId);
    const groupKey = comparableGroupKey(run);
    if (!ctxCache.has(groupKey)) ctxCache.set(groupKey, buildScoringContext(runs, run));
    const ctx = ctxCache.get(groupKey);
    const psnr = toNumber(run.psnr);
    const ssim = toNumber(run.ssim);
    const niqe = toNumber(run.niqe);
    const nPSNR = norm01(psnr, ctx.mmPSNR.min, ctx.mmPSNR.max);
    const nSSIM = norm01(ssim, ctx.mmSSIM.min, ctx.mmSSIM.max);
    const nNIQE = norm01(niqe, ctx.mmNIQE.min, ctx.mmNIQE.max);
    const okAll = [nPSNR, nSSIM, nNIQE].every((x) => x != null);
    let score = null;
    if (okAll) score = Number((W.psnr * nPSNR + W.ssim * nSSIM + W.niqe * (1 - nNIQE)).toFixed(4));
    return {
      ...run,
      datasetName: ds?.name || run.datasetId,
      algorithmName: alg?.name || run.algorithmId,
      score,
      comparableSampleCount: ctx.sampleCount || 0,
      legacyReason: okAll
        ? "默认质量综合分按 PSNR / SSIM / NIQE 加权计算。"
        : "平台内置指标不完整，当前不参与默认综合分排序。",
      reason: okAll
        ? `默认质量综合分按 PSNR ${Math.round(W.psnr * 100)}% + SSIM ${Math.round(W.ssim * 100)}% + NIQE ${Math.round(W.niqe * 100)}% 计算；评分范围为同任务同数据集（样本池 ${ctx.sampleCount || 0} 条）。耗时请单独查看。`
        : "同任务同数据集下平台内置指标不完整，当前不参与默认综合分排序。",
    };
  });

  const currentMetric = String(chartMetric.value || "score");
  const betterHigh = !["niqe", "time"].includes(currentMetric) && metricDirection(currentMetric) !== "lower_better";
  rows.forEach((row) => { row.sortMetricValue = getSortMetricValue(row, currentMetric); });
  rows.sort((a, b) => {
    const av = a.sortMetricValue;
    const bv = b.sortMetricValue;
    const aOk = Number.isFinite(av);
    const bOk = Number.isFinite(bv);
    if (aOk && bOk) return betterHigh ? bv - av : av - bv;
    if (aOk) return -1;
    if (bOk) return 1;
    return String(a.algorithmName || "").localeCompare(String(b.algorithmName || ""), "zh-Hans-CN-u-co-pinyin");
  });
  return rows;
});

const bestResultRow = computed(() => (tableRows.value.length ? tableRows.value[0] : null));
const bestResultSummary = computed(() => {
  const top = bestResultRow.value;
  if (!top) return "";
  if (chartMetric.value === "score") return `这是当前筛选条件下基于综合分得到的默认最优方案。${top.reason ? ` ${top.reason}` : ""}`;
  return `这是当前筛选条件下按“${selectedRankMetricLabel.value}”排序得到的当前最优方案。${top.reason ? ` ${top.reason}` : ""}`;
});
const recommendText = computed(() => {
  if (!tableRows.value.length) return "";
  const top = tableRows.value[0];
  const currentValue = getSortMetricValue(top, chartMetric.value);
  if (!Number.isFinite(currentValue)) return "";
  return [
    `推荐算法：${top.algorithmName}`,
    `当前排序：${selectedRankMetricLabel.value}=${formatSortMetricValue(currentValue, chartMetric.value)}`,
    `推荐理由：${top.reason || '-'}`,
    `结论口径：${compareAuthenticityLabel(top)}`,
    `指标摘要：PSNR=${top.psnr}，SSIM=${top.ssim}，NIQE=${top.niqe}，耗时=${top.elapsed || '-'}`,
  ].join(" ");
});
const chartItems = computed(() => {
  const n = Math.max(1, Number(chartTopN.value) || 10);
  const metricKey = String(chartMetric.value || "score");
  const betterHigh = !["niqe", "time"].includes(metricKey) && metricDirection(metricKey) !== "lower_better";
  return [...tableRows.value]
    .map((row) => ({ name: row.algorithmName, value: getSortMetricValue(row, metricKey), raw: row }))
    .filter((item) => item.value != null)
    .sort((a, b) => (betterHigh ? b.value - a.value : a.value - b.value))
    .slice(0, n);
});

function onChartLeave() { chartTip.value = { ...chartTip.value, visible: false }; }

function onChartMove(event) {
  const canvas = chartCanvas.value;
  if (!canvas || !chartHits.length) return;
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const hit = chartHits.find((item) => x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h);
  if (!hit) return onChartLeave();
  chartTip.value = { visible: true, x: Math.max(8, Math.min(rect.width - 8, x + 12)), y: Math.max(8, Math.min(rect.height - 8, y + 12)), text: `${hit.name}锛?{hit.text}` };
}

function drawChart() {
  const canvas = chartCanvas.value;
  if (!canvas) return;
  if (!canvas.isConnected) return;
  const items = chartItems.value || [];
  const wrap = canvas.parentElement;
  const cssW = Math.min(1600, Math.max(320, Math.floor(wrap?.clientWidth || 720)));
  const cssH = items.length >= 10 ? 360 : 320;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, cssW, cssH);

  const padL = 56, padR = 16, padT = 24, padB = 88;
  const plotW = cssW - padL - padR;
  const plotH = cssH - padT - padB;
  ctx.strokeStyle = "#e5e7eb";
  ctx.strokeRect(padL, padT, plotW, plotH);

  const values = items.map((item) => Number(item.value)).filter((x) => Number.isFinite(x));
  const metricKey = String(chartMetric.value || "score");
  const useUnitScale = metricKey === "score" || metricKey === "ssim";
  const maxV = useUnitScale ? 1 : values.length ? Math.max(...values) : 1;
  const minV = useUnitScale ? 0 : values.length ? Math.min(...values) : 0;
  const span = maxV - minV || 1;

  ctx.font = "12px var(--el-font-family, system-ui)";
  ctx.fillStyle = "#6b7280";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 4; i += 1) {
    const t = i / 4;
    const y = padT + plotH - t * plotH;
    ctx.strokeStyle = i === 0 ? "#e5e7eb" : "#f3f4f6";
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(padL + plotW, y);
    ctx.stroke();
    const v = minV + t * span;
    ctx.fillText(useUnitScale ? v.toFixed(2) : v.toFixed(3), padL - 6, y);
  }

  if (!items.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.textAlign = "center";
    ctx.fillText("无图表数据", cssW / 2, cssH / 2);
    chartHits = [];
    return;
  }

  const gap = items.length >= 12 ? 6 : 10;
  const bw = Math.max(12, Math.floor((plotW - gap * (items.length - 1)) / items.length));
  const totalBarsW = bw * items.length + gap * (items.length - 1);
  const startX = padL + Math.max(0, Math.floor((plotW - totalBarsW) / 2));
  chartHits = [];
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.font = "11px var(--el-font-family, system-ui)";

  items.forEach((item, index) => {
    const x = startX + index * (bw + gap);
    const value = Number(item.value);
    const nv = (Math.max(minV, Math.min(maxV, value)) - minV) / span;
    const h = Math.max(1, Math.round(nv * plotH));
    const y = padT + plotH - h;
    ctx.fillStyle = "#3b82f6";
    ctx.fillRect(x, y, bw, h);
    ctx.fillStyle = "#1f2937";
    const label = item.name.length > 12 ? `${item.name.slice(0, 12)}...` : item.name;
    ctx.save();
    ctx.translate(x + bw / 2, padT + plotH + 8);
    ctx.rotate(-Math.PI / 5);
    ctx.fillText(label, 0, 0);
    ctx.restore();
    chartHits.push({ x, y, w: bw, h, name: item.name, text: formatSortMetricValue(value, metricKey) });
  });

  ctx.fillStyle = "#1f2937";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  const extra = metricKey === "score" ? "（平台内置综合分）" : "";
  ctx.fillText(`图表指标：${selectedRankMetricLabel.value}${extra}`, padL, 0);
}



function buildExportRows() {
  return (tableRows.value || []).map((row) => ({
    创建时间: row.createdAt ?? "",
    任务: row.task ?? "",
    数据集: row.datasetName ?? "",
    算法: row.algorithmName ?? "",
    排序指标: selectedRankMetricLabel.value,
    排序值: formatSortableMetricValue(row),
    PSNR: row.psnr ?? "",
    SSIM: row.ssim ?? "",
    NIQE: row.niqe ?? "",
    耗时: row.elapsed ?? "",
    综合分: Number.isFinite(row.score) ? row.score : "",
    推荐分析: row.reason ?? "",
    RunID: row.id ?? "",
  }));
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function exportRecommendCsv() {
  const rows = buildExportRows();
  const headers = Object.keys(rows[0] || {});
  const csv = [headers.join(",")]
    .concat(rows.map((row) => headers.map((key) => `"${String(row[key] ?? "").replaceAll('"', '""')}"`).join(",")))
    .join("\n");
  downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8;" }), `compare_${Date.now()}.csv`);
}

function exportRecommendXlsx() {
  const rows = buildExportRows();
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(rows);
  XLSX.utils.book_append_sheet(wb, ws, "Compare");
  XLSX.writeFile(wb, `compare_${Date.now()}.xlsx`);
}

function exportXlsx() { exportRecommendXlsx(); }

function exportConclusionMd() {
  const lines = [
    "# 平台算法对比结论",
    "",
    `- 排序方式：${selectedRankMetricLabel.value}`,
    `- 默认综合分口径：PSNR=${wPSNR.value}，SSIM=${wSSIM.value}，NIQE=${wNIQE.value}（耗时单独展示，不纳入默认综合分）`,
    "",
  ];
  if (bestResultRow.value) {
    lines.push("## 当前最优");
    lines.push(bestResultSummary.value);
    lines.push("");
  }
  if (recommendText.value) {
    lines.push("## 推荐说明");
    lines.push(recommendText.value);
    lines.push("");
  }
  for (const row of tableRows.value) {
    lines.push(`- ${row.algorithmName}：${selectedRankMetricLabel.value}=${formatSortableMetricValue(row)}，${row.reason || '-'}`);
  }
  downloadBlob(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8;" }), `compare_${Date.now()}.md`);
}

function exportChartPng() {
  const canvas = chartCanvas.value;
  if (!canvas) return;
  canvas.toBlob((blob) => {
    if (!blob) return;
    downloadBlob(blob, `compare_chart_${chartMetric.value}_${Date.now()}.png`);
  }, "image/png");
}

watch([task, datasetId, onlyDone, chartMetric, chartTopN, wPSNR, wSSIM, wNIQE], saveCache, { deep: true });
watch([tableRows, chartMetric, chartTopN], async () => { await nextTick(); drawChart(); });
watch(availableRankMetrics, () => {
  const allowed = new Set(availableRankMetrics.value.map((item) => item.value));
  if (!allowed.has(chartMetric.value)) chartMetric.value = "score";
});

onMounted(async () => {
  loadCache();
  await refreshAll();
  await nextTick();
  drawChart();
});
</script>

<style scoped>
.page {
  --page-bg: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  --card-bg: rgba(255, 255, 255, 0.96);
  --card-border: #e2e8f0;
  --card-shadow: 0 10px 25px rgba(148, 163, 184, 0.08);
  --text-main: #1e293b;
  --text-soft: #64748b;
  --text-muted: #94a3b8;
  --accent: #3b82f6;
  --accent-deep: #2563eb;
  --accent-soft: #dbeafe;
  --success: #10b981;
  --success-deep: #059669;
  --warning: #f59e0b;
  --danger: #ef4444;
  padding: 24px;
  min-height: 100%;
  background: var(--page-bg);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.hero-panel,
.header-actions,
.hero-meta,
.card-header,
.filter-row-secondary,
.filter-footer-actions,
.weight-actions,
.tool-row,
.tool-actions,
.fast-meta-row,
.recommend-top,
.export-actions,
.table-header,
.table-actions,
.chart-header,
.chart-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-panel,
.tool-row,
.table-header,
.chart-header,
.filter-row-secondary {
  justify-content: space-between;
}

.hero-panel {
  padding: 32px 36px;
  margin-bottom: 24px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 34%),
    radial-gradient(circle at right center, rgba(59, 130, 246, 0.08), transparent 28%),
    rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(220, 231, 245, 0.95);
  box-shadow: var(--card-shadow);
  transition: all 0.3s ease;
}

.hero-panel:hover {
  box-shadow: 0 15px 30px rgba(148, 163, 184, 0.12);
  transform: translateY(-2px);
}

.hero-copy {
  max-width: 980px;
}

.hero-kicker,
.card-eyebrow {
  margin-bottom: 10px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.page-title {
  margin: 0;
  color: var(--text-main);
  font-size: 38px;
  line-height: 1.1;
  font-weight: 800;
}

.page-subtitle,
.card-desc,
.tool-desc,
.weight-note,
.fast-meta,
.fast-note,
.sort-hint,
.table-reason,
.table-note,
.inline-tip {
  color: var(--text-soft);
}

.page-subtitle {
  max-width: 860px;
  margin: 16px 0 0;
  font-size: 16px;
  line-height: 1.8;
}

.hero-meta {
  margin-top: 24px;
}

.meta-pill {
  min-width: 160px;
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(219, 234, 254, 0.9);
  transition: all 0.2s ease;
}

.meta-pill:hover {
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.meta-label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.meta-pill strong {
  color: var(--text-main);
  font-size: 15px;
  font-weight: 700;
}

.config-grid,
.results-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.config-card,
.tool-card,
.chart-card-wrapper,
.table-card-wrapper,
.recommend-card {
  border: 1px solid var(--card-border);
  border-radius: 16px;
  background: var(--card-bg);
  box-shadow: var(--card-shadow);
  transition: all 0.3s ease;
}

.config-card:hover,
.tool-card:hover,
.chart-card-wrapper:hover,
.table-card-wrapper:hover,
.recommend-card:hover {
  box-shadow: 0 15px 30px rgba(148, 163, 184, 0.12);
  transform: translateY(-2px);
}

.card-header {
  align-items: flex-start;
}

.card-title,
.tool-title,
.table-title,
.chart-title {
  color: var(--text-main);
  font-weight: 800;
  line-height: 1.15;
}

.card-title {
  font-size: 22px;
}

.tool-title,
.table-title,
.chart-title {
  font-size: 20px;
}

.card-desc {
  max-width: 280px;
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  text-align: right;
}

.filter-form,
.weight-grid {
  display: grid;
  gap: 16px;
}

.flex-item {
  width: 100%;
}

.topn-select {
  width: 112px;
}

.filter-footer-actions {
  justify-content: flex-end;
}

.weight-note,
.table-note,
.tool-placeholder {
  padding: 16px 18px;
  border-radius: 16px;
  background: #f8fbff;
  border: 1px solid #e2ebf7;
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 16px;
}

.tool-warning {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #ffe1c2;
  background: #fff6eb;
  color: #9a5b18;
  line-height: 1.7;
}

.weight-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.weight-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px;
  border-radius: 18px;
  background: #fbfdff;
  border: 1px solid #e2ebf7;
  transition: all 0.2s ease;
}

.weight-item:hover {
  background: #f8fbff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.weight-label {
  color: var(--text-main);
  font-size: 18px;
  font-weight: 800;
}

.weight-sum {
  color: var(--accent);
  font-weight: 800;
}

.weight-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.weight-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: #edf4ff;
  color: #315ea8;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s ease;
}

.weight-chip:hover {
  background: #dbeafe;
  transform: translateY(-1px);
}

.tool-card,
.table-card-wrapper {
  margin-bottom: 20px;
}

.tool-row {
  align-items: flex-start;
  margin-bottom: 16px;
}

.tool-status {
  padding: 10px 14px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
}

.control-box {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #fbfdff;
  border: 1px solid #e2ebf7;
}

.control-label {
  color: var(--text-main);
  font-size: 13px;
  font-weight: 700;
}

.rank-badge,
.recommend-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #e8fff1;
  color: #15803d;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 800;
  transition: all 0.2s ease;
}

.rank-badge:hover,
.recommend-badge:hover {
  background: #dcfce7;
  transform: translateY(-1px);
}

.recommend-sort-tag {
  padding: 8px 14px;
  border-radius: 999px;
  background: #edf4ff;
  color: #315ea8;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s ease;
}

.recommend-sort-tag:hover {
  background: #dbeafe;
  transform: translateY(-1px);
}

.fast-res-container,
.recommend-card {
  margin-top: 16px;
}

.fast-meta-row {
  justify-content: space-between;
  margin-top: 14px;
}

.recommend-card {
  padding: 28px;
}

.rec-title {
  margin: 16px 0 12px;
  color: var(--text-main);
  font-size: 34px;
  line-height: 1.15;
  font-weight: 800;
}

.rec-summary {
  margin: 0 0 24px;
  color: #4b5d79;
  font-size: 15px;
  line-height: 1.8;
}

.rec-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.rec-metric {
  padding: 16px 18px;
  border-radius: 18px;
  background: #f8fbff;
  border: 1px solid #e2ebf7;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
}

.rec-metric:hover {
  background: #edf4ff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transform: translateY(-1px);
}

.rec-metric-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.rec-metric strong,
.table-score {
  color: var(--accent);
  font-weight: 800;
  font-size: 18px;
}

.chart-container {
  position: relative;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.main-canvas {
  width: 100%;
  max-width: 100%;
  height: 340px;
  display: block;
  contain: strict;
}

.canvas-tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 2;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.92);
  color: #fff;
  font-size: 12px;
  transform: translateY(-100%);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.22);
  transition: all 0.2s ease;
}

.empty-state {
  padding: 32px 16px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.soft-btn,
.danger-soft-btn,
.ghost-btn,
.preset-btn,
.success-btn,
.primary-btn,
.accent-btn {
  min-height: 44px;
  border-radius: 8px;
  font-weight: 600;
  box-shadow: none;
  transition: all 0.2s ease;
  padding: 0 18px;
  font-size: 14px;
}

.soft-btn,
.ghost-btn,
.preset-btn {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.95);
  border-color: #e2e8f0;
}

.soft-btn:hover,
.ghost-btn:hover,
.preset-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.danger-soft-btn {
  color: var(--danger);
  background: #fef2f2;
  border-color: #fecaca;
}

.danger-soft-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.primary-btn {
  color: white;
  border-color: var(--accent);
  background: var(--accent);
}

.primary-btn:hover {
  background: var(--accent-deep);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.accent-btn {
  color: var(--warning);
  border-color: #fcd34d;
  background: #fef3c7;
}

.accent-btn:hover {
  background: #fde68a;
  border-color: #fbbf24;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.success-btn {
  color: white;
  border-color: var(--success);
  background: var(--success);
}

.success-btn:hover {
  background: var(--success-deep);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);
}

:deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #edf2f8;
}

:deep(.el-card__body) {
  padding: 24px;
}

:deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 8px;
  box-shadow: none;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

:deep(.el-select__wrapper:hover) {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

:deep(.el-select__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

:deep(.el-input-number) {
  width: 144px;
}

:deep(.el-input-number .el-input__wrapper) {
  border-radius: 8px;
  box-shadow: none;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
  min-height: 40px;
}

:deep(.el-input-number .el-input__wrapper:hover) {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

:deep(.el-input-number .el-input__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

:deep(.el-table) {
  --el-table-header-bg-color: #f8fafc;
  --el-table-row-hover-bg-color: #f1f5f9;
  --el-table-border-color: #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

:deep(.el-table:hover) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

:deep(.el-table th.el-table__cell) {
  color: var(--text-main);
  font-weight: 700;
  font-size: 14px;
  padding: 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

:deep(.el-table td.el-table__cell) {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
  color: var(--text-main);
}

:deep(.el-checkbox__label) {
  color: var(--text-main);
  font-size: 14px;
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--accent);
  border-color: var(--accent);
}

@media (max-width: 1200px) {
  .config-grid,
  .results-layout,
  .weight-grid,
  .rec-metrics {
    grid-template-columns: 1fr;
  }

  .card-desc {
    max-width: none;
    text-align: left;
  }
}

@media (max-width: 768px) {
  .page {
    padding: 16px;
  }

  .hero-panel,
  .recommend-card {
    padding: 24px;
  }

  .page-title {
    font-size: 28px;
  }

  .rec-title {
    font-size: 28px;
  }

  .header-actions,
  .tool-actions,
  .table-actions,
  .chart-actions,
  .export-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .control-box,
  .soft-btn,
  .danger-soft-btn,
  .ghost-btn,
  .preset-btn,
  .success-btn,
  .primary-btn,
  .accent-btn {
    width: 100%;
    justify-content: center;
  }

  :deep(.el-input-number) {
    width: 100%;
  }

  .hero-meta {
    flex-direction: column;
    align-items: stretch;
  }

  .meta-pill {
    min-width: auto;
  }
}
</style>




