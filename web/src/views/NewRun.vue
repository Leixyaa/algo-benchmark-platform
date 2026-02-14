<template>
  <div class="page">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="header">
          <div>
            <h2 class="title">新建评测</h2>
            <div class="subtitle">选择任务类型、数据集、算法、指标与参数，发起一次评测（Run）。支持保存/应用预设，便于复现。</div>
          </div>
          <div class="headerRight">
            <el-button @click="goRuns">查看运行列表</el-button>
          </div>
        </div>
      </template>

      <el-form :model="form" label-width="110px" class="form">
        <el-form-item label="预设方案">
          <div class="row">
            <el-select v-model="form.presetId" filterable clearable placeholder="不使用预设（手动配置）" style="width: 360px">
              <el-option label="不使用预设（手动配置）" value="" />
              <el-option
                v-for="p in presetsAll"
                :key="p.id"
                :label="`${p.name}（${toTaskLabel(p.taskType)}）`"
                :value="p.id"
              />
            </el-select>
            <el-button type="primary" :disabled="!form.presetId" @click="applyPreset">应用</el-button>
            <el-button type="danger" plain :disabled="!form.presetId" @click="removePreset">删除</el-button>
          </div>
        </el-form-item>

        <el-form-item label="预设名称">
          <div class="row">
            <el-input v-model="form.presetName" placeholder="例如：去雾-DCP-参数方案A" style="width: 360px" />
            <el-button :disabled="!form.presetName.trim()" @click="savePreset">保存为预设</el-button>
          </div>
        </el-form-item>

        <el-form-item label="任务类型">
          <el-select v-model="form.taskType" style="width: 360px">
            <el-option v-for="x in taskTypeOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="数据集">
          <div class="row">
            <el-select v-model="form.datasetId" filterable placeholder="请选择数据集" style="width: 360px">
              <el-option v-for="d in store.datasets" :key="d.id" :label="datasetOptionLabel(d)" :value="d.id" />
            </el-select>
            <el-button :disabled="!form.datasetId" @click="scanSelectedDataset">扫描</el-button>
          </div>
          <div v-if="datasetHintText" class="hint">
            <el-alert :title="datasetHintText" type="warning" show-icon :closable="false" />
          </div>
        </el-form-item>

        <el-form-item label="严格校验">
          <el-checkbox v-model="form.strictValidate">无配对则拒绝创建（推荐）</el-checkbox>
        </el-form-item>

        <el-form-item label="算法">
          <el-select v-model="form.algorithmId" filterable placeholder="请选择算法" style="width: 360px">
            <el-option
              v-for="a in filteredAlgorithms"
              :key="a.id"
              :label="`${a.name}（${a.impl} / ${a.version}）`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="指标">
          <el-checkbox-group v-model="form.metrics">
            <el-checkbox label="PSNR" />
            <el-checkbox label="SSIM" />
            <el-checkbox label="NIQE">NIQE（无参考，越低越好）</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="参数方案">
          <div class="row">
            <el-select v-model="form.paramSchemeKey" :disabled="!form.algorithmId" style="width: 360px">
              <el-option label="自定义：保持当前参数" value="__custom__" />
              <el-option label="默认参数" value="__default__" />
              <el-option v-if="paramPresetEntries.length === 0" label="该算法未提供参数预设" value="__none__" disabled />
              <el-option v-for="entry in paramPresetEntries" :key="entry[0]" :label="schemeLabel(entry[0])" :value="entry[0]" />
            </el-select>
            <el-button :disabled="!form.algorithmId" @click="applyParamScheme">应用</el-button>
          </div>
        </el-form-item>

        <el-form-item label="参数(JSON)">
          <el-input
            v-model="form.paramsText"
            type="textarea"
            :rows="10"
            placeholder='例如：{ "dcp_patch": 15, "dcp_omega": 0.95, "dcp_t0": 0.1 }'
            class="codeInput"
          />
        </el-form-item>

        <el-form-item>
          <div class="footer">
            <el-button type="primary" @click="create">开始评测</el-button>
            <el-button @click="goRuns">查看运行列表</el-button>
          </div>
        </el-form-item>
      </el-form>

      <el-alert
        title="提示：数据集新增/导入文件后，先点击“扫描”刷新规模与配对数；参数必须是合法 JSON，可在默认参数基础上修改并保存为预设。"
        type="info"
        show-icon
        :closable="false"
        class="tips"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { TASK_LABEL_BY_TYPE, useAppStore, toTaskLabel, toTaskType } from "../stores/app";

const NEWRUN_CACHE_KEY = "newrun_form_v2";
const router = useRouter();
const store = useAppStore();
const applyingPreset = ref(false);

