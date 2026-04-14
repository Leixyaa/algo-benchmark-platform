
<template>
  <div class="page">
    <div class="header-section runs-page-head">
      <h2 class="title">运行任务中心</h2>
      <p class="subtitle">查看运行状态、量化指标、参数详情与综合评分结果。</p>
    </div>

    <div class="action-bar runs-action-bar">
      <div class="toolbar">
        <div class="toolbar-right">
          <el-button type="primary" size="large" class="create-btn" @click="goNewRun" :disabled="!store.user.isLoggedIn">
            新建运行任务
          </el-button>
        </div>
      </div>
    </div>

    <el-card shadow="never" class="main-card">
      <div class="toolbar-section">
        <div class="filter-group">
          <el-select v-model="statusFilter" clearable placeholder="运行状态" class="filter-item status-select">
            <el-option v-for="x in statusOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-select v-model="taskFilter" clearable placeholder="算法任务" class="filter-item task-select">
            <el-option v-for="x in taskOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-input v-model="keyword" clearable placeholder="搜索算法、数据集、参数方案" class="filter-item search-input" />
          <el-button class="refresh-btn" @click="clearFilters">清除筛选</el-button>
        </div>

        <div class="action-group">
          <el-dropdown trigger="click" :disabled="!store.user.isLoggedIn">
            <el-button size="small" :disabled="!store.user.isLoggedIn">导出数据</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="exportDoneCsv">导出已完成 CSV</el-dropdown-item>
                <el-dropdown-item @click="exportDoneXlsx">导出已完成 Excel</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" type="danger" plain @click="clearSelected" :disabled="!store.user.isLoggedIn || selectedIds.length === 0">批量清除</el-button>
          <el-button size="small" type="danger" plain @click="clearDone" :disabled="!store.user.isLoggedIn">清理已完成</el-button>
        </div>
      </div>

      <el-table
        :data="filteredRows"
        class="custom-table"
        style="width: 100%"
        stripe
        size="small"
        :row-key="getRunId"
        v-loading="store.loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="46" :selectable="canBatchClearRow" reserve-selection />
        <el-table-column prop="task" label="算法任务" width="110">
          <template #default="{ row }">
            <div class="task-cell">
              <span class="task-dot" :class="row.taskType"></span>
              {{ row.task }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="dataset" label="评测数据集" min-width="150" show-overflow-tooltip />
        <el-table-column prop="algorithm" label="运行算法" min-width="180">
          <template #default="{ row }">
            <div class="algo-cell">
              <span class="algo-name">{{ row.algorithm }}</span>
              <span class="algo-scheme">{{ row.paramSchemeText }}</span>
              <span class="algo-auth" :class="`algo-auth--${authenticityType(row)}`">{{ authenticityLabel(row) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="运行状态" width="120" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="`status-pill--${statusTagType(row.status)}`">{{ statusText(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="综合评分" width="100" align="center">
          <template #default="{ row }">
            <div class="score-wrap">
              <span v-if="Number.isFinite(row.score) && isRealDatasetRun(row)" class="score-val">{{ row.score }}</span>
              <span v-else-if="isActiveStatus(row.status)" class="score-pending">计算中</span>
              <span v-else class="score-null">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" type="primary" plain @click="openDetail(row)" :disabled="!store.user.isLoggedIn">详情</el-button>
              <el-button v-if="canCancel(row)" size="small" type="warning" plain @click="cancel(row.id)" :disabled="!store.user.isLoggedIn">取消</el-button>
              <el-button v-if="!isActiveStatus(row.status)" size="small" type="danger" plain @click="remove(row.id)" :disabled="!store.user.isLoggedIn">删除</el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无运行记录" :image-size="120" />
        </template>
      </el-table>

      <div class="pagination-mock">共 {{ filteredRows.length }} 条记录</div>
    </el-card>

    <el-dialog v-model="detailVisible" title="运行任务详情" width="860px" class="detail-dialog" destroy-on-close>
      <div v-if="detail" class="detail-container">
        <div class="detail-header-card">
          <div class="detail-main-info">
            <div class="info-item">
              <span class="info-label">运行编号</span>
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
            <div class="info-item">
              <span class="info-label">开始时间</span>
              <span class="info-value">{{ detail.startedAt || "-" }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">完成时间</span>
              <span class="info-value">{{ detail.finishedAt || "-" }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section-grid">
          <div class="detail-card">
            <div class="card-title">基本配置</div>
            <div class="card-content">
              <div class="kv-row"><span class="kv-label">算法大类</span><span class="kv-value">{{ detail.task }}</span></div>
              <div class="kv-row"><span class="kv-label">数据集</span><span class="kv-value">{{ detail.dataset }}</span></div>
              <div class="kv-row"><span class="kv-label">算法名称</span><span class="kv-value">{{ detail.algorithm }}</span></div>
              <div v-if="detail.datasetMissing || detail.algorithmMissing" class="kv-row">
                <span class="kv-label">关联资源</span>
                <span class="kv-value danger-text">
                  {{ detail.datasetMissing ? "数据集已删除" : "" }}{{ detail.datasetMissing && detail.algorithmMissing ? "，" : "" }}{{ detail.algorithmMissing ? "算法已删除" : "" }}
                </span>
              </div>
              <div class="kv-row"><span class="kv-label">参数方案</span><span class="kv-value">{{ detail.paramSchemeText || '-' }}</span></div>
              <div class="kv-row"><span class="kv-label">执行口径</span><span class="kv-value"><span class="algo-auth" :class="`algo-auth--${authenticityType(detail)}`">{{ authenticityLabel(detail) }}</span></span></div>
              <div class="kv-row"><span class="kv-label">实际算法</span><span class="kv-value">{{ detail.raw?.params?.real_algo || '-' }}</span></div>
              <div class="kv-row"><span class="kv-label">输入目录</span><span class="kv-value">{{ detail.raw?.params?.input_dir || '-' }}</span></div>
            </div>
          </div>

          <div class="detail-card">
            <div class="card-title">量化指标</div>
            <div class="card-content">
              <div class="metric-grid">
                <div class="metric-box"><div class="metric-label">PSNR</div><div class="metric-value">{{ detail.psnr ?? '-' }}</div></div>
                <div class="metric-box"><div class="metric-label">SSIM</div><div class="metric-value">{{ detail.ssim ?? '-' }}</div></div>
                <div class="metric-box"><div class="metric-label">NIQE</div><div class="metric-value">{{ detail.niqe ?? '-' }}</div></div>
                <div class="metric-box highlighted"><div class="metric-label">综合评分</div><div class="metric-value">{{ detailScoreText(detail) }}</div></div>
              </div>
              <div v-if="(detail.customMetrics || []).length" class="metric-grid custom-metric-grid">
                <div v-for="item in detail.customMetrics || []" :key="`metric-${item.key}`" class="metric-box custom-metric-box">
                  <div class="metric-label">{{ item.label }}</div>
                  <div class="metric-value">{{ formatMetricNumber(item.value) }}</div>
                </div>
              </div>
              <div class="performance-info">
                <div class="perf-item"><span>评测模式:</span> <strong>{{ evalModeLabel(detail.raw) }}</strong></div>
                <div class="perf-item"><span>数据集总量:</span> <strong>{{ detail.raw?.record?.pair_total ?? detail.raw?.params?.pair_total ?? '-' }}</strong></div>
                <div class="perf-item"><span>总耗时:</span> <strong>{{ detail.elapsed ?? '-' }}</strong></div>
                <div class="perf-item"><span>样本数:</span> <strong>{{ detail.raw?.params?.data_used ?? '-' }}</strong></div>
                <div class="perf-item"><span>读取成功:</span> <strong>{{ detail.raw?.params?.read_ok ?? '-' }}</strong></div>
                <div class="perf-item"><span>读取失败:</span> <strong>{{ detail.raw?.params?.read_fail ?? '-' }}</strong></div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="detail.reason" class="detail-card full-width reason-card">
          <div class="card-title">推荐分析</div>
          <div class="card-content">
            <div class="reason-text">{{ detail.reason }}</div>
          </div>
        </div>

        <div v-if="detail.raw?.error || detail.raw?.error_code" class="detail-card full-width error-card">
          <div class="card-title">异常报告</div>
          <div class="card-content">
            <pre class="error-pre">{{ formatRunError(detail.raw) }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
export default { name: "Runs" };
</script>
<script setup>
import { computed, onActivated, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { TASK_LABEL_BY_TYPE, TASK_TYPE_BY_LABEL, useAppStore } from "../stores/app";
import { authFetch } from "../api/http";

const router = useRouter();
const store = useAppStore();

/** 切回任务页时若距上次拉取较近则不再请求，避免「来回切页总在等接口」 */
const lastRunsFetchedAt = ref(0);
const RUNS_STALE_MS = 25000;

const HIDDEN_KEY = "hiddenRunIds_v1";
const hiddenIds = ref(new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || "[]")));
const selectedIds = ref([]);
const statusFilter = ref("");
const taskFilter = ref("");
const keyword = ref("");
const detailVisible = ref(false);
const detail = ref(null);

const statusOptions = [
  { value: "queued", label: "排队中" },
  { value: "running", label: "运行中" },
  { value: "done", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "canceling", label: "取消中" },
  { value: "canceled", label: "已取消" },
];

const PARAM_LABELS = {
  dcp_patch: "暗通道窗口",
  dcp_omega: "去雾强度",
  dcp_t0: "最小透射率",
  clahe_clip_limit: "对比度上限",
  gamma: "Gamma 值",
  lowlight_gamma: "低照度增强强度",
  nlm_h: "去噪强度",
  nlm_hColor: "彩色去噪强度",
  nlm_templateWindowSize: "模板窗口大小",
  nlm_searchWindowSize: "搜索窗口大小",
  bilateral_d: "邻域直径",
  bilateral_sigmaColor: "颜色域平滑系数",
  bilateral_sigmaSpace: "空间域平滑系数",
  gaussian_sigma: "高斯标准差",
  median_ksize: "中值核大小",
  unsharp_sigma: "锐化半径",
  unsharp_amount: "锐化强度",
  laplacian_strength: "拉普拉斯锐化强度",
};

const PARAM_DESC = {
  dcp_patch: "越大去雾越明显，但细节可能减少。",
  dcp_omega: "越大去雾越强。",
  dcp_t0: "用于保护暗区，避免过度增强噪声。",
  clahe_clip_limit: "越大对比越强，过高可能放大噪声。",
  gamma: "小于 1 会提亮画面。",
  lowlight_gamma: "建议从 0.5 到 0.8 起步。",
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
  unsharp_amount: "越大边缘越锐，过高容易产生白边。",
  laplacian_strength: "越大锐化越明显。",
};

const SYSTEM_PARAM_KEYS = new Set([
  "metrics","data_mode","data_used","algo_elapsed_mean","algo_elapsed_sum","metric_elapsed_mean","metric_elapsed_sum",
  "metric_psnr_ssim_elapsed_mean","metric_psnr_ssim_elapsed_sum","metric_niqe_elapsed_mean","metric_niqe_elapsed_sum",
  "metric_custom_elapsed_mean","metric_custom_elapsed_sum","read_ok","read_fail","real_algo","input_dir",
  "eval_mode","sample_limit","pair_total",
  "batch_id","batch_name","param_scheme","user_scheme_name",
]);

const taskOptions = computed(() => Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label })));

const rows = computed(() => {
  const dsMap = new Map((store.datasets ?? []).map((d) => [d.id, d.name]));
  const algoMap = new Map((store.algorithms ?? []).map((a) => [a.id, a.name]));
  const ctxCache = new Map();
  return (store.runs ?? []).filter((r) => !hiddenIds.value.has(r.id)).map((r) => {
    const datasetId = String(r.datasetId || "").trim();
    const algorithmId = String(r.algorithmId || "").trim();
    const datasetName = dsMap.get(datasetId);
    const algorithmName = algoMap.get(algorithmId);
    const datasetMissing = Boolean(datasetId) && !datasetName;
    const algorithmMissing = Boolean(algorithmId) && !algorithmName;
    const base = {
      ...r,
      name: r.name || `${r.task || "任务"} Run`,
      dataset: datasetName ?? (datasetId ? `关联数据集已删除（${datasetId}）` : "-"),
      algorithm: algorithmName ?? (algorithmId ? `关联算法已删除（${algorithmId}）` : "-"),
      datasetMissing,
      algorithmMissing,
      paramSchemeText: resolveParamSchemeText(r),
    };
    const key = comparableGroupKey(base);
    if (!ctxCache.has(key)) ctxCache.set(key, buildScoringContext(store.runs ?? [], base));
    const ctx = ctxCache.get(key);
    const s = scoreOne(base, ctx);
    return { ...base, score: s.score };
  });
});

const filteredRows = computed(() => {
  const kw = String(keyword.value || "").trim().toLowerCase();
  return (rows.value ?? []).filter((r) => {
    if (statusFilter.value && normalizeStatusFilterValue(r.status) !== statusFilter.value) return false;
    if (taskFilter.value && normalizeRunTaskType(r) !== taskFilter.value) return false;
    if (!kw) return true;
    const hay = `${r.dataset ?? ""} ${r.algorithm ?? ""} ${r.task ?? ""} ${r.paramSchemeText ?? ""}`.toLowerCase();
    return hay.includes(kw);
  });
});

function persistHidden() { localStorage.setItem(HIDDEN_KEY, JSON.stringify(Array.from(hiddenIds.value))); }
function goNewRun() { router.push("/new-run"); }
function clearFilters() { statusFilter.value = ""; taskFilter.value = ""; keyword.value = ""; }
function downloadFile(blob, filename) { const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = filename; a.rel = "noopener"; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); }
async function exportDone(format, filename) {
  const res = await authFetch("/runs/export", { query: { format, status: "done" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `导出失败(${res.status})`);
  }
  const blob = await res.blob();
  downloadFile(blob, filename);
}

async function exportDoneCsv() { try { await exportDone("csv", "runs_done.csv"); } catch (e) { ElMessage({ type: "error", message: `导出失败：${e?.message || e}` }); } }
async function exportDoneXlsx() { try { await exportDone("xlsx", "runs_done.xlsx"); } catch (e) { ElMessage({ type: "error", message: `导出失败：${e?.message || e}` }); } }

async function clearDone() {
  try {
    await ElMessageBox.confirm("确认清理所有已完成任务吗？", "清理确认", { type: "warning", confirmButtonText: "清理", cancelButtonText: "取消" });
    const res = await authFetch("/runs/clear", { method: "POST", query: { status: "done" } });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    ElMessage({ type: "success", message: `已清理 ${data.deleted} 条已完成任务` });
    await refresh();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `清理失败：${e?.message || e}` });
  }
}

function canBatchClearRow(row) { return !isActiveStatus(row?.status); }
function getRunId(row) {
  const raw = row && typeof row === "object" ? row : {};
  return String(raw.id || raw.run_id || raw?.raw?.run_id || "").trim();
}
function handleSelectionChange(selection) {
  selectedIds.value = (selection || []).map((row) => getRunId(row)).filter(Boolean);
}

async function clearSelected() {
  if (!selectedIds.value.length) {
    ElMessage({ type: "warning", message: "请先勾选要清除的任务" });
    return;
  }
  try {
    await ElMessageBox.confirm(`确认批量清除已勾选的 ${selectedIds.value.length} 条任务吗？运行中和排队中的任务不会被清除。`, "批量清除确认", {
      type: "warning",
      confirmButtonText: "批量清除",
      cancelButtonText: "取消",
    });
    const runIds = Array.from(new Set(selectedIds.value.map((id) => String(id || "").trim()).filter(Boolean)));
    const res = await authFetch("/runs/batch-clear", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds }),
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    selectedIds.value = [];
    const deleted = Number(data?.deleted || 0);
    const skipped = Number(data?.skipped || 0);
    if (deleted <= 0 && skipped > 0) {
      ElMessage({
        type: "warning",
        message: `未删除任何任务（跳过 ${skipped} 条）。请确认这些任务属于当前账号，且不是排队/运行中。`,
      });
    } else {
      ElMessage({ type: "success", message: `已清除 ${deleted} 条任务${skipped ? `，跳过 ${skipped} 条` : ""}` });
    }
    await refresh();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `批量清除失败：${e?.message || e}` });
  }
}

