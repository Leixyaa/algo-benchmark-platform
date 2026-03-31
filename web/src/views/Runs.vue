<template>
  <div class="page">
    <div class="header-section">
      <div class="header-left">
        <h2 class="page-title">运行任务中心</h2>
        <p class="page-subtitle">监控算法运行状态、查看量化指标、导出评测结果与排查失败原因</p>
      </div>
      <div class="header-right">
        <el-button type="primary" size="large" icon="Plus" class="create-btn" @click="goNewRun">新建运行任务</el-button>
      </div>
    </div>

    <el-card shadow="never" class="main-card">
      <div class="toolbar-section">
        <div class="filter-group">
          <el-select v-model="statusFilter" clearable placeholder="运行状态" class="filter-item status-select">
            <template #prefix><el-icon><InfoFilled /></el-icon></template>
            <el-option v-for="x in statusOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-select v-model="taskFilter" clearable placeholder="算法任务" class="filter-item task-select">
            <template #prefix><el-icon><Grid /></el-icon></template>
            <el-option v-for="x in taskOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索算法、数据集、参数方案..."
            class="filter-item search-input"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button icon="Refresh" circle class="refresh-btn" @click="refresh" />
        </div>

        <div class="action-group">
          <el-dropdown trigger="click">
            <el-button size="small" icon="Download">
              导出数据<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item icon="Document" @click="exportDoneCsv">导出已完成 (CSV)</el-dropdown-item>
                <el-dropdown-item icon="TrendCharts" @click="exportDoneXlsx">导出已完成 (Excel)</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" type="danger" plain icon="Delete" @click="clearDone">清理已完成</el-button>
        </div>
      </div>

      <el-table 
        :data="filteredRows" 
        class="custom-table"
        style="width: 100%"
        stripe 
        size="small"
        row-key="id"
        v-loading="store.loading"
      >
        <el-table-column prop="task" label="算法任务" width="110">
          <template #default="{ row }">
            <div class="task-cell">
              <span class="task-dot" :class="row.taskType"></span>
              {{ row.task }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="dataset" label="评测数据集" min-width="120" show-overflow-tooltip />
        <el-table-column prop="algorithm" label="运行算法" min-width="140">
          <template #default="{ row }">
            <div class="algo-cell">
              <span class="algo-name">{{ row.algorithm }}</span>
              <span class="algo-scheme">{{ row.paramSchemeText }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="运行状态" width="110">
          <template #default="{ row }">
            <el-tag 
              :type="statusTagType(row.status)" 
              effect="light" 
              class="status-tag"
              round
            >
              <el-icon v-if="row.status === '运行中' || row.status === 'running'"><Loading /></el-icon>
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="综合评分" width="90" align="center">
          <template #default="{ row }">
            <div v-if="row.score !== null" class="score-cell">
              <span class="score-val">{{ row.score }}</span>
            </div>
            <span v-else class="score-null">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" class="op-btn" type="primary" plain @click="openDetail(row)">详情</el-button>
              <el-button v-if="canCancel(row)" size="small" class="op-btn" type="warning" plain @click="cancel(row.id)">取消</el-button>
              <el-button size="small" class="op-btn" type="danger" plain @click="remove(row.id)">隐藏</el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无运行记录" :image-size="120" />
        </template>
      </el-table>

      <div class="pagination-mock">
        共 {{ filteredRows.length }} 条记录
      </div>
    </el-card>

    <el-dialog 
      v-model="detailVisible" 
      title="运行任务详情" 
      width="800px" 
      class="detail-dialog"
      destroy-on-close
    >
      <div v-if="detail" class="detail-container">
        <div class="detail-header-card">
          <div class="detail-main-info">
            <div class="info-item">
              <span class="info-label">任务 ID</span>
              <span class="info-value mono">{{ detail.id }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">当前状态</span>
              <el-tag :type="statusTagType(detail.status)" round>{{ statusText(detail.status) }}</el-tag>
            </div>
            <div class="info-item">
              <span class="info-label">创建时间</span>
              <span class="info-value">{{ detail.createdAt }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section-grid">
          <!-- 基础信息 -->
          <div class="detail-card">
            <div class="card-title"><el-icon><Memo /></el-icon> 基本配置</div>
            <div class="card-content">
              <div class="kv-row">
                <span class="kv-label">算法大类</span>
                <span class="kv-value">{{ detail.task }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">数据集</span>
                <span class="kv-value">{{ detail.dataset }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">算法种类</span>
                <span class="kv-value">{{ detail.algorithm }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">参数方案</span>
                <span class="kv-value">{{ detail.paramSchemeText || "-" }}</span>
              </div>
            </div>
          </div>

          <!-- 指标数据 -->
          <div class="detail-card">
            <div class="card-title"><el-icon><DataLine /></el-icon> 量化指标</div>
            <div class="card-content">
              <div class="metric-grid">
                <div class="metric-box">
                  <div class="metric-label">PSNR</div>
                  <div class="metric-value">{{ detail.psnr ?? "-" }}</div>
                </div>
                <div class="metric-box">
                  <div class="metric-label">SSIM</div>
                  <div class="metric-value">{{ detail.ssim ?? "-" }}</div>
                </div>
                <div class="metric-box">
                  <div class="metric-label">NIQE</div>
                  <div class="metric-value">{{ detail.niqe ?? "-" }}</div>
                </div>
                <div class="metric-box highlighted">
                  <div class="metric-label">综合评分</div>
                  <div class="metric-value">{{ detail.score ?? "-" }}</div>
                </div>
              </div>
              <div class="performance-info">
                <div class="perf-item"><span>总耗时:</span> <strong>{{ detail.elapsed ?? "-" }}</strong></div>
                <div class="perf-item"><span>样本数:</span> <strong>{{ detail.raw?.params?.data_used ?? "-" }}</strong></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 参数详情 -->
        <div class="detail-card full-width">
          <div class="card-title"><el-icon><Setting /></el-icon> 运行参数详情</div>
          <div class="card-content">
            <div class="params-container">
              <div v-if="(detail.userParamRows || []).length === 0" class="params-empty">
                本次运行使用系统内置默认参数。
              </div>
              <div class="params-grid">
                <div v-for="item in detail.userParamRows || []" :key="`u-${item.key}`" class="param-card">
                  <div class="param-header">
                    <span class="param-name">{{ item.label }}</span>
                    <span class="param-val mono">{{ item.value }}</span>
                  </div>
                  <div class="param-desc">{{ item.desc }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 推荐理由 -->
        <div v-if="detail.reason" class="detail-card full-width reason-card">
          <div class="card-title"><el-icon><MagicStick /></el-icon> 推荐分析</div>
          <div class="card-content">
            <div class="reason-text">{{ detail.reason }}</div>
          </div>
        </div>

        <!-- 错误详情 -->
        <div v-if="detail.raw?.error || detail.raw?.error_code" class="detail-card full-width error-card">
          <div class="card-title"><el-icon><Warning /></el-icon> 异常报告</div>
          <div class="card-content">
            <pre class="error-pre">{{ formatRunError(detail.raw) }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>

</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";

const router = useRouter();
const store = useAppStore();

const HIDDEN_KEY = "hiddenRunIds_v1";
const BUILTIN_ALGORITHM_IDS = new Set([
  "alg_dn_cnn",
  "alg_denoise_bilateral",
  "alg_denoise_gaussian",
  "alg_denoise_median",
  "alg_dehaze_dcp",
  "alg_dehaze_clahe",
  "alg_dehaze_gamma",
  "alg_deblur_unsharp",
  "alg_deblur_laplacian",
  "alg_sr_bicubic",
  "alg_sr_lanczos",
  "alg_sr_nearest",
  "alg_lowlight_gamma",
  "alg_lowlight_clahe",
  "alg_video_denoise_gaussian",
  "alg_video_denoise_median",
  "alg_video_sr_bicubic",
  "alg_video_sr_lanczos",
]);
const hiddenIds = ref(new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || "[]")));

function persistHidden() {
  localStorage.setItem(HIDDEN_KEY, JSON.stringify(Array.from(hiddenIds.value)));
}

function downloadFile(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function exportDoneCsv() {
  const url = "http://127.0.0.1:8000/runs/export?format=csv&status=done";
  downloadFile(url, "runs_done.csv");
}

function exportDoneXlsx() {
  const url = "http://127.0.0.1:8000/runs/export?format=xlsx&status=done";
  downloadFile(url, "runs_done.xlsx");
}

async function clearDone() {
  try {
    await ElMessageBox.confirm("确认清理所有已完成任务吗？", "清理确认", {
      type: "warning",
      confirmButtonText: "清理",
      cancelButtonText: "取消",
    });
    const res = await fetch("http://127.0.0.1:8000/runs/clear?status=done", {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    ElMessage({ type: "success", message: `已清理 ${data.deleted} 条已完成任务` });
    await refresh();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `清理失败：${e?.message || e}` });
  }
}


const rows = computed(() => {
  const dsMap = new Map((store.datasets ?? []).map((d) => [d.id, d.name]));
  const algoMap = new Map((store.algorithms ?? []).map((a) => [a.id, a.name]));

  return (store.runs ?? [])
    .filter((r) => !hiddenIds.value.has(r.id))
    .map((r) => {
      const base = {
        ...r,
        name: r.name || `${r.task || "任务"} Run`,
        dataset: dsMap.get(r.datasetId) ?? r.datasetId ?? "-",
        algorithm: algoMap.get(r.algorithmId) ?? r.algorithmId ?? "-",
        paramSchemeText: resolveParamSchemeText(r),
      };

      const ctx = buildScoringContext(store.runs ?? []);
      const s = scoreOne(base, ctx);
      return {
        ...base,
        score: s.score,
      };
  });
});

const statusFilter = ref("");
const taskFilter = ref("");
const keyword = ref("");

const statusOptions = [
  { value: "排队中", label: "排队中" },
  { value: "运行中", label: "运行中" },
  { value: "已完成", label: "已完成" },
  { value: "失败", label: "失败" },
  { value: "取消中", label: "取消中" },
  { value: "已取消", label: "已取消" },
];

const taskOptions = computed(() =>
  Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label }))
);

const filteredRows = computed(() => {
  const kw = String(keyword.value || "").trim().toLowerCase();
  return (rows.value ?? []).filter((r) => {
    if (statusFilter.value && r.status !== statusFilter.value) return false;
    if (taskFilter.value && r.taskType !== taskFilter.value) return false;
    if (!kw) return true;
    const hay = `${r.dataset ?? ""} ${r.algorithm ?? ""} ${r.task ?? ""} ${r.paramSchemeText ?? ""}`.toLowerCase();
    return hay.includes(kw);
  });
});

function goNewRun() {
  router.push("/new-run");
}

function formatJson(v) {
  try {
    return JSON.stringify(v ?? null, null, 2);
  } catch {
    return String(v ?? "");
  }
}

function formatNum(v) {
  if (v == null || v === "") return "-";
  const x = Number(v);
  if (!Number.isFinite(x)) return String(v);
  return x.toFixed(4);
}

function formatRunError(raw) {
  if (!raw || typeof raw !== "object") return "-";
  const code = raw.error_code || raw.errorCode || "";
  const msg = raw.error || "";
  const detail = raw.error_detail || raw.errorDetail || null;
  const head = code ? `${code}${msg ? `: ${msg}` : ""}` : msg || "-";
  if (!detail) return head;
  return `${head}\n${formatJson(detail)}`;
}

function resolveParamSchemeText(run) {
  const p = run?.raw?.params && typeof run.raw.params === "object" && !Array.isArray(run.raw.params) ? run.raw.params : {};
  const s = String(p.param_scheme || "").trim().toLowerCase();
  if (String(p.user_scheme_name || "").trim()) return `用户：${String(p.user_scheme_name).trim()}`;
  if (s.startsWith("user:")) return `用户：${s.slice(5)}`;
  const alg = (store.algorithms || []).find((a) => String(a?.id || "") === String(run?.algorithmId || ""));
  const runEff = pickEffectiveParams(p);
  if (alg) {
    const def = pickEffectiveParams(alg?.defaultParams && typeof alg.defaultParams === "object" ? alg.defaultParams : {});
    if (isSameParams(runEff, def)) return "系统内置默认参数";
    const presets = alg?.paramPresets && typeof alg.paramPresets === "object" && !Array.isArray(alg.paramPresets) ? alg.paramPresets : {};
    for (const [k, v] of Object.entries(presets)) {
      const cur = pickEffectiveParams(v && typeof v === "object" && !Array.isArray(v) ? v : {});
      if (isSameParams(runEff, cur)) {
        if (k === "speed") return "系统：速度优先";
        if (k === "quality") return "系统：质量优先";
        return `系统：${k}`;
      }
    }
    const base = normalizeSchemeBaseName(alg?.name || "");
    const candidates = (store.algorithms || [])
      .filter(
        (x) =>
          !BUILTIN_ALGORITHM_IDS.has(String(x?.id || "")) &&
          String(x?.task || "") === String(alg?.task || "") &&
          normalizeSchemeBaseName(x?.name || "") === base
      );
    for (const x of candidates) {
      const up = pickEffectiveParams(x?.defaultParams && typeof x.defaultParams === "object" ? x.defaultParams : {});
      if (isSameParams(runEff, up)) return `用户：${String(x?.name || "用户方案")}`;
    }
  }
  if (s === "speed") return "系统：速度优先";
  if (s === "quality") return "系统：质量优先";
  if (s === "default" || s === "__default__") return "系统内置默认参数";
  return Object.keys(runEff).length ? "用户自定义参数方案" : "系统内置默认参数";
}

function normalizeSchemeBaseName(name) {
  const n = String(name || "").trim();
  if (!n.endsWith("）")) return n;
  const i = n.lastIndexOf("（");
  if (i <= 0) return n;
  return n.slice(0, i);
}

function pickEffectiveParams(obj) {
  const src = obj && typeof obj === "object" && !Array.isArray(obj) ? obj : {};
  const out = {};
  for (const [k, v] of Object.entries(src)) {
    if (SYSTEM_PARAM_KEYS.has(k)) continue;
    out[k] = v;
  }
  return out;
}

function isSameParams(a, b) {
  const sa = JSON.stringify(Object.keys(a || {}).sort().reduce((acc, k) => ((acc[k] = (a || {})[k]), acc), {}));
  const sb = JSON.stringify(Object.keys(b || {}).sort().reduce((acc, k) => ((acc[k] = (b || {})[k]), acc), {}));
  return sa === sb;
}

const PARAM_LABELS = {
  dcp_patch: "暗通道窗口",
  dcp_omega: "去雾强度",
  dcp_t0: "最小透射率",
  clahe_clip_limit: "对比度上限",
  gamma: "伽马值",
  lowlight_gamma: "低照增强强度",
  nlm_h: "去噪强度",
  nlm_hColor: "色彩去噪强度",
  nlm_templateWindowSize: "模板窗口大小",
  nlm_searchWindowSize: "搜索窗口大小",
  bilateral_d: "邻域直径",
  bilateral_sigmaColor: "色域平滑系数",
  bilateral_sigmaSpace: "空间平滑系数",
  gaussian_sigma: "高斯标准差",
  median_ksize: "中值核大小",
  unsharp_sigma: "锐化半径",
  unsharp_amount: "锐化强度",
  laplacian_strength: "拉普拉斯锐化强度",
};

const PARAM_DESC = {
  dcp_patch: "越大去雾更明显，但细节可能变少。",
  dcp_omega: "越大去雾更强。",
  dcp_t0: "用于保护暗区，避免过度增强噪声。",
  clahe_clip_limit: "越大对比越强，过高可能放大噪声。",
  gamma: "小于 1 会提亮画面。",
  lowlight_gamma: "建议 0.5~0.8 起步。",
  nlm_h: "越大去噪越强，细节可能减少。",
  nlm_hColor: "建议与去噪强度接近。",
  nlm_templateWindowSize: "常用奇数 7。",
  nlm_searchWindowSize: "常用奇数 21。",
  bilateral_d: "影响平滑范围。",
  bilateral_sigmaColor: "影响颜色平滑强度。",
  bilateral_sigmaSpace: "影响空间平滑强度。",
  gaussian_sigma: "越大模糊越强。",
  median_ksize: "应为奇数。",
  unsharp_sigma: "控制锐化作用范围。",
  unsharp_amount: "越大边缘越锐，过高易发白边。",
  laplacian_strength: "越大锐化越明显。",
};

const SYSTEM_PARAM_KEYS = new Set([
  "metrics",
  "data_mode",
  "data_used",
  "algo_elapsed_mean",
  "algo_elapsed_sum",
  "metric_elapsed_mean",
  "metric_elapsed_sum",
  "metric_psnr_ssim_elapsed_mean",
  "metric_psnr_ssim_elapsed_sum",
  "metric_niqe_elapsed_mean",
  "metric_niqe_elapsed_sum",
  "read_ok",
  "read_fail",
  "real_algo",
  "input_dir",
  "batch_id",
  "batch_name",
  "param_scheme",
  "user_scheme_name",
]);

function prettyValue(v) {
  if (Array.isArray(v)) return v.join("、");
  if (v == null) return "-";
  if (typeof v === "object") return formatJson(v);
  return String(v);
}

function splitParamRows(paramsObj) {
  const p = paramsObj && typeof paramsObj === "object" && !Array.isArray(paramsObj) ? paramsObj : {};
  const userParamRows = [];
  const systemParamRows = [];
  for (const [key, value] of Object.entries(p)) {
    if (SYSTEM_PARAM_KEYS.has(key)) {
      systemParamRows.push({ key, label: key, value: prettyValue(value) });
      continue;
    }
    userParamRows.push({
      key,
      label: PARAM_LABELS[key] || key,
      value: prettyValue(value),
      desc: PARAM_DESC[key] || "该参数用于控制算法处理强度或范围。",
    });
  }
  return { userParamRows, systemParamRows };
}

function statusText(status) {
  if (status === "done" || status === "completed" || status === "已完成") return "已完成";
  if (status === "running" || status === "运行中") return "运行中";
  if (status === "failed" || status === "失败") return "失败";
  if (status === "queued" || status === "排队中") return "排队中";
  if (status === "canceling" || status === "取消中") return "取消中";
  if (status === "canceled" || status === "已取消") return "已取消";
  return status || "-";
}

function statusTagType(status) {
  if (status === "done" || status === "completed" || status === "已完成") return "success";
  if (status === "running" || status === "运行中") return "warning";
  if (status === "failed" || status === "失败") return "danger";
  if (status === "canceling" || status === "取消中") return "warning";
  if (status === "canceled" || status === "已取消") return "info";
  if (status === "queued" || status === "排队中") return "info";
  return "info";
}

function canCancel(row) {
  return row?.status === "排队中" || row?.status === "运行中" || row?.status === "取消中" || row?.status === "queued" || row?.status === "running" || row?.status === "canceling";
}

async function cancel(runId) {
  try {
    await ElMessageBox.confirm("确认取消该任务吗？", "取消确认", {
      type: "warning",
      confirmButtonText: "取消任务",
      cancelButtonText: "返回",
    });
    await store.cancelRun(runId);
    await refresh();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `取消失败：${e?.message || e}` });
  }
}


function parseElapsedSeconds(elapsed) {
  if (elapsed == null) return null;
  if (typeof elapsed === "number") return elapsed;
  const m = String(elapsed).match(/([\d.]+)/);
  if (!m) return null;
  const x = Number(m[1]);
  return Number.isFinite(x) ? x : null;
}

function toNumber(v) {
  const x = Number(v);
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

function buildScoringContext(allRuns) {
  const psnrs = allRuns.map((r) => toNumber(r.psnr)).filter((x) => x != null);
  const ssims = allRuns.map((r) => toNumber(r.ssim)).filter((x) => x != null);
  const niqes = allRuns.map((r) => toNumber(r.niqe)).filter((x) => x != null);
  const times = allRuns.map((r) => parseElapsedSeconds(r.elapsed)).filter((x) => x != null);

  const mmPSNR = minMax(psnrs);
  const mmSSIM = minMax(ssims);
  const mmNIQE = minMax(niqes);
  const mmTIME = minMax(times);

  const W = { psnr: 0.35, ssim: 0.35, niqe: 0.2, time: 0.1 };

  return { mmPSNR, mmSSIM, mmNIQE, mmTIME, W };
}

function scoreOne(run, ctx) {
  const psnr = toNumber(run.psnr);
  const ssim = toNumber(run.ssim);
  const niqe = toNumber(run.niqe);
  const tsec = parseElapsedSeconds(run.elapsed);

  const nPSNR = norm01(psnr, ctx.mmPSNR.min, ctx.mmPSNR.max);
  const nSSIM = norm01(ssim, ctx.mmSSIM.min, ctx.mmSSIM.max);
  const nNIQE = norm01(niqe, ctx.mmNIQE.min, ctx.mmNIQE.max);
  const nTIME = norm01(tsec, ctx.mmTIME.min, ctx.mmTIME.max);

  const okAll = [nPSNR, nSSIM, nNIQE, nTIME].every((x) => x != null);
  if (!okAll) return { score: null, reason: "指标不完整，暂不评分" };

  const score =
    ctx.W.psnr * nPSNR +
    ctx.W.ssim * nSSIM +
    ctx.W.niqe * (1 - nNIQE) +
    ctx.W.time * (1 - nTIME);

  const parts = [];
  if (nPSNR >= 0.8) parts.push("PSNR表现突出");
  if (nSSIM >= 0.8) parts.push("SSIM表现突出");
  if (nNIQE <= 0.2) parts.push("NIQE表现优秀（越低越好）");
  if (nTIME <= 0.2) parts.push("耗时表现优秀");
  if (parts.length === 0) parts.push("综合表现均衡");

  return {
    score: Number(score.toFixed(4)),
    reason: `${parts.join("，")}；评分权重：PSNR 35% + SSIM 35% + NIQE 20% + 耗时 10%`,
  };
}
// ===========================================================================//


async function refresh() {
  try {
    await store.fetchRuns();
  } catch (e) {
    ElMessage({ type: "error", message: `刷新失败：${e?.message || e}` });
  }
}

function remove(id) {
  ElMessageBox.confirm("确认从当前列表隐藏该任务吗？", "隐藏确认", {
    type: "warning",
    confirmButtonText: "隐藏",
    cancelButtonText: "取消",
  })
    .then(() => {
      hiddenIds.value.add(id);
      persistHidden();
      ElMessage({ type: "success", message: "已从当前列表隐藏" });
    })
    .catch(() => {});
}

onMounted(() => {
  refresh();
});

const detailVisible = ref(false);
const detail = ref(null);

function openDetail(row) {
  const ctx = buildScoringContext(filteredRows.value);
  const s = scoreOne(row, ctx);
  const { userParamRows, systemParamRows } = splitParamRows(row?.raw?.params ?? {});

  detail.value = {
    ...row,
    score: s.score,
    reason: s.reason,
    userParamRows,
    systemParamRows,
  };
  detailVisible.value = true;
}

</script>

<style scoped>
.page {
  padding: 24px;
  background-color: #f5f7fb;
  min-height: 100%;
}

/* Header Section */
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
  letter-spacing: -0.5px;
}

.page-subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 14px;
}

.create-btn {
  box-shadow: none;
  transition: none;
}

.create-btn:hover {
  transform: none;
  box-shadow: none;
}

/* Main Card & Toolbar */
.main-card {
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  box-shadow: none;
}

.toolbar-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.filter-item {
  width: 160px;
}

.search-input {
  width: 220px;
}

.refresh-btn {
  color: #64748b;
  border-color: #e2e8f0;
}

.action-group {
  display: flex;
  gap: 12px;
  margin-left: auto;
  align-items: center;
}

/* Table Customization */
.custom-table {
  --el-table-border-color: #f1f5f9;
  --el-table-header-bg-color: #f8fafc;
  --el-table-row-hover-bg-color: #f1f5f9;
  width: 100%;
}

.custom-table :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

.task-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.task-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #cbd5e1;
}

.task-dot.denoise { background-color: #3b82f6; }
.task-dot.deblur { background-color: #8b5cf6; }
.task-dot.dehaze { background-color: #06b6d4; }
.task-dot.sr { background-color: #f59e0b; }
.task-dot.lowlight { background-color: #ec4899; }

.algo-cell {
  display: flex;
  flex-direction: column;
}

.algo-name {
  font-weight: 600;
  color: #1e293b;
}

.algo-scheme {
  font-size: 12px;
  color: #64748b;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  padding: 0 10px;
}

.score-cell {
  background: #eef6ff;
  border-radius: 6px;
  padding: 4px 8px;
  display: inline-block;
}

.score-val {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #0369a1;
}

.score-null {
  color: #cbd5e1;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.op-btn {
  min-width: 54px;
  padding: 5px 10px;
}

.pagination-mock {
  margin-top: 20px;
  text-align: right;
  color: #94a3b8;
  font-size: 13px;
}

/* Dialog & Detail Styles */
.detail-dialog :deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

.detail-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 20px 24px;
  background-color: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.detail-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  color: #1e293b;
}

.detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-header-card {
  background: #1e293b;
  padding: 20px;
  border-radius: 12px;
  color: white;
}

.detail-main-info {
  display: flex;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
}

.detail-section-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.detail-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-card.full-width {
  grid-column: 1 / -1;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #475569;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.kv-row:last-child { border-bottom: none; }

.kv-label { color: #64748b; font-size: 13px; }
.kv-value { color: #1e293b; font-weight: 600; font-size: 13px; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.metric-box {
  background-color: #f8fafc;
  border: 1px solid #f1f5f9;
  padding: 10px;
  border-radius: 8px;
  text-align: center;
}

.metric-box.highlighted {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.metric-label { font-size: 11px; color: #64748b; margin-bottom: 2px; }
.metric-value { font-size: 16px; font-weight: 700; color: #1e293b; }

.performance-info {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.param-card {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
}

.param-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.param-name { font-weight: 700; color: #334155; font-size: 13px; }
.param-val { color: #2563eb; font-weight: 700; font-size: 13px; }
.param-desc { font-size: 11px; color: #64748b; line-height: 1.4; }

.reason-card {
  background-color: #f0fdf4;
  border-color: #dcfce7;
}

.reason-text {
  font-size: 13px;
  line-height: 1.6;
  color: #166534;
}

.error-card {
  background-color: #fef2f2;
  border-color: #fee2e2;
}

.error-pre {
  background: #450a0a;
  color: #fca5a5;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.mono { font-family: 'JetBrains Mono', monospace; }

@media (max-width: 768px) {
  .filter-item {
    width: 100%;
  }

  .search-input {
    width: 100%;
  }

  .action-group {
    width: 100%;
    justify-content: flex-end;
  }

  .detail-section-grid {
    grid-template-columns: 1fr;
  }
}
</style>
