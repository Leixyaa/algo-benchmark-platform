<template>
  <div class="page">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="header">
          <div class="headerLeft">
            <div class="titleRow">
              <h2 class="title">运行中心</h2>
              <el-tag size="small" type="info">{{ filteredRows.length }} 条</el-tag>
            </div>
            <div class="subtitle">支持查看 Run 状态、导出结果与失败排查</div>
          </div>
          <div class="headerRight">
            <el-button type="primary" @click="goNewRun">新建 Run</el-button>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <div class="filters">
          <el-select v-model="statusFilter" clearable size="small" placeholder="按状态筛选" style="width: 130px">
            <el-option v-for="x in statusOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-select v-model="taskFilter" clearable size="small" placeholder="按任务筛选" style="width: 140px">
            <el-option v-for="x in taskOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-input
            v-model="keyword"
            clearable
            size="small"
            placeholder="搜索 Run ID / 数据集 / 算法"
            style="width: 260px"
          />
        </div>

        <div class="actions">
          <el-button-group>
            <el-button size="small" @click="refresh">刷新</el-button>
            <el-button size="small" @click="mockOne">创建示例</el-button>
          </el-button-group>
          <el-button-group>
            <el-button size="small" @click="exportDoneCsv">导出已完成CSV</el-button>
            <el-button size="small" @click="exportDoneXlsx">导出已完成Excel</el-button>
          </el-button-group>
          <el-button size="small" type="danger" @click="clearDone">清理已完成</el-button>
        </div>
      </div>

      <el-table :data="filteredRows" size="small" stripe border style="width: 100%" row-key="id">
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="Run ID" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="task" label="任务" width="110" show-overflow-tooltip />
        <el-table-column prop="dataset" label="数据集" min-width="160" show-overflow-tooltip />
        <el-table-column prop="algorithm" label="算法" min-width="160" show-overflow-tooltip />

        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="综合分" width="100" align="right">
          <template #default="{ row }">
            <span>{{ row.score ?? "-" }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="180" />

        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="rowActions">
              <el-button size="small" @click="openDetail(row)">详情</el-button>
              <el-button v-if="canCancel(row)" size="small" type="warning" @click="cancel(row.id)">取消</el-button>
              <el-button size="small" type="danger" plain @click="remove(row.id)">隐藏</el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty">
            <div class="emptyTitle">暂无运行记录</div>
            <div class="emptySub">请新建 Run 或调整筛选条件</div>
          </div>
        </template>
      </el-table>

      <el-dialog v-model="detailVisible" title="运行详情" width="760px">
        <div v-if="detail" class="detail">
          <el-descriptions size="small" :column="2" border>
            <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTagType(detail.status)">
                {{ statusText(detail.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Run ID">
              <span class="mono">{{ detail.id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ detail.createdAt }}</el-descriptions-item>
            <el-descriptions-item label="数据集">{{ detail.dataset }}</el-descriptions-item>
            <el-descriptions-item label="算法">{{ detail.algorithm }}</el-descriptions-item>
          </el-descriptions>

          <div class="detailGrid">
            <div class="detailBlock">
              <div class="blockTitle">参数</div>
              <pre class="code codeDark">{{ formatJson(detail.raw?.params ?? {}) }}</pre>
            </div>
            <div class="detailBlock">
              <div class="blockTitle">指标与性能</div>
              <el-descriptions size="small" :column="1" border>
                <el-descriptions-item label="PSNR">{{ detail.psnr ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="SSIM">{{ detail.ssim ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="NIQE">{{ detail.niqe ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="耗时">{{ detail.elapsed ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="样本数">{{ detail.raw?.params?.data_used ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="算法均耗时(s)">{{ formatNum(detail.raw?.params?.algo_elapsed_mean) }}</el-descriptions-item>
                <el-descriptions-item label="指标均耗时(s)">{{ formatNum(detail.raw?.params?.metric_elapsed_mean) }}</el-descriptions-item>
                <el-descriptions-item label="综合分">{{ detail.score ?? "-" }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>

          <div v-if="detail.reason" class="reason">
            <div class="blockTitle">推荐理由</div>
            <div class="reasonText">{{ detail.reason }}</div>
          </div>

          <div v-if="detail.raw?.error || detail.raw?.error_code" class="errorBlock">
            <div class="blockTitle">错误码/错误详情</div>
            <pre class="code codeError">{{ formatRunError(detail.raw) }}</pre>
          </div>
        </div>

        <template #footer>
          <el-button @click="detailVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";

const router = useRouter();
const store = useAppStore();

const HIDDEN_KEY = "hiddenRunIds_v1";
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
  if (!confirm("确认清理 Redis 中所有已完成 Run 吗？")) return;

  try {
    const res = await fetch("http://127.0.0.1:8000/runs/clear?status=done", {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));

    alert(`已清理 ${data.deleted} 条已完成 Run`);
    await refresh();
  } catch (e) {
    alert(`清理失败：${e?.message || e}`);
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
    const hay = `${r.id ?? ""} ${r.dataset ?? ""} ${r.algorithm ?? ""} ${r.name ?? ""}`.toLowerCase();
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
  if (!confirm("确认取消该 Run 吗？")) return;
  try {
    await store.cancelRun(runId);
    await refresh();
  } catch (e) {
    alert(`取消失败：${e?.message || e}`);
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
    alert(`刷新失败：${e?.message || e}`);
  }
}

function remove(id) {
  if (!confirm("确认在本地列表隐藏该 Run 吗？")) return;
  hiddenIds.value.add(id);
  persistHidden();
}

async function mockOne() {
  const ds = (store.datasets ?? [])[0];
  const algo = (store.algorithms ?? [])[0];
  if (!ds || !algo) return alert("请先准备至少一个数据集和算法，再创建示例 Run");

  try {
    await store.createRun({
      task: algo.task || "去噪",
      datasetId: ds.id,
      algorithmId: algo.id,
      metrics: ["PSNR", "SSIM", "NIQE"],
    });
  } catch (e) {
    alert(`创建示例失败：${e?.message || e}`);
  }
}

onMounted(() => {
  refresh();
});

const detailVisible = ref(false);
const detail = ref(null);

function openDetail(row) {
  const ctx = buildScoringContext(filteredRows.value);
  const s = scoreOne(row, ctx);

  detail.value = {
    ...row,
    score: s.score,
    reason: s.reason,
  };
  detailVisible.value = true;
}

</script>

<style scoped>
.page {
  padding: 12px;
}

.card {
  border-radius: 14px;
  border: 1px solid #d8e3ff;
  box-shadow: 0 14px 28px rgba(26, 78, 190, 0.1);
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.titleRow {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1b2f62;
  line-height: 1.2;
}

.subtitle {
  margin-top: 6px;
  color: #4f628f;
  font-size: 14px;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.rowActions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color: #23386a;
}

.empty {
  padding: 28px 0;
  text-align: center;
}

.emptyTitle {
  font-size: 14px;
  color: #2a3f71;
}

.emptySub {
  margin-top: 6px;
  font-size: 12px;
  color: #5f7098;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detailGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detailBlock {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.blockTitle {
  color: #3d5588;
  font-size: 13px;
  font-weight: 600;
}

.code {
  margin: 0;
  padding: 12px;
  border-radius: 10px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.codeDark {
  background: #0b1020;
  color: #e7e7e7;
}

.codeError {
  background: #1a0f12;
  color: #ffd7d7;
}

.reasonText {
  padding: 10px 12px;
  border: 1px solid #d3e1ff;
  border-radius: 10px;
  background: #f7faff;
  color: #2b3f6f;
  font-size: 13px;
  line-height: 1.5;
}

:deep(.el-table) {
  --el-table-text-color: #243965;
  --el-table-header-text-color: #23478f;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px #c9d8ff inset;
}

@media (max-width: 980px) {
  .detailGrid {
    grid-template-columns: 1fr;
  }
}
</style>