function formatJson(v) { try { return JSON.stringify(v ?? null, null, 2); } catch { return String(v ?? ""); } }
function formatMetricNumber(v) { if (v == null || v === "") return "-"; const x = Number(v); if (!Number.isFinite(x)) return String(v); return x.toFixed(4); }
function detailScoreText(run) { if (!isRealDatasetRun(run)) return "仅真实数据评测"; return Number.isFinite(run?.score) ? run.score : "-"; }

function formatRunError(raw) {
  if (!raw || typeof raw !== "object") return "-";
  const code = raw.error_code || raw.errorCode || "";
  const msg = raw.error || "";
  const detail = raw.error_detail || raw.errorDetail || null;
  const head = code ? `${code}${msg ? `: ${msg}` : ""}` : msg || "-";
  if (!detail) return head;
  return `${head}\n${formatJson(detail)}`;
}

function extractSchemeDisplayName(fullName, baseName = "") {
  const full = String(fullName || "").trim();
  const base = String(baseName || "").trim();
  if (!full) return "用户方案";
  if (base && full.startsWith(base)) {
    const rest = full.slice(base.length).trim();
    if (rest) return rest.replace(/^[（(]\s*/, "").replace(/\s*[）)]$/, "").trim() || full;
  }
  const m = full.match(/[（(]([^（）()]+)[）)]$/);
  return m?.[1]?.trim() || full;
}

