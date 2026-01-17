<template>
  <div class="page">
    <h2 class="title">结果对比与快速选型</h2>

    <el-card shadow="never" class="card">
      <div class="filters">
        <el-select v-model="task" placeholder="选择任务类型" style="width: 180px">
          <el-option v-for="t in taskOptions" :key="t" :label="t" :value="t" />
        </el-select>

        <el-select v-model="datasetId" placeholder="选择数据集" style="width: 220px">
          <el-option
            v-for="d in store.datasets"
            :key="d.id"
            :label="d.name"
            :value="d.id"
          />
        </el-select>

        <el-checkbox v-model="onlyDone">只显示已完成</el-checkbox>

        <el-button type="primary" @click="reset">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="card" style="margin-top: 12px">
      <div class="recommend" v-if="recommendText">
        <div class="recommend-title">快速推荐</div>
        <div class="recommend-body">{{ recommendText }}</div>
      </div>

      <el-table :data="tableRows" stripe style="width: 100%; margin-top: 8px">
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column prop="task" label="任务" width="110" />
        <el-table-column prop="datasetName" label="数据集" min-width="180" />
        <el-table-column prop="algorithmName" label="算法" min-width="180" />
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

        <el-table-column prop="score" label="综合分" width="100" sortable />
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

const store = useAppStore();

const task = ref("");
const datasetId = ref("");
const onlyDone = ref(true);

// 页面首次进入时，从后端拉取历史 runs（避免刷新页面表格为空）
onMounted(async () => {
  if (!store.runs || store.runs.length === 0) {
    try {
      await store.fetchRuns();
    } catch (e) {
      // 不挡页面：用户仍然可以去 Runs/NewRun 再回来
      console.warn(e);
    }
  }
});

// 任务类型来自算法库 task 字段（你现在 algorithms 里就是 task: "去噪"）
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
}

// 计算综合分（多指标融合，可解释）
// 说明：PSNR/SSIM 越大越好；NIQE 越小越好；score 越大越推荐
function calcScore(r) {
  const psnr = Number(r.psnr);
  const ssim = Number(r.ssim);
  const niqe = Number(r.niqe);

  // 防空：没结果就给 -Infinity，让它排到最后
  if (!isFinite(psnr) || !isFinite(ssim) || !isFinite(niqe)) return -Infinity;

  // 稳定、可解释的权重（答辩按这个解释）
  // - PSNR 45%
  // - SSIM 45%（乘 100 把量纲拉到类似）
  // - NIQE 惩罚 10%（乘 10 把量纲拉到类似）
  const score = 0.45 * psnr + 0.45 * (ssim * 100) - 0.1 * (niqe * 10);
  return +score.toFixed(2);
}

const tableRows = computed(() => {
  const dsMap = new Map(store.datasets.map((d) => [d.id, d]));
  const algMap = new Map(store.algorithms.map((a) => [a.id, a]));

  let runs = store.runs.slice();

  if (task.value) {
    runs = runs.filter((r) => r.task === task.value);
  }
  if (datasetId.value) {
    runs = runs.filter((r) => r.datasetId === datasetId.value);
  }
  if (onlyDone.value) {
    runs = runs.filter((r) => isDone(r.status));
  }

  const rows = runs.map((r) => {
    const ds = dsMap.get(r.datasetId);
    const alg = algMap.get(r.algorithmId);
    const score = calcScore(r);

    return {
      ...r,
      datasetName: ds ? ds.name : r.datasetId,
      algorithmName: alg ? alg.name : r.algorithmId,
      score,
    };
  });

  // 默认按综合分降序
  rows.sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
  return rows;
});

const recommendText = computed(() => {
  if (tableRows.value.length === 0) return "";

  const top = tableRows.value[0];
  if (!isFinite(top.score)) return "";

  const parts = [];
  parts.push(`在当前筛选条件下，综合分最高的是 ${top.algorithmName}。`);
  parts.push(
    `它的指标表现为 PSNR=${top.psnr}、SSIM=${top.ssim}、NIQE=${top.niqe}，耗时 ${
      top.elapsed || "—"
    }。`
  );
  parts.push(
    `本平台采用加权综合评分进行快速选型：画质类指标（PSNR、SSIM）为主，无参考质量（NIQE）作为惩罚项，从而在多指标下给出可解释的排序推荐。`
  );
  return parts.join("");
});
</script>

<style scoped>
.page {
  padding: 12px;
}
.title {
  margin: 0 0 10px 0;
  font-size: 18px;
  font-weight: 600;
}
.card {
  border-radius: 10px;
}
.filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.recommend {
  padding: 10px 12px;
  border: 1px dashed #dcdfe6;
  border-radius: 10px;
}
.recommend-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.recommend-body {
  line-height: 1.6;
}
.empty {
  margin-top: 12px;
  color: #909399;
}
</style>
