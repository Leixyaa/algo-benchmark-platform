<template>
  <div style="padding:16px;">
    <h2 style="margin:0 0 8px;">发起评测</h2>
    <div style="color:#666; margin-bottom:12px;">
      选择任务类别、数据集、算法与指标，创建一次评测任务。任务由后端异步执行，可在任务中心查看状态与结果。
    </div>

    <div style="display:grid; grid-template-columns: 140px 1fr; gap:10px; max-width:680px;">
      <div>实验预设</div>
      <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
        <select v-model="form.presetId" style="padding:6px; min-width:240px;">
          <option value="">（不使用预设）</option>
          <option v-for="p in presetsAll" :key="p.id" :value="p.id">
            {{ p.name }}（{{ toTaskLabel(p.taskType) }}）
          </option>
        </select>
        <button @click="applyPreset" style="padding:6px 10px;">加载</button>
        <button @click="removePreset" style="padding:6px 10px;">删除</button>
      </div>

      <div>预设名称</div>
      <div style="display:flex; gap:8px; align-items:center;">
        <input v-model="form.presetName" placeholder="例如：去雾-DCP-默认参数" style="flex:1; padding:6px;" />
        <button @click="savePreset" style="padding:6px 10px;">保存为预设</button>
      </div>

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

      <div>参数(JSON)</div>
      <textarea
        v-model="form.paramsText"
        rows="8"
        style="width:100%; padding:8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;"
        placeholder="例如：{&quot;dcp_patch&quot;:15,&quot;dcp_omega&quot;:0.95,&quot;dcp_t0&quot;:0.1}"
      />
    </div>

    <div style="margin-top:14px; display:flex; gap:10px;">
      <button @click="create" style="padding:8px 12px;">创建评测任务</button>
      <button @click="goRuns" style="padding:8px 12px;">查看任务中心</button>
    </div>

    <div style="margin-top:14px; color:#666;">
      <div>提示：</div>
      <div>1）算法会按任务类别过滤（例如去雾只显示去雾算法）。</div>
      <div>2）创建任务会进入队列，状态从排队中→运行中→完成/失败。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useAppStore, toTaskLabel, toTaskType } from "../stores/app";

const NEWRUN_CACHE_KEY = "newrun_form_v1";
const router = useRouter();
const store = useAppStore();
const applyingPreset = ref(false);

const form = reactive({
  presetId: "",
  presetName: "",
  task: "去噪",
  datasetId: "",
  algorithmId: "",
  metrics: ["PSNR", "SSIM"],
  paramsText: "{}",
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
    if (typeof cached.paramsText === "string") form.paramsText = cached.paramsText;
    if (typeof cached.presetId === "string") form.presetId = cached.presetId;
    if (typeof cached.presetName === "string") form.presetName = cached.presetName;
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

const presetsAll = computed(() =>
  (store.presets || [])
    .slice()
    .sort((a, b) => (b?.raw?.updated_at || b?.raw?.created_at || 0) - (a?.raw?.updated_at || a?.raw?.created_at || 0))
);

const selectedAlgorithm = computed(() =>
  store.algorithms.find((a) => a.id === form.algorithmId)
);

watch(
  () => form.task,
  () => {
    if (applyingPreset.value) return;
    if (!filteredAlgorithms.value.some((a) => a.id === form.algorithmId)) {
      form.algorithmId = "";
    }
  }
);

watch(
  () => form.algorithmId,
  () => {
    const cur = String(form.paramsText || "").trim();
    if (cur && cur !== "{}") return;
    const alg = selectedAlgorithm.value;
    const obj =
      alg?.defaultParams && typeof alg.defaultParams === "object" && !Array.isArray(alg.defaultParams)
        ? alg.defaultParams
        : {};
    form.paramsText = JSON.stringify(obj, null, 2);
  }
);

onMounted(async () => {
  try {
    await store.fetchPresets();
  } catch {
    // ignore
  }
});

function applyPreset() {
  const pid = form.presetId;
  if (!pid) return;
  const p = (store.presets || []).find((x) => x.id === pid);
  if (!p) return;
  applyingPreset.value = true;
  form.presetName = p.name || "";
  form.task = toTaskLabel(p.taskType);
  form.datasetId = p.datasetId || "";
  form.algorithmId = p.algorithmId || "";
  form.metrics = Array.isArray(p.metrics) && p.metrics.length ? [...p.metrics] : ["PSNR", "SSIM"];
  const params = p.params && typeof p.params === "object" && !Array.isArray(p.params) ? p.params : {};
  form.paramsText = JSON.stringify(params, null, 2);
  setTimeout(() => {
    applyingPreset.value = false;
  }, 0);
}

watch(
  () => form.presetId,
  () => {
    if (!form.presetId) return;
    applyPreset();
  }
);

async function savePreset() {
  if (!form.presetName.trim()) return alert("请填写预设名称");
  if (!form.datasetId) return alert("请先选择数据集");
  if (!form.algorithmId) return alert("请先选择算法");
  if (!form.metrics.length) return alert("请至少选择一个指标");

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`参数不是合法 JSON：${e?.message || e}`);
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return alert("参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }");
  }

  try {
    const out = await store.createPreset({
      name: form.presetName.trim(),
      task: form.task,
      datasetId: form.datasetId,
      algorithmId: form.algorithmId,
      metrics: [...form.metrics],
      params,
    });
    form.presetId = out?.id || "";
    alert("预设已保存");
  } catch (e) {
    alert(`保存预设失败：${e?.message || e}`);
  }
}

async function removePreset() {
  if (!form.presetId) return;
  const ok = confirm("确定删除该预设吗？");
  if (!ok) return;
  try {
    await store.removePreset(form.presetId);
    form.presetId = "";
    alert("预设已删除");
  } catch (e) {
    alert(`删除预设失败：${e?.message || e}`);
  }
}

async function create() {
  if (!form.datasetId) return alert("请先选择数据集");
  if (!form.algorithmId) return alert("请先选择算法");
  if (!form.metrics.length) return alert("请至少选择一个指标");

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`参数不是合法 JSON：${e?.message || e}`);
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return alert("参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }");
  }

  try {
    await store.createRun({
      task: form.task,
      datasetId: form.datasetId,
      algorithmId: form.algorithmId,
      metrics: [...form.metrics],
      params,
    });
    localStorage.removeItem(NEWRUN_CACHE_KEY);
    alert("任务已创建，正在后端异步执行，可在任务中心查看");
    router.push("/runs");
  } catch (e) {
    alert(`创建失败：${e?.message || e}`);
  }
}

function goRuns() {
  router.push("/runs");
}
</script>