function normalizeSchemeBaseName(name) {
  const n = String(name || "").trim();
  if (!n.endsWith("版")) return n;
  const i = n.lastIndexOf("版");
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

function isBuiltinAlgorithm(alg) { return String(alg?.raw?.owner_id || "") === "system" && String(alg?.id || "").startsWith("alg_"); }
function isSameParams(a, b) { const sa = JSON.stringify(Object.keys(a || {}).sort().reduce((acc, k) => ((acc[k] = (a || {})[k]), acc), {})); const sb = JSON.stringify(Object.keys(b || {}).sort().reduce((acc, k) => ((acc[k] = (b || {})[k]), acc), {})); return sa === sb; }

function resolveParamSchemeText(run) {
  const p = run?.raw?.params && typeof run.raw.params === "object" && !Array.isArray(run.raw.params) ? run.raw.params : {};
  const s = String(p.param_scheme || "").trim().toLowerCase();
  if (String(p.user_scheme_name || "").trim()) return `用户：${extractSchemeDisplayName(String(p.user_scheme_name).trim(), run?.algorithm || "")}`;
  if (s.startsWith("user:")) return `用户：${extractSchemeDisplayName(String(p.param_scheme || "").trim().slice(5), run?.algorithm || "")}`;
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
    const candidates = (store.algorithms || []).filter((x) => !isBuiltinAlgorithm(x) && String(x?.task || "") === String(alg?.task || "") && normalizeSchemeBaseName(x?.name || "") === base);
    for (const x of candidates) {
      const up = pickEffectiveParams(x?.defaultParams && typeof x.defaultParams === "object" ? x.defaultParams : {});
      if (isSameParams(runEff, up)) return `用户：${extractSchemeDisplayName(String(x?.name || "用户方案"), alg?.name || run?.algorithm || "")}`;
    }
  }
  if (s === "speed") return "系统：速度优先";
  if (s === "quality") return "系统：质量优先";
  if (s === "default" || s === "__default__") return "系统内置默认参数";
  return Object.keys(runEff).length ? "用户自定义参数方案" : "系统内置默认参数";
}
function prettyValue(v) { if (Array.isArray(v)) return v.join("、"); if (v == null) return "-"; if (typeof v === "object") return formatJson(v); return String(v); }

