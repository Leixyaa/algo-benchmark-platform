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

      <div style="display: flex; gap: 8px">
        <el-button type="primary" @click="goNewRun">发起评测</el-button>
        <el-button @click="mockOne">添加一条示例任务</el-button>
        <el-button @click="refresh">刷新</el-button>
      </div>
    </div>

    <el-table :data="rows" size="small" border style="width: 100%">
      <el-table-column prop="name" label="任务名" min-width="160" />
      <el-table-column prop="id" label="Run ID" min-width="160" />
      <el-table-column prop="dataset" label="数据集" min-width="140" />
      <el-table-column prop="algorithm" label="算法" min-width="140" />

      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
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
const HIDDEN_KEY = "hiddenRunIds_v1";
const hiddenIds = ref(new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || "[]")));

function persistHidden() {
  localStorage.setItem(HIDDEN_KEY, JSON.stringify(Array.from(hiddenIds.value)));
}


// 统一把“任务中心”理解为：评测 Run 列表。
// NewRun.vue 创建的是 run，所以这里也用 store.runs。
const rows = computed(() => {
  const dsMap = new Map((store.datasets ?? []).map((d) => [d.id, d.name]));
  const algoMap = new Map((store.algorithms ?? []).map((a) => [a.id, a.name]));
  return (store.runs ?? [])
  .filter((r) => !hiddenIds.value.has(r.id))
  .map((r) => ({
    ...r,
    name: r.name || `${r.task || "评测"} Run`,
    dataset: dsMap.get(r.datasetId) ?? r.datasetId ?? "-",
    algorithm: algoMap.get(r.algorithmId) ?? r.algorithmId ?? "-",
  }));
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
  if (status === "done" || status === "已完成") return "success"; // 绿
  if (status === "running" || status === "运行中") return "warning";
  if (status === "failed" || status === "失败") return "danger";
  return "info";
}

// 刷新列表：从后端 Redis 拉取最新 runs
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
  // 用现有 demo 数据集/算法快速创建一条真实 run（POST /runs），方便验收闭环
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
  detail.value = row;
  detailVisible.value = true;
}
</script>