const form = reactive({
  presetId: "",
  presetName: "",
  taskType: "denoise",
  datasetId: "",
  algorithmId: "",
  metrics: ["PSNR", "SSIM"],
  paramSchemeKey: "__default__",
  paramsText: "{}",
  strictValidate: false,
});

// 表单缓存
try {
  const raw = localStorage.getItem(NEWRUN_CACHE_KEY);
  if (raw) {
    const cached = JSON.parse(raw);

    // 兼容旧缓存字段（taskType / task）
    if (typeof cached.taskType === "string") form.taskType = cached.taskType;
    else if (typeof cached.task === "string") form.taskType = toTaskType(cached.task);
    if (cached.datasetId) form.datasetId = cached.datasetId;
    if (cached.algorithmId) form.algorithmId = cached.algorithmId;
    if (Array.isArray(cached.metrics)) form.metrics = cached.metrics;
    if (typeof cached.paramsText === "string") form.paramsText = cached.paramsText;
    if (typeof cached.presetId === "string") form.presetId = cached.presetId;
    if (typeof cached.presetName === "string") form.presetName = cached.presetName;
    if (typeof cached.strictValidate === "boolean") form.strictValidate = cached.strictValidate;
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

const taskTypeOptions = computed(() =>
  Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label }))
);

const filteredAlgorithms = computed(() =>
  store.algorithms.filter((a) => a.task === toTaskLabel(form.taskType))
);

const presetsAll = computed(() =>
  (store.presets || [])
    .slice()
    .sort((a, b) => (b?.raw?.updated_at || b?.raw?.created_at || 0) - (a?.raw?.updated_at || a?.raw?.created_at || 0))
);

const selectedAlgorithm = computed(() =>
  store.algorithms.find((a) => a.id === form.algorithmId)
);

const selectedDataset = computed(() =>
  store.datasets.find((d) => d.id === form.datasetId)
);

const paramPresetEntries = computed(() => {
  const alg = selectedAlgorithm.value;
  const pp = alg?.paramPresets && typeof alg.paramPresets === "object" && !Array.isArray(alg.paramPresets) ? alg.paramPresets : {};
  return Object.entries(pp).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v));
});

watch(
  () => form.paramSchemeKey,
  () => {
    if (!form.algorithmId) return;
    if (form.paramSchemeKey === "__custom__") return;
    applyParamScheme();
  }
);

watch(
  () => form.taskType,
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
    form.paramSchemeKey = "__default__";
    form.paramsText = JSON.stringify(obj, null, 2);
  }
);

onMounted(async () => {
  try { await store.fetchDatasets(); } catch {}
  try { await store.fetchAlgorithms(); } catch {}
  try { await store.fetchPresets(); } catch {}
});