function splitParamRows(paramsObj) {
  const p = paramsObj && typeof paramsObj === "object" && !Array.isArray(paramsObj) ? paramsObj : {};
  const userParamRows = [];
  const systemParamRows = [];
  for (const [key, value] of Object.entries(p)) {
    if (SYSTEM_PARAM_KEYS.has(key)) { systemParamRows.push({ key, label: key, value: prettyValue(value) }); continue; }
    userParamRows.push({ key, label: PARAM_LABELS[key] || key, value: prettyValue(value), desc: PARAM_DESC[key] || "当前参数暂无补充说明，可结合算法原理与预览结果进行调整。" });
  }
  return { userParamRows, systemParamRows };
}

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

function normalizeStatusFilterValue(status) {
  const text = statusText(status);
  if (text === "已完成") return "done";
  if (text === "运行中") return "running";
  if (text === "失败") return "failed";
  if (text === "排队中") return "queued";
  if (text === "取消中") return "canceling";
  if (text === "已取消") return "canceled";
  return String(status ?? "").trim().toLowerCase();
}

function normalizeRunTaskType(run) {
  const rawType = String(run?.taskType || "").trim();
  if (rawType) return rawType;
  const taskLabel = String(run?.task || "").trim();
  return TASK_TYPE_BY_LABEL[taskLabel] || taskLabel;
}

