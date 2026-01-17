<template>
  <div>
    <div
      style="
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
      "
    >
      <div>
        <h2 style="margin: 0 0 6px">任务中心</h2>
        <div style="color: #666">
          展示评测任务的状态、参数与结果概览。状态由后端 Celery/Redis 驱动，会自动刷新。
        </div>
      </div>

      <div style="display: flex; gap: 8px; flex-wrap: wrap">
        <el-button type="primary" @click="goNewRun">发起评测</el-button>
        <el-button @click="mockOne">添加一条示例任务</el-button>
        <el-button @click="refresh">刷新</el-button>
        <el-button @click="exportDoneCsv">导出已完成CSV</el-button>
        <el-button @click="exportDoneXlsx">导出已完成Excel</el-button>
        <el-button type="danger" @click="clearDone">清理已完成</el-button>
      </div>
    </div>

    <el-table :data="rows" size="small" border style="width: 100%">
      <el-table-column prop="name" label="任务名" min-width="160" />
      <el-table-column prop="id" label="Run ID" min-width="160" />
      <el-table-column prop="dataset" label="数据集" min-width="140" />
      <el-table-column prop="algorithm" label="算法" min-width="140" />

      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="综合分" width="100">
        <template #default="{ row }">
          <span>{{ row.score ?? "-" }}</span>
        </template>
      </el-table-column>


      <el-table-column prop="createdAt" label="创建时间" width="170" />

      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button size="small" type="danger" @click="remove(row.id)">从列表隐藏</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="rows.length === 0" style="color: #888; margin-top: 12px">
      还没有任务。你可以点击右上角“发起评测”创建第一条任务。
    </div>

    <el-dialog v-model="detailVisible" title="任务详情" width="680px">
      <div v-if="detail">
        <div
          style="
            display: grid;
            grid-template-columns: 120px 1fr;
            row-gap: 8px;
            column-gap: 8px;
            margin-bottom: 12px;
          "
        >
          <div style="color: #666">任务名</div><div>{{ detail.name }}</div>
          <div style="color: #666">Run ID</div><div>{{ detail.id }}</div>
          <div style="color: #666">数据集</div><div>{{ detail.dataset }}</div>
          <div style="color: #666">算法</div><div>{{ detail.algorithm }}</div>
          <div style="color: #666">状态</div><div>{{ statusText(detail.status) }}</div>
          <div style="color: #666">创建时间</div><div>{{ detail.createdAt }}</div>
        </div>

        <div style="color: #666; margin: 0 0 6px">参数（后端 params 原样展示）</div>
        <pre
          style="
            background: #0b1020;
            color: #e7e7e7;
            padding: 12px;
            border-radius: 8px;
            overflow: auto;
          "
        >{{ detail.raw?.params ?? {} }}</pre>

        <div style="color: #666; margin: 12px 0 6px">结果指标</div>
        <div
          style="
            display: grid;
            grid-template-columns: 120px 1fr;
            row-gap: 8px;
            column-gap: 8px;
          "
        >
          <div style="color: #666">PSNR</div><div>{{ detail.psnr ?? "-" }}</div>
          <div style="color: #666">SSIM</div><div>{{ detail.ssim ?? "-" }}</div>
          <div style="color: #666">NIQE</div><div>{{ detail.niqe ?? "-" }}</div>
          <div style="color: #666">耗时</div><div>{{ detail.elapsed ?? "-" }}</div>
          <div style="color: #666">综合分</div><div>{{ detail.score ?? "-" }}</div>
          <div style="color: #666">推荐原因</div><div>{{ detail.reason ?? "-" }}</div>

        </div>
      </div>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";

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

function goNewRun() {
  router.push("/new-run");
}

function statusText(status) {
  if (status === "done" || status === "已完成") return "已完成";
  if (status === "running" || status === "运行中") return "运行中";
  if (status === "failed" || status === "失败") return "失败";
  if (status === "queued" || status === "排队中") return "排队中";
  return status || "-";
}

function statusTagType(status) {
  if (status === "done" || status === "已完成") return "success";
  if (status === "running" || status === "运行中") return "warning";
  if (status === "failed" || status === "失败") return "danger";
  return "info";
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
  const ctx = buildScoringContext(rows.value);
  const s = scoreOne(row, ctx);

  detail.value = {
    ...row,
    score: s.score,
    reason: s.reason,
  };
  detailVisible.value = true;
}

</script>