function applyPreset() {
  const pid = form.presetId;
  if (!pid) return;
  const p = (store.presets || []).find((x) => x.id === pid);
  if (!p) return;
  applyingPreset.value = true;
  form.presetName = p.name || "";
  form.taskType = p.taskType;
  form.datasetId = p.datasetId || "";
  form.algorithmId = p.algorithmId || "";
  form.metrics = Array.isArray(p.metrics) && p.metrics.length ? [...p.metrics] : ["PSNR", "SSIM"];
  const params = p.params && typeof p.params === "object" && !Array.isArray(p.params) ? p.params : {};
  form.paramSchemeKey = "__custom__";
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

function applyParamScheme() {
  const alg = selectedAlgorithm.value;
  if (!alg) return;

  if (form.paramSchemeKey === "__custom__") return;

  if (form.paramSchemeKey === "__default__") {
    const obj =
      alg?.defaultParams && typeof alg.defaultParams === "object" && !Array.isArray(alg.defaultParams)
        ? alg.defaultParams
        : {};
    form.paramsText = JSON.stringify(obj, null, 2);
    return;
  }

  const pp = alg?.paramPresets && typeof alg.paramPresets === "object" && !Array.isArray(alg.paramPresets) ? alg.paramPresets : {};
  const obj = pp?.[form.paramSchemeKey];
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return;
  form.paramsText = JSON.stringify(obj, null, 2);
}

function schemeLabel(key) {
  if (key === "speed") return "速度优先";
  if (key === "quality") return "质量优先";
  return String(key || "");
}

async function scanSelectedDataset() {
  if (!form.datasetId) return;
  try {
    await store.scanDataset(form.datasetId);
  } catch (e) {
    alert(`扫描失败：${e?.message || e}`);
  }
}

function datasetOptionLabel(d) {
  const tt = form.taskType;
  const pairs =
    (d?.meta?.pairs_by_task && typeof d.meta.pairs_by_task === "object" ? d.meta.pairs_by_task : null) ||
    (d?.raw?.meta?.pairs_by_task && typeof d.raw.meta.pairs_by_task === "object" ? d.raw.meta.pairs_by_task : {}) ||
    {};
  const n = Number(pairs?.[tt] ?? 0);
  if (!tt) return `${d?.name || "-"}（${d?.type || "-"}）`;
  if (n > 0) return `${d?.name || "-"}（${d?.type || "-"}）- 配对数：${n}`;
  return `${d?.name || "-"}（${d?.type || "-"}）- 当前任务配对数为 0`;
}

const datasetHintText = computed(() => {
  if (!form.datasetId) return "";
  const tt = form.taskType;
  const d = selectedDataset.value;
  const pairs =
    (d?.meta?.pairs_by_task && typeof d.meta.pairs_by_task === "object" ? d.meta.pairs_by_task : null) ||
    (d?.raw?.meta?.pairs_by_task && typeof d.raw.meta.pairs_by_task === "object" ? d.raw.meta.pairs_by_task : {}) ||
    {};
  const n = Number(pairs?.[tt] ?? 0);
  if (Number.isFinite(n) && n > 0) return `当前任务可用配对数：${n}（输入目录/gt 同名配对）`;
  return "当前任务配对数为 0：请检查输入目录与 gt/ 是否齐全、文件名是否一一对应，并点击“扫描”刷新。";
});

async function savePreset() {
  if (!form.presetName.trim()) return alert("请填写预设名称");
  if (!form.datasetId) return alert("请选择数据集");
  if (!form.algorithmId) return alert("请选择算法");
  if (!form.metrics.length) return alert("请选择至少一个指标");

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`参数不是合法 JSON：${e?.message || e}`);
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return alert('参数必须是 JSON 对象，例如：{ "dcp_patch": 15 }');
  }

  try {
    const out = await store.createPreset({
      name: form.presetName.trim(),
      task: toTaskLabel(form.taskType),
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
  const ok = confirm("确认删除该预设？");
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
  if (!form.datasetId) return alert("请选择数据集");
  if (!form.algorithmId) return alert("请选择算法");
  if (!form.metrics.length) return alert("请选择至少一个指标");

  const tt = form.taskType;
  const d = selectedDataset.value;
  const pairs =
    (d?.meta?.pairs_by_task && typeof d.meta.pairs_by_task === "object" ? d.meta.pairs_by_task : null) ||
    (d?.raw?.meta?.pairs_by_task && typeof d.raw.meta.pairs_by_task === "object" ? d.raw.meta.pairs_by_task : {}) ||
    {};
  const pairCount = Number(pairs?.[tt] ?? 0);
  if (!Number.isFinite(pairCount) || pairCount <= 0) {
    if (form.strictValidate) {
      return alert("严格校验已开启：当前任务配对数为 0，无法创建。请导入正确目录结构并点击“扫描”刷新配对数。");
    }
    const ok = confirm("当前任务配对数为 0，仍要发起评测？请检查输入目录与 gt/ 是否齐全并扫描刷新。");
    if (!ok) return;
  }

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`参数不是合法 JSON：${e?.message || e}`);
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return alert('参数必须是 JSON 对象，例如：{ "dcp_patch": 15 }');
  }

  try {
    await store.createRun({
      task: toTaskLabel(form.taskType),
      datasetId: form.datasetId,
      algorithmId: form.algorithmId,
      metrics: [...form.metrics],
      params,
      strictValidate: form.strictValidate,
    });
    localStorage.removeItem(NEWRUN_CACHE_KEY);
    alert("已创建评测任务，将跳转到运行列表查看进度。");
    router.push("/runs");
  } catch (e) {
    const d = e?.detail;
    if (d && typeof d === "object") {
      if (d.error === "dataset_no_pairs_for_task") {
        const dirs = Array.isArray(d.expected_dirs) ? d.expected_dirs.join(" + ") : "";
        const hint = dirs ? `需要目录：${dirs}（同名配对）。` : "请检查输入目录与 gt/ 是否齐全并扫描刷新。";
        const ok = confirm(`${d.message || "数据集无配对，无法创建评测。"}\n${hint}\n是否现在执行一次“扫描”刷新数据集信息？`);
        if (ok) {
          try {
            await scanSelectedDataset();
          } catch {
          }
        }
        return;
      }
      if (d.error === "algorithm_task_mismatch") {
        const tip = `任务：${d.task_label || d.task_type || "-"}；算法任务：${d.algorithm_task || "-"}；期望：${d.expected_algorithm_task || "-"}`;
        return alert(`${d.message || "算法与任务不匹配。"}\n${tip}`);
      }
      if (d.message) return alert(`创建评测失败：${d.message}`);
    }
    alert(`创建评测失败：${e?.message || e}`);
  }
}

function goRuns() {
  router.push("/runs");
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

.form {
  max-width: 860px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hint {
  margin-top: 10px;
  max-width: 860px;
}

.codeInput :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.footer {
  display: flex;
  gap: 10px;
}

.tips {
  margin-top: 12px;
}
</style>
