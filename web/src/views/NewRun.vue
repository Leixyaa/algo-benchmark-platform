<template>
  <div style="padding:16px;">
    <h2 style="margin:0 0 8px;">发起评测</h2>
    <div style="color:#666; margin-bottom:12px;">
      选择任务类别、数据集、算法与指标，创建一次评测任务。当前为前端模拟，后续接后端异步执行。
    </div>

    <div style="display:grid; grid-template-columns: 140px 1fr; gap:10px; max-width:680px;">
      <div>任务类别</div>
      <select v-model="form.task" style="padding:6px;">
        <option>去噪</option>
        <option>去模糊</option>
        <option>去雾</option>
        <option>超分辨率</option>
        <option>低照度增强</option>
        <option>视频去噪</option>
        <option>视频超分</option>
      </select>

      <div>数据集</div>
      <select v-model="form.datasetId" style="padding:6px;">
        <option value="" disabled>请选择数据集</option>
        <option v-for="d in store.datasets" :key="d.id" :value="d.id">
          {{ d.name }}（{{ d.type }}）
        </option>
      </select>

      <div>算法</div>
      <select v-model="form.algorithmId" style="padding:6px;">
        <option value="" disabled>请选择算法</option>
        <option v-for="a in filteredAlgorithms" :key="a.id" :value="a.id">
          {{ a.name }}（{{ a.impl }} / {{ a.version }}）
        </option>
      </select>

      <div>指标</div>
      <div style="display:flex; gap:12px; flex-wrap:wrap;">
        <label><input type="checkbox" value="PSNR" v-model="form.metrics" /> PSNR</label>
        <label><input type="checkbox" value="SSIM" v-model="form.metrics" /> SSIM</label>
        <label><input type="checkbox" value="NIQE" v-model="form.metrics" /> NIQE（无参考）</label>
      </div>
    </div>

    <div style="margin-top:14px; display:flex; gap:10px;">
      <button @click="create" style="padding:8px 12px;">创建评测任务</button>
      <button @click="goRuns" style="padding:8px 12px;">查看任务中心</button>
    </div>

    <div style="margin-top:14px; color:#666;">
      <div>提示：</div>
      <div>1）算法会按任务类别过滤（例如去雾只显示去雾算法）。</div>
      <div>2）后续接后端后：创建任务会进入 Celery 队列，状态从排队中→运行中→完成/失败。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";

const NEWRUN_CACHE_KEY = "newrun_form_v1";
const router = useRouter();
const store = useAppStore();

const form = reactive({
  task: "去噪",
  datasetId: "",
  algorithmId: "",
  metrics: ["PSNR", "SSIM"],
});

// 恢复上次选择
try {
  const raw = localStorage.getItem(NEWRUN_CACHE_KEY);
  if (raw) {
    const cached = JSON.parse(raw);

    // 只恢复你表单里已有字段，避免脏数据
    if (cached.task) form.task = cached.task;
    if (cached.datasetId) form.datasetId = cached.datasetId;
    if (cached.algorithmId) form.algorithmId = cached.algorithmId;
    if (Array.isArray(cached.metrics)) form.metrics = cached.metrics;
  }
} catch {
  // ignore
}

watch(
  () => ({ ...form, metrics: Array.isArray(form.metrics) ? [...form.metrics] : [] }),
  (val) => {
    localStorage.setItem(NEWRUN_CACHE_KEY, JSON.stringify(val));
  },
  { deep: true }
);


const filteredAlgorithms = computed(() =>
  store.algorithms.filter((a) => a.task === form.task)
);

function create() {
  if (!form.datasetId) return alert("请先选择数据集");
  if (!form.algorithmId) return alert("请先选择算法");
  if (!form.metrics.length) return alert("请至少选择一个指标");

  const ds = store.datasets.find((d) => d.id === form.datasetId);
  const alg = store.algorithms.find((a) => a.id === form.algorithmId);

  const runId = store.createRun({
    task: form.task,
    datasetId: ds.id,
    datasetName: ds.name,
    algorithmId: alg.id,
    algorithmName: alg.name,
    metrics: [...form.metrics],
  });

// 前端模拟：2秒后运行中，5秒后完成并生成指标
setTimeout(() => store.updateRunStatus(runId, "运行中"), 2000);

setTimeout(() => {
  store.updateRunStatus(runId, "已完成");
  // 模拟结果（后续接后端这里会被真实结果替代）
  store.attachRunResult(runId, {
    psnr: +(28 + Math.random() * 6).toFixed(2),
    ssim: +(0.80 + Math.random() * 0.18).toFixed(3),
    niqe: +(3 + Math.random() * 2.5).toFixed(2),
    elapsed: `${(2 + Math.random() * 6).toFixed(1)}s`,
  });
}, 5000);

  localStorage.removeItem(NEWRUN_CACHE_KEY);

  alert("任务已创建（模拟执行中），已进入任务中心");
  router.push("/runs");
}

function goRuns() {
  router.push("/runs");
}
</script>