function statusTagType(status) {
  const text = statusText(status);
  if (text === "已完成") return "success";
  if (text === "运行中") return "warning";
  if (text === "失败") return "danger";
  if (text === "取消中") return "warning";
  if (text === "已取消") return "info";
  if (text === "排队中") return "info";
  return "info";
}

function canCancel(row) { const text = statusText(row?.status); return text === "排队中" || text === "运行中" || text === "取消中"; }
function isActiveStatus(status) { const text = statusText(status); return text === "排队中" || text === "运行中" || text === "取消中"; }
function getDataMode(row) { return String(row?.raw?.params?.data_mode || row?.raw?.record?.data_mode || "").trim(); }
function isRealDatasetRun(row) { return getDataMode(row) === "real_dataset"; }

function authenticityType(row) {
  const mode = getDataMode(row);
  if (mode === "real_dataset") return "real";
  if (mode === "synthetic_no_dataset") return "demo";
  if (mode === "dataset_read_failed_or_empty") return "fallback";
  if (mode === "paired_images" || mode === "paired_videos") return "real";
  return "unknown";
}

function authenticityLabel(row) {
  const mode = getDataMode(row);
  if (mode === "real_dataset") return "真实数据评测";
  if (mode === "paired_images") return "真实图像配对";
  if (mode === "paired_videos") return "真实视频配对";
  if (mode === "synthetic_no_dataset") return "演示兜底结果";
  if (mode === "dataset_read_failed_or_empty") return "读取失败兜底";
  return "执行口径未标注";
}

