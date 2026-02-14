<template>
  <div class="page">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="header">
          <div class="headerLeft">
            <div class="titleRow">
              <h2 class="title">任务中心</h2>
              <el-tag size="small" type="info">{{ filteredRows.length }} 条</el-tag>
            </div>
            <div class="subtitle">展示评测任务的状态、参数与结果概览。状态由后端 Celery/Redis 驱动，会自动刷新。</div>
          </div>
          <div class="headerRight">
            <el-button type="primary" @click="goNewRun">发起评测</el-button>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <div class="filters">
          <el-select v-model="statusFilter" clearable size="small" placeholder="状态" style="width: 130px">
            <el-option v-for="x in statusOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
          <el-select v-model="taskFilter" clearable size="small" placeholder="任务类型" style="width: 140px">
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
            <el-button size="small" @click="mockOne">示例</el-button>
          </el-button-group>
          <el-button-group>
            <el-button size="small" @click="exportDoneCsv">导出CSV</el-button>
            <el-button size="small" @click="exportDoneXlsx">导出Excel</el-button>
          </el-button-group>
          <el-button size="small" type="danger" @click="clearDone">清理已完成</el-button>
        </div>
      </div>

      <el-table :data="filteredRows" size="small" stripe border style="width: 100%" row-key="id">
        <el-table-column prop="name" label="任务名" min-width="180" show-overflow-tooltip />
        <el-table-column label="Run ID" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="task" label="任务类型" width="110" show-overflow-tooltip />
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
            <div class="emptyTitle">暂无任务</div>
            <div class="emptySub">点击右上角“发起评测”创建第一条任务。</div>
          </div>
        </template>
      </el-table>

      <el-dialog v-model="detailVisible" title="任务详情" width="760px">
        <div v-if="detail" class="detail">
          <el-descriptions size="small" :column="2" border>
            <el-descriptions-item label="任务名">{{ detail.name }}</el-descriptions-item>
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
              <div class="blockTitle">结果指标</div>
              <el-descriptions size="small" :column="1" border>
                <el-descriptions-item label="PSNR">{{ detail.psnr ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="SSIM">{{ detail.ssim ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="NIQE">{{ detail.niqe ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="耗时">{{ detail.elapsed ?? "-" }}</el-descriptions-item>
                <el-descriptions-item label="综合分">{{ detail.score ?? "-" }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>

          <div v-if="detail.reason" class="reason">
            <div class="blockTitle">推荐原因</div>
            <div class="reasonText">{{ detail.reason }}</div>
          </div>

          <div v-if="detail.raw?.error" class="errorBlock">
            <div class="blockTitle">失败/取消原因</div>
            <pre class="code codeError">{{ detail.raw?.error }}</pre>
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

// ========= 隐藏（本地持久化，不动后端）=========
const HIDDEN_KEY = "hiddenRunIds_v1";
const hiddenIds = ref(new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || "[]")));

function persistHidden() {
  localStorage.setItem(HIDDEN_KEY, JSON.stringify(Array.from(hiddenIds.value)));
}

// ========= 下载（不弹窗，不会被拦截）=========
function downloadFile(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename; // 某些浏览器会忽略，但不影响下载
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
  if (!confirm("确定清理所有“已完成”的历史任务吗？（会删除后端Redis记录，无法恢复）")) return;

  try {
    const res = await fetch("http://127.0.0.1:8000/runs/clear?status=done", {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));

    alert(`已清理：${data.deleted} 条已完成任务`);
    await refresh(); // 重新拉取列表
  } catch (e) {
    alert(`清理失败：${e?.message || e}`);
  }
}


// ========= 表格数据 =========
const rows = computed(() => {
  const dsMap = new Map((store.datasets ?? []).map((d) => [d.id, d.name]));
  const algoMap = new Map((store.algorithms ?? []).map((a) => [a.id, a.name]));

  return (store.runs ?? [])
    .filter((r) => !hiddenIds.value.has(r.id))
    .map((r) => {
      const base = {
        ...r,
        name: r.name || `${r.task || "评测"} Run`,
        dataset: dsMap.get(r.datasetId) ?? r.datasetId ?? "-",
        algorithm: algoMap.get(r.algorithmId) ?? r.algorithmId ?? "-",
      };

      // 只对已完成且指标齐全的 run 算综合分
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
  { value: "已完成", label: "已完成" },
  { value: "运行中", label: "运行中" },
  { value: "排队中", label: "排队中" },
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

function statusText(status) {
  if (status === "done" || status === "已完成") return "已完成";
  if (status === "running" || status === "运行中") return "运行中";
  if (status === "failed" || status === "失败") return "失败";
  if (status === "queued" || status === "排队中") return "排队中";
  if (status === "canceling" || status === "取消中") return "取消中";
  if (status === "canceled" || status === "已取消") return "已取消";
  return status || "-";
}

function statusTagType(status) {
  if (status === "done" || status === "已完成") return "success";
  if (status === "running" || status === "运行中") return "warning";
  if (status === "failed" || status === "失败") return "danger";
  if (status === "canceling" || status === "取消中") return "warning";
  if (status === "canceled" || status === "已取消") return "info";
  return "info";
}

function canCancel(row) {
  return row?.status === "排队中" || row?.status === "运行中" || row?.status === "取消中";
}

async function cancel(runId) {
  if (!confirm("确定取消该任务吗？")) return;
  try {
    await store.cancelRun(runId);
    await refresh();
  } catch (e) {
    alert(`取消失败：${e?.message || e}`);
  }
}


// ====== 快速选型：给单条 run 计算综合分 + 推荐原因（与 Compare 同逻辑）======

// elapsed "1.23s" -> seconds
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

  // Runs 详情这里用固定默认权重（你在 Compare 里可调；详情里只展示“平台默认推荐逻辑”）
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
  if (!okAll) return { score: null, reason: "指标不完整，无法计算综合分" };

  const score =
    ctx.W.psnr * nPSNR +
    ctx.W.ssim * nSSIM +
    ctx.W.niqe * (1 - nNIQE) +
    ctx.W.time * (1 - nTIME);

  // 简短解释：点出主导项
  const parts = [];
  if (nPSNR >= 0.8) parts.push("PSNR较高");
  if (nSSIM >= 0.8) parts.push("SSIM较高");
  if (nNIQE <= 0.2) parts.push("NIQE较低(更自然)");
  if (nTIME <= 0.2) parts.push("耗时较短");
  if (parts.length === 0) parts.push("多指标较均衡");

  return {
    score: Number(score.toFixed(4)),
    reason: `${parts.join("，")}；默认权重：PSNR 35% + SSIM 35% + NIQE 20% + 耗时 10%`,
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
  if (!confirm("确定隐藏该任务吗？（仅本机本浏览器生效，后端不会删除）")) return;
  hiddenIds.value.add(id);
  persistHidden();
}

async function mockOne() {
  const ds = (store.datasets ?? [])[0];
  const algo = (store.algorithms ?? [])[0];
  if (!ds || !algo) return alert("缺少 Demo 数据集或算法，无法创建示例任务");

  try {
    await store.createRun({
      task: algo.task || "去噪",
      datasetId: ds.id,
      algorithmId: algo.id,
      metrics: ["PSNR", "SSIM", "NIQE"],
    });
  } catch (e) {
    alert(`创建失败：${e?.message || e}`);
  }
}

onMounted(() => {
  refresh();
});

const detailVisible = ref(false);
const detail = ref(null);

function openDetail(row) {
  // 用当前列表（已过滤隐藏）作为评分范围；这样解释是“在当前可见 runs 中的相对表现”
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
  border-radius: 12px;
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
  font-size: 18px;
  line-height: 1.2;
}

.subtitle {
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
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
}

.empty {
  padding: 28px 0;
  text-align: center;
}

.emptyTitle {
  font-size: 14px;
  color: #374151;
}

.emptySub {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
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
  color: #6b7280;
  font-size: 13px;
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
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafafa;
  color: #374151;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 980px) {
  .detailGrid {
    grid-template-columns: 1fr;
  }
}
</style>