function evalModeLabel(raw) {
  const mode = String(raw?.params?.eval_mode || raw?.record?.eval_mode || "").trim().toLowerCase();
  if (mode === "full") return "全量评测";
  if (mode === "preview") return "快速预览(前5个)";
  return "-";
}

async function cancel(runId) {
  try {
    await ElMessageBox.confirm("确认取消该任务吗？", "取消确认", { type: "warning", confirmButtonText: "取消任务", cancelButtonText: "返回" });
    await store.cancelRun(runId);
    ElMessage({ type: "success", message: "已提交取消请求，请稍候状态刷新" });
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

function toNumber(v) { const x = Number(v); return Number.isFinite(x) ? x : null; }
function minMax(values) { const nums = values.filter((x) => Number.isFinite(x)); if (nums.length === 0) return { min: null, max: null }; return { min: Math.min(...nums), max: Math.max(...nums) }; }
function norm01(x, min, max) { if (!Number.isFinite(x) || !Number.isFinite(min) || !Number.isFinite(max)) return null; if (max === min) return 1.0; return (x - min) / (max - min); }

function comparableTaskKey(run) { return normalizeRunTaskType(run); }

function comparableGroupKey(run) {
  return `${comparableTaskKey(run)}::${String(run?.datasetId || "").trim()}`;
}

function buildScoringContext(allRuns, targetRun) {
  const targetKey = comparableGroupKey(targetRun);
  const realRuns = (allRuns || []).filter((r) => isRealDatasetRun(r) && comparableGroupKey(r) === targetKey);
  const psnrs = realRuns.map((r) => toNumber(r.psnr)).filter((x) => x != null);
  const ssims = realRuns.map((r) => toNumber(r.ssim)).filter((x) => x != null);
  const niqes = realRuns.map((r) => toNumber(r.niqe)).filter((x) => x != null);
  return {
    mmPSNR: minMax(psnrs),
    mmSSIM: minMax(ssims),
    mmNIQE: minMax(niqes),
    sampleCount: realRuns.length,
    W: { psnr: 0.39, ssim: 0.39, niqe: 0.22 },
  };
}

function scoreOne(run, ctx) {
  if (!isRealDatasetRun(run)) return { score: null, reason: `${authenticityLabel(run)}，该结果仅用于流程演示，不参与真实性能评分` };
  const psnr = toNumber(run.psnr);
  const ssim = toNumber(run.ssim);
  const niqe = toNumber(run.niqe);
  const nPSNR = norm01(psnr, ctx.mmPSNR.min, ctx.mmPSNR.max);
  const nSSIM = norm01(ssim, ctx.mmSSIM.min, ctx.mmSSIM.max);
  const nNIQE = norm01(niqe, ctx.mmNIQE.min, ctx.mmNIQE.max);
  const okAll = [nPSNR, nSSIM, nNIQE].every((x) => x != null);
  if (!okAll) return { score: null, reason: "同任务同数据集下指标不完整，暂不评分" };
  const score = ctx.W.psnr * nPSNR + ctx.W.ssim * nSSIM + ctx.W.niqe * (1 - nNIQE);
  const parts = [];
  if (nPSNR >= 0.8) parts.push("PSNR 表现优秀");
  if (nSSIM >= 0.8) parts.push("SSIM 表现优秀");
  if (nNIQE <= 0.2) parts.push("NIQE 表现优秀（越低越好）");
  if (parts.length === 0) parts.push("综合表现均衡");
  return { score: Number(score.toFixed(4)), reason: `${parts.join("；")}；评分范围：同任务同数据集（样本池 ${ctx.sampleCount || 0} 条）；评分权重：PSNR 39% + SSIM 39% + NIQE 22%；耗时请单独查看。` };
}

async function refresh() {
  try {
    await store.fetchRuns();
    lastRunsFetchedAt.value = Date.now();
  } catch (e) {
    ElMessage({ type: "error", message: `刷新失败：${e?.message || e}` });
  }
}

async function remove(id) {
  const runId = String(id || "").trim();
  if (!runId) {
    ElMessage({ type: "warning", message: "任务 ID 缺失，无法删除，请先刷新页面后重试" });
    return;
  }
  try {
    await ElMessageBox.confirm("确认删除该任务记录吗？删除后不可恢复。", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    const res = await authFetch("/runs/batch-clear", {
      method: "POST",
      body: JSON.stringify({ run_ids: [runId] }),
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    if (Number(data?.deleted || 0) <= 0) {
      ElMessage({ type: "warning", message: "当前任务状态不可删除，请稍后重试" });
      return;
    }
    hiddenIds.value.delete(runId);
    persistHidden();
    if (detail.value?.id === runId) detailVisible.value = false;
    ElMessage({ type: "success", message: "任务已删除" });
    await refresh();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `删除失败：${e?.message || e}` });
  }
}

function openDetail(row) {
  const ctx = buildScoringContext(store.runs ?? [], row);
  const s = scoreOne(row, ctx);
  const { userParamRows, systemParamRows } = splitParamRows(row?.raw?.params ?? {});
  detail.value = { ...row, score: s.score, reason: s.reason, userParamRows, systemParamRows };
  detailVisible.value = true;
}

onMounted(() => {
  refresh();
});

onActivated(() => {
  if (!lastRunsFetchedAt.value) return;
  if (Date.now() - lastRunsFetchedAt.value < RUNS_STALE_MS) return;
  refresh();
});
</script>

<style scoped>
.page {
  padding: 24px;
  background: #f8fbff;
  min-height: 100%;
  max-width: 1400px;
  margin: 0 auto;
}

.header-section.runs-page-head {
  margin-bottom: 8px;
}

.runs-page-head .title {
  margin: 0 0 12px;
  font-size: 28px;
  font-weight: 700;
  color: #1f2f57;
  line-height: 1.2;
}

.runs-page-head .subtitle {
  margin: 0;
  max-width: 860px;
  color: #6a7ca9;
  font-size: 14px;
  line-height: 1.6;
}

.action-bar {
  background: #f8faff;
  padding: 20px 28px;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.runs-action-bar .toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.main-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  padding: 24px;
  background: white;
}

.detail-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: white;
  overflow: hidden;
}

.toolbar-section {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-group {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  flex: 1;
}

.action-group {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-item {
  min-width: 180px;
  border-radius: 8px;
}

.search-input {
  min-width: 300px;
}

.create-btn {
  border-radius: 10px;
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.create-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.refresh-btn, .action-group .el-button {
  border-radius: 8px;
  font-size: 13px;
  padding: 6px 16px;
  transition: all 0.3s ease;
}

.refresh-btn:hover, .action-group .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.custom-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.custom-table :deep(.el-table__header th) {
  background-color: #f8fafc;
  font-weight: 600;
  color: #1f2f57;
  padding: 12px 16px;
}

.custom-table :deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

.custom-table :deep(.el-table__row:hover) {
  background-color: #f8fafc !important;
}

.task-cell, .algo-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
  margin-right: 8px;
  background: #3b82f6;
}

.algo-name {
  font-weight: 700;
  color: #1d355e;
  font-size: 14px;
}

.algo-scheme {
  color: #7b8aa5;
  font-size: 12px;
  line-height: 1.4;
}

.algo-auth {
  align-self: flex-start;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  margin-top: 4px;
}

.algo-auth--real {
  background: #dcfce7;
  color: #15803d;
}

.algo-auth--demo, .algo-auth--fallback, .algo-auth--unknown {
  background: #eff6ff;
  color: #2563eb;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 84px;
  padding: 6px 16px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 13px;
  transition: all 0.2s ease;
}

.status-pill--success {
  background: #dcfce7;
  color: #15803d;
}

.status-pill--warning {
  background: #fef3c7;
  color: #b45309;
}

.status-pill--danger {
  background: #fee2e2;
  color: #dc2626;
}

.status-pill--info {
  background: #e0f2fe;
  color: #0369a1;
}

.score-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
}

.score-val {
  color: #2563eb;
  font-weight: 800;
  font-size: 16px;
}

.score-null, .score-pending, .pagination-mock {
  color: #7b8aa5;
  font-size: 13px;
}

.row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
}

.row-actions .el-button {
  border-radius: 6px;
  font-size: 12px;
  padding: 4px 12px;
  transition: all 0.3s ease;
  min-width: 60px;
}

.row-actions .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.pagination-mock {
  margin-top: 20px;
  text-align: right;
  font-size: 13px;
  padding: 12px 0;
  border-top: 1px solid #e2e8f0;
}

.detail-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e2e8f0;
  padding: 20px 24px;
}

.detail-dialog :deep(.el-dialog__title) {
  font-size: 18px;
  font-weight: 700;
  color: #1f2f57;
}

.detail-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-header-card {
  background: #1f2a44;
  color: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.detail-main-info {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}

.info-item .el-tag {
  margin-top: 4px;
}

.detail-section-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.card-title {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 700;
  color: #203250;
  padding: 16px 20px 0;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.card-content {
  color: #203250;
  padding: 20px;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #eef2f7;
  align-items: center;
}

.danger-text {
  color: #d9534f;
}

.kv-row:last-child {
  border-bottom: none;
}

.kv-label {
  font-weight: 500;
  color: #6b7a96;
  font-size: 13px;
}

.kv-value {
  color: #203250;
  font-weight: 600;
  font-size: 13px;
  text-align: right;
  flex: 1;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.custom-metric-grid {
  margin-top: 16px;
}

.metric-box {
  background: #f8fbff;
  border: 1px solid #e6eef8;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.metric-box:hover {
  border-color: #2f6bff;
  box-shadow: 0 4px 12px rgba(47, 107, 255, 0.1);
  transform: translateY(-1px);
}

.metric-box.highlighted {
  background: #eef5ff;
  border-color: #bfd6ff;
}

.metric-label {
  color: #6b7a96;
  font-size: 13px;
  font-weight: 500;
}

.metric-value {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 700;
  color: #2563eb;
}

.performance-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eef2f7;
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.perf-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.perf-item span {
  color: #6b7a96;
}

.perf-item strong {
  color: #203250;
  font-weight: 600;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.param-card {
  background: #f8fbff;
  border: 1px solid #e6eef8;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.param-card:hover {
  border-color: #2f6bff;
  box-shadow: 0 4px 12px rgba(47, 107, 255, 0.1);
  transform: translateY(-1px);
}

.param-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  align-items: center;
}

.param-name {
  color: #203250;
  font-weight: 600;
  font-size: 13px;
  flex: 1;
}

.param-val {
  color: #2563eb;
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}

.param-desc {
  color: #6b7a96;
  font-size: 12px;
  line-height: 1.4;
}

.params-empty, .reason-text, .error-pre {
  color: #4f6185;
  font-size: 13px;
  line-height: 1.6;
}

.reason-card {
  background: #effdf4;
  border-color: #dcfce7;
}

.error-card {
  background: #fff7f7;
  border-color: #fee2e2;
}

.error-pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: Consolas, Monaco, monospace;
  padding: 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  border: 1px solid #fee2e2;
  max-height: 300px;
  overflow-y: auto;
}

.mono {
  font-family: Consolas, Monaco, monospace;
}

.full-width {
  grid-column: 1 / -1;
}

/* 响应式设计 */
@media (max-width: 980px) {
  .detail-section-grid, .detail-main-info, .params-grid {
    grid-template-columns: 1fr;
  }
  
  .toolbar-section {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-group {
    order: 2;
  }
  
  .action-group {
    order: 1;
    justify-content: flex-end;
  }
  
  .filter-item, .search-input {
    min-width: 100%;
  }
  
  .row-actions {
    flex-direction: column;
    align-items: stretch;
  }
  
  .row-actions .el-button {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .page {
    padding: 16px;
  }

  .runs-page-head .title {
    font-size: 24px;
  }
  
  .main-card {
    padding: 16px;
  }
  
  .detail-dialog :deep(.el-dialog) {
    width: 95% !important;
    margin: 20px auto !important;
  }
  
  .detail-dialog :deep(.el-dialog__header),
  .detail-dialog :deep(.el-dialog__body) {
    padding: 16px;
  }
}
</style>
