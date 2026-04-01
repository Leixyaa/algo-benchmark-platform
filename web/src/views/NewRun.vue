<template>
  <div class="page">
    <div class="header-section">
      <div class="header-left">
        <h2 class="page-title">发起评测任务</h2>
        <p class="page-subtitle">通过简单的三个步骤，快速配置并启动您的算法性能评测</p>
      </div>
      <div class="header-right">
        <el-button class="centered-btn" @click="goRuns">返回任务中心</el-button>
      </div>
    </div>

    <el-card shadow="never" class="main-card">
      <div class="steps-wrapper">
        <el-steps :active="activeStep" finish-status="success" align-center class="custom-steps">
          <el-step title="基础配置" icon="Collection" />
          <el-step title="算法选型" icon="Cpu" />
          <el-step title="参数确认" icon="Setting" />
        </el-steps>
      </div>

      <div class="form-container">
        <!-- Step 1: Basic Config -->
        <div v-show="activeStep === 0" class="step-content">
          <div class="step-header">
            <h3 class="step-title">1. 选择评测任务与数据集</h3>
            <p class="step-desc">可先选择预设一键加载配置；或手动选择任务类型与数据集。</p>
          </div>
          
          <el-form :model="form" label-position="top" class="modern-form">
            <el-form-item label="使用参数预设 (可选)">
              <div class="preset-box">
                <el-select v-model="form.presetId" filterable clearable placeholder="从历史预设中快速加载配置" class="full-width-select">
                  <el-option label="不使用预设 (手动配置)" value="" />
                  <el-option
                    v-for="p in presetsAll"
                    :key="p.id"
                    :label="`${p.name}（${toTaskLabel(p.taskType)}）`"
                    :value="p.id"
                  />
                </el-select>
                <div v-if="form.presetId" class="preset-actions">
                  <el-button type="info" plain size="small" class="centered-btn" @click="clearPreset">解除预设锁定</el-button>
                  <el-button type="danger" plain size="small" class="centered-btn" @click="removePreset">永久删除预设</el-button>
                </div>
              </div>
              <el-alert v-if="form.presetId" title="已加载预设：部分选项已按预设锁定，如需修改请先解除锁定。" type="success" :closable="false" show-icon class="preset-alert" />
            </el-form-item>

            <el-form-item label="任务类型">
              <div class="task-options">
                <div 
                  v-for="x in taskTypeOptions" 
                  :key="x.value" 
                  class="task-card"
                  :class="{ active: form.taskType === x.value, disabled: !!form.presetId }"
                  @click="!form.presetId && (form.taskType = x.value)"
                >
                  <div class="task-icon"><el-icon><component :is="getTaskIcon(x.value)" /></el-icon></div>
                  <div class="task-info">
                    <div class="task-label">{{ x.label }}</div>
                    <div class="task-val">{{ x.value }}</div>
                  </div>
                  <div class="active-check"><el-icon><Check /></el-icon></div>
                </div>
              </div>
            </el-form-item>

            <el-form-item label="数据集选择">
              <el-select 
                v-model="form.datasetId" 
                :disabled="!!form.presetId" 
                filterable 
                placeholder="请选择评测数据集" 
                class="full-width-select"
              >
                <el-option v-for="d in store.datasets" :key="d.id" :label="datasetOptionLabel(d)" :value="d.id" />
              </el-select>
              <div v-if="datasetHintText" class="dataset-alert">
                <el-alert :title="datasetHintText" :type="datasetHintType" :closable="false" show-icon />
              </div>
              <el-button 
                v-if="form.datasetId" 
                size="small" 
                plain 
                class="scan-btn centered-btn"
                @click="scanSelectedDataset"
              >
                立即扫描数据集配对
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <!-- Step 2: Algorithm Config -->
        <div v-show="activeStep === 1" class="step-content">
          <div class="step-header">
            <h3 class="step-title">2. 选择评测算法与指标</h3>
            <p class="step-desc">选择本次运行使用的算法条目，并勾选需要计算的评测指标。</p>
          </div>

          <el-form :model="form" label-position="top" class="modern-form">
            <el-form-item label="选择评测算法">
              <el-select 
                v-model="form.algorithmId" 
                :disabled="!!form.presetId" 
                filterable 
                placeholder="请选择内置评测算法" 
                class="full-width-select"
              >
                <el-option
                  v-for="a in filteredAlgorithms"
                  :key="a.id"
                  :label="`${a.name}（${a.impl} / ${a.version}）`"
                  :value="a.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="评测指标">
              <div class="metrics-group">
                <button
                  type="button"
                  class="metric-chip"
                  :class="{ active: isMetricSelected('PSNR'), locked: !!form.presetId }"
                  :disabled="!!form.presetId"
                  @click="toggleMetric('PSNR')"
                >
                  PSNR
                </button>
                <button
                  type="button"
                  class="metric-chip"
                  :class="{ active: isMetricSelected('SSIM'), locked: !!form.presetId }"
                  :disabled="!!form.presetId"
                  @click="toggleMetric('SSIM')"
                >
                  SSIM
                </button>
                <button
                  type="button"
                  class="metric-chip metric-chip-wide"
                  :class="{ active: isMetricSelected('NIQE'), locked: !!form.presetId }"
                  :disabled="!!form.presetId"
                  @click="toggleMetric('NIQE')"
                >
                  NIQE (无参考)
                </button>
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- Step 3: Parameter & Review -->
        <div v-show="activeStep === 2" class="step-content">
          <div class="step-header">
            <h3 class="step-title">3. 参数方案与确认</h3>
            <p class="step-desc">确认运行参数并为本次配置保存预设（可选），随后即可启动 Run。</p>
          </div>

          <el-form :model="form" label-position="top" class="modern-form">
            <el-form-item label="参数方案">
              <el-select v-model="form.paramSchemeKey" :disabled="!!form.presetId || !form.algorithmId" class="full-width-select">
                <el-option label="系统内置默认参数" value="__default__" />
                <el-option v-for="entry in userSchemeEntries" :key="entry.id" :label="`用户自定义：${entry.name}`" :value="`__user__${entry.id}`" />
              </el-select>
            </el-form-item>

            <el-form-item label="运行参数预览">
              <div class="readonly-param-container">
                <div v-if="paramDisplayRows.length === 0" class="readonly-empty">当前算法无需配置参数</div>
                <div class="param-cards-grid">
                  <div v-for="row in paramDisplayRows" :key="row.key" class="param-info-card">
                    <div class="param-info-head">
                      <span class="param-info-key">{{ row.key }}</span>
                      <span class="param-info-val">{{ row.value }}</span>
                    </div>
                    <div class="param-info-desc">{{ row.explain }}</div>
                  </div>
                </div>
              </div>
            </el-form-item>

            <el-form-item label="另存为新预设 (可选)">
              <div class="save-preset-row">
                <el-input v-model="form.presetName" :disabled="!!form.presetId" placeholder="输入预设名称，如：去雾-DCP-实验A" />
                <el-button 
                  type="success" 
                  plain 
                  :disabled="!!form.presetId || !form.presetName.trim()" 
                  class="centered-btn"
                  @click="savePreset"
                >
                  保存预设
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>

        <div class="form-footer">
          <div class="footer-left">
            <el-button v-if="activeStep > 0" size="large" class="centered-btn" @click="activeStep--">上一步</el-button>
          </div>
          <div class="footer-center">
            <el-button v-if="activeStep < 2" type="primary" size="large" class="centered-btn" :disabled="!isNextEnabled" @click="activeStep++">下一步</el-button>
            <el-button v-if="activeStep === 2" type="primary" size="large" class="launch-btn centered-btn" @click="create">启动评测任务</el-button>
          </div>
          <div class="footer-right">
            <!-- Space for balance -->
          </div>
        </div>
      </div>
    </el-card>

    <div class="page-tips">
      <el-icon><InfoFilled /></el-icon>
      <span>温馨提示：系统会自动校验数据集的输入与 GT 配对情况，若配对数为 0 则无法启动任务。</span>
    </div>
  </div>

</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { TASK_LABEL_BY_TYPE, useAppStore, toTaskLabel, toTaskType } from "../stores/app";

const NEWRUN_CACHE_KEY = "newrun_form_v2";
function isBuiltinAlgorithm(alg) {
  return String(alg?.raw?.owner_id || "") === "system" && String(alg?.id || "").startsWith("alg_");
}
const router = useRouter();
const store = useAppStore();
const applyingPreset = ref(false);
const activeStep = ref(0);

// 使用ref创建响应式的metrics变量
const metrics = ref(["PSNR", "SSIM"]);
const ALLOWED_METRICS = ["PSNR", "SSIM", "NIQE"];

const isNextEnabled = computed(() => {
  if (activeStep.value === 0) return !!form.taskType && !!form.datasetId;
  if (activeStep.value === 1) return !!form.algorithmId && metrics.value.length > 0;
  return true;
});

function getTaskIcon(type) {
  const map = {
    denoise: "MagicStick",
    deblur: "Aim",
    dehaze: "Cloudy",
    sr: "FullScreen",
    lowlight: "Moon",
    video_denoise: "VideoPlay",
    video_sr: "VideoCamera",
  };
  return map[type] || "Menu";
}

const datasetHintType = computed(() => {
  if (!form.datasetId) return "info";
  const d = selectedDataset.value;
  const pairs = (d?.meta?.pairs_by_task) || (d?.raw?.meta?.pairs_by_task) || {};
  return Number(pairs?.[form.taskType] ?? 0) > 0 ? "success" : "warning";
});

const form = reactive({
  presetId: "",
  presetName: "",
  taskType: "denoise",
  datasetId: "",
  algorithmId: "",
  metrics: [], // 不再使用，改用metrics.value
  paramSchemeKey: "__default__",
  paramsText: "{}",
  strictValidate: true,
});

try {
  const raw = localStorage.getItem(NEWRUN_CACHE_KEY);
  if (raw) {
    const cached = JSON.parse(raw);

    if (typeof cached.taskType === "string") form.taskType = cached.taskType;
    else if (typeof cached.task === "string") form.taskType = toTaskType(cached.task);
    if (cached.datasetId) form.datasetId = cached.datasetId;
    if (cached.algorithmId) form.algorithmId = cached.algorithmId;
    if (Array.isArray(cached.metrics)) metrics.value = cached.metrics;
    if (typeof cached.paramsText === "string") form.paramsText = cached.paramsText;
    if (typeof cached.presetId === "string") form.presetId = cached.presetId;
    if (typeof cached.presetName === "string") form.presetName = cached.presetName;
    form.strictValidate = true;
  }
} catch {
  // ignore
}


watch(
  () => ({ ...form, metrics: Array.isArray(metrics.value) ? [...metrics.value] : [] }),
  (val) => {
    localStorage.setItem(NEWRUN_CACHE_KEY, JSON.stringify(val));
  },
  { deep: true }
);

const taskTypeOptions = computed(() =>
  Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label }))
);

const filteredAlgorithms = computed(() =>
  store.algorithms.filter((a) => a.task === toTaskLabel(form.taskType) && isBuiltinAlgorithm(a))
);

const presetsAll = computed(() => {
  const sorted = (store.presets || [])
    .slice()
    .sort((a, b) => (b?.raw?.updated_at || b?.raw?.created_at || 0) - (a?.raw?.updated_at || a?.raw?.created_at || 0));
  const seen = new Set();
  const out = [];
  for (const p of sorted) {
    const key = `${normalizePresetName(p?.name || "")}|${String(p?.taskType || "")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(p);
  }
  return out;
});

const selectedAlgorithm = computed(() =>
  store.algorithms.find((a) => a.id === form.algorithmId)
);

const PARAM_DOCS = {
  dcp_patch: "暗通道窗口，越大去雾更强，但细节更容易被抹平。",
  dcp_omega: "去雾强度，越大去雾越明显。",
  dcp_t0: "最小透射率，用于限制暗区噪声。",
  clahe_clip_limit: "局部对比度上限，越大对比更强。",
  gamma: "亮度伽马，小于1提亮暗部。",
  lowlight_gamma: "低照增强强度，建议0.5~0.8起步。",
  nlm_h: "去噪强度，越大去噪越强。",
  nlm_hColor: "色彩去噪强度，建议与nlm_h接近。",
  nlm_templateWindowSize: "模板窗口大小，常用奇数7。",
  nlm_searchWindowSize: "搜索窗口大小，常用奇数21。",
  bilateral_d: "双边滤波邻域直径。",
  bilateral_sigmaColor: "色域平滑系数。",
  bilateral_sigmaSpace: "空间平滑系数。",
  gaussian_sigma: "高斯标准差，越大模糊越强。",
  median_ksize: "中值核大小，应为奇数。",
  unsharp_sigma: "锐化半径，控制作用范围。",
  unsharp_amount: "锐化强度，越大边缘越锐。",
  laplacian_strength: "拉普拉斯锐化强度。",
};
const SYSTEM_PARAM_KEYS = new Set(["param_scheme", "user_scheme_name"]);

const paramDisplayRows = computed(() => {
  let obj = {};
  try {
    const s = String(form.paramsText || "").trim();
    const parsed = s ? JSON.parse(s) : {};
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) obj = parsed;
  } catch {
    obj = {};
  }
  return Object.entries(obj)
    .filter(([key]) => !SYSTEM_PARAM_KEYS.has(String(key)))
    .map(([key, value]) => ({
      key,
      value: String(value),
      explain: PARAM_DOCS[key] || "当前参数暂无内置说明",
    }));
});

const selectedDataset = computed(() =>
  store.datasets.find((d) => d.id === form.datasetId)
);

const userSchemeEntries = computed(() => {
  const alg = selectedAlgorithm.value;
  if (!alg) return [];
  const base = normalizeSchemeBaseName(alg.name);
  return store.algorithms
    .filter((x) => !isBuiltinAlgorithm(x) && x?.task === alg.task)
    .map((x) => ({
      id: String(x.id || ""),
      name: String(x.name || ""),
      params: x?.defaultParams && typeof x.defaultParams === "object" && !Array.isArray(x.defaultParams) ? x.defaultParams : {},
      base: normalizeSchemeBaseName(x?.name || ""),
    }))
    .filter((x) => x.base === base);
});

watch(
  () => form.paramSchemeKey,
  () => {
    if (!form.algorithmId) return;
    if (applyingPreset.value) return;
    if (form.paramSchemeKey !== "__default__" && !String(form.paramSchemeKey).startsWith("__user__")) {
      form.paramSchemeKey = "__default__";
      return;
    }
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
  () => filteredAlgorithms.value.map((a) => a.id).join("|"),
  () => {
    if (applyingPreset.value) return;
    if (form.algorithmId && filteredAlgorithms.value.some((a) => a.id === form.algorithmId)) return;
    form.algorithmId = filteredAlgorithms.value[0]?.id || "";
  }
);

watch(
  () => form.algorithmId,
  () => {
    if (applyingPreset.value) return;
    const alg = selectedAlgorithm.value;
    const obj =
      alg?.defaultParams && typeof alg.defaultParams === "object" && !Array.isArray(alg.defaultParams)
        ? alg.defaultParams
        : {};
    form.paramSchemeKey = "__default__";
    form.paramsText = JSON.stringify(obj, null, 2);
  }
);

watch(
  () => selectedAlgorithm.value?.id,
  () => {
    if (applyingPreset.value) return;
    if (!form.algorithmId) return;
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
  // 直接更新表单数据
  form.presetName = p.name || "";
  form.taskType = p.taskType;
  form.datasetId = p.datasetId || "";
  form.algorithmId = p.algorithmId || "";
  metrics.value = normalizeMetrics(p.metrics);
  const params = p.params && typeof p.params === "object" && !Array.isArray(p.params) ? p.params : {};
  form.paramSchemeKey = resolveSchemeKeyByParams(params);
  form.paramsText = JSON.stringify(params, null, 2);
}

function normalizeMetrics(list) {
  if (!Array.isArray(list)) return ["PSNR", "SSIM"];
  const normalized = list
    .map((item) => String(item || "").trim().toUpperCase())
    .filter((item) => ALLOWED_METRICS.includes(item));
  return normalized.length ? [...new Set(normalized)] : ["PSNR", "SSIM"];
}

watch(
  () => form.presetId,
  (newVal) => {
    if (!newVal) return;
    applyPreset();
  }
);

function applyParamScheme() {
  const alg = selectedAlgorithm.value;
  if (!alg) return;

  if (form.paramSchemeKey === "__default__") {
    const obj =
      alg?.defaultParams && typeof alg.defaultParams === "object" && !Array.isArray(alg.defaultParams)
        ? alg.defaultParams
        : {};
    form.paramsText = JSON.stringify(obj, null, 2);
    return;
  }

  if (String(form.paramSchemeKey).startsWith("__user__")) {
    const sid = String(form.paramSchemeKey).replace("__user__", "");
    const found = userSchemeEntries.value.find((x) => x.id === sid);
    if (!found) return;
    form.paramsText = JSON.stringify(found.params, null, 2);
  }
}

function _normalizeParamObj(x) {
  const src = x && typeof x === "object" && !Array.isArray(x) ? x : {};
  const out = {};
  for (const k of Object.keys(src).sort()) out[k] = src[k];
  return out;
}

function _sameParams(a, b) {
  return JSON.stringify(_normalizeParamObj(a)) === JSON.stringify(_normalizeParamObj(b));
}

function resolveSchemeKeyByParams(params) {
  const alg = selectedAlgorithm.value;
  if (!alg) return "__default__";
  const def = alg?.defaultParams && typeof alg.defaultParams === "object" && !Array.isArray(alg.defaultParams) ? alg.defaultParams : {};
  if (_sameParams(params, def)) return "__default__";
  const hit = userSchemeEntries.value.find((x) => _sameParams(params, x.params));
  if (hit) return `__user__${hit.id}`;
  return "__default__";
}

function normalizeSchemeBaseName(name) {
  const n = String(name || "").trim();
  if (!n.endsWith("）")) return n;
  const i = n.lastIndexOf("（");
  if (i <= 0) return n;
  return n.slice(0, i);
}

function normalizePresetName(name) {
  return String(name || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

async function scanSelectedDataset() {
  if (!form.datasetId) return;
  try {
    await store.scanDataset(form.datasetId);
    ElMessage({ type: "success", message: "扫描完成" });
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
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
  if (n > 0) return `${d?.name || "-"}（${d?.type || "-"}）- 可用配对 ${n}`;
  return `${d?.name || "-"}（${d?.type || "-"}）- 可用配对 0`;
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
  if (Number.isFinite(n) && n > 0) return `当前任务可用配对：${n} 组（已检测输入/gt）`;
  return "当前任务配对数为 0，请检查 gt 目录与输入目录后重新扫描。";
});

async function savePreset() {
  if (!form.presetName.trim()) return ElMessage({ type: "warning", message: "请填写预设名称" });
  if (!form.datasetId) return ElMessage({ type: "warning", message: "请先选择数据集" });
  if (!form.algorithmId) return ElMessage({ type: "warning", message: "请先选择算法" });
  if (!metrics.value.length) return ElMessage({ type: "warning", message: "请至少选择一个指标" });
  {
    const wanted = normalizePresetName(form.presetName);
    const dup = (store.presets || []).find(
      (p) =>
        normalizePresetName(p?.name || "") === wanted &&
        String(p?.taskType || "") === String(form.taskType || "")
    );
    if (dup) return ElMessage({ type: "warning", message: `预设名称重复：当前任务下已存在「${dup.name}」` });
  }

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return ElMessage({ type: "error", message: `参数 JSON 解析失败：${e?.message || e}` });
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return ElMessage({ type: "error", message: '参数必须是 JSON 对象，例如 { "dcp_patch": 15 }' });
  }
  if (!Object.prototype.hasOwnProperty.call(params, "param_scheme")) {
    if (form.paramSchemeKey === "__default__") {
      params.param_scheme = "default";
    } else if (String(form.paramSchemeKey).startsWith("__user__")) {
      const sid = String(form.paramSchemeKey).replace("__user__", "");
      const picked = userSchemeEntries.value.find((x) => x.id === sid);
      params.param_scheme = picked?.name ? `user:${picked.name}` : "user";
      if (picked?.name) params.user_scheme_name = picked.name;
    }
  }

  try {
    const out = await store.createPreset({
      name: form.presetName.trim(),
      task: toTaskLabel(form.taskType),
      datasetId: form.datasetId,
      algorithmId: form.algorithmId,
      metrics: [...metrics.value],
      params,
    });
    form.presetId = out?.id || "";
    form.presetName = "";
    ElMessage({ type: "success", message: "预设保存成功" });
  } catch (e) {
    ElMessage({ type: "error", message: `保存预设失败：${e?.message || e}` });
  }
}

async function removePreset() {
  if (!form.presetId) return;
  try {
    await ElMessageBox.confirm("确认删除当前预设吗？", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    await store.removePreset(form.presetId);
    form.presetId = "";
    ElMessage({ type: "success", message: "预设已删除" });
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `删除预设失败：${e?.message || e}` });
  }
}

function clearPreset() {
  form.presetId = "";
  form.presetName = "";
  ElMessage({ type: "info", message: "已清除预设，表单已解锁" });
}

async function create() {
  if (!form.datasetId) return ElMessage({ type: "warning", message: "请先选择数据集" });
  if (!form.algorithmId) return ElMessage({ type: "warning", message: "请先选择算法" });
  if (!metrics.value.length) return ElMessage({ type: "warning", message: "请至少选择一个指标" });

  const tt = form.taskType;
  const d = selectedDataset.value;
  const pairs =
    (d?.meta?.pairs_by_task && typeof d.meta.pairs_by_task === "object" ? d.meta.pairs_by_task : null) ||
    (d?.raw?.meta?.pairs_by_task && typeof d.raw.meta.pairs_by_task === "object" ? d.raw.meta.pairs_by_task : {}) ||
    {};
  const pairCount = Number(pairs?.[tt] ?? 0);
  if (!Number.isFinite(pairCount) || pairCount <= 0) {
    return ElMessage({ type: "error", message: "当前任务配对数为 0，无法创建 Run。请先扫描并修复输入/gt配对。" });
  }

  let params = {};
  try {
    const s = String(form.paramsText || "").trim();
    params = s ? JSON.parse(s) : {};
  } catch (e) {
    return ElMessage({ type: "error", message: `参数 JSON 解析失败：${e?.message || e}` });
  }
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return ElMessage({ type: "error", message: '参数必须是 JSON 对象，例如 { "dcp_patch": 15 }' });
  }
  if (!Object.prototype.hasOwnProperty.call(params, "param_scheme")) {
    if (form.paramSchemeKey === "__default__") {
      params.param_scheme = "default";
    } else if (String(form.paramSchemeKey).startsWith("__user__")) {
      const sid = String(form.paramSchemeKey).replace("__user__", "");
      const picked = userSchemeEntries.value.find((x) => x.id === sid);
      params.param_scheme = picked?.name ? `user:${picked.name}` : "user";
      if (picked?.name) params.user_scheme_name = picked.name;
    }
  }

  try {
    await store.createRun({
      task: toTaskLabel(form.taskType),
      datasetId: form.datasetId,
      algorithmId: form.algorithmId,
      metrics: [...metrics.value],
      params,
      strictValidate: true,
    });
    // 让用户选择是否留在当前页面或转到任务中心
    try {
      await ElMessageBox.confirm(
        "Run 创建成功，是否跳转到任务中心查看？",
        "操作选择",
        {
          confirmButtonText: "转到任务中心",
          cancelButtonText: "留在当前页面",
          type: "success"
        }
      );
      // 用户选择转到任务中心
      router.push("/runs");
    } catch (e) {
      // 用户选择留在当前页面或取消
      if (e !== "cancel" && e !== "close") {
        throw e;
      }
      // 重置到第一步，但保留预设等内容
      activeStep.value = 0;
    }
  } catch (e) {
    const d = e?.detail;
    if (d && typeof d === "object") {
      const code = d.error_code || d.error || "";
      if (code === "dataset_no_pairs_for_task" || code === "E_DATASET_NO_PAIR") {
        const dirs = Array.isArray(d.expected_dirs) ? d.expected_dirs.join(" + ") : "";
        const hint = dirs ? `建议目录：${dirs}` : "请检查 gt 目录与输入目录";
        try {
          await ElMessageBox.confirm(`${d.message || "当前数据集无有效配对"}\n${hint}\n是否立即扫描数据集？`, "数据集提示", {
            type: "warning",
            confirmButtonText: "立即扫描",
            cancelButtonText: "稍后",
          });
          try {
            await scanSelectedDataset();
          } catch {
          }
        } catch {
        }
        return;
      }
      if (code === "algorithm_task_mismatch" || code === "E_ALGORITHM_TASK_MISMATCH") {
        const tip = `任务：${d.task_label || d.task_type || "-"}，算法任务：${d.algorithm_task || "-"}，期望：${d.expected_algorithm_task || "-"}`;
        return ElMessage({ type: "error", message: `${d.message || "算法任务类型不匹配"}；${tip}` });
      }
      if (d.message) return ElMessage({ type: "error", message: `创建失败：${d.message}` });
    }
    ElMessage({ type: "error", message: `创建 Run 失败：${e?.message || e}` });
  }
}

function getPresetMetrics() {
  if (!form.presetId) return "无";
  const preset = presetsAll.value.find(p => p.id === form.presetId);
  return preset?.metrics?.join(', ') || "无";
}

// 检查指标是否被选中
function isMetricSelected(metric) {
  return metrics.value.includes(metric);
}

function toggleMetric(metric) {
  if (form.presetId) return;
  const next = normalizeMetrics(metrics.value);
  if (next.includes(metric)) {
    metrics.value = next.filter((item) => item !== metric);
    return;
  }
  metrics.value = [...next, metric];
}

function goRuns() {
  router.push("/runs");
}
</script>

<style scoped>
.page {
  padding: 24px;
  background-color: #f8fbff;
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
}

.page-subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 14px;
}

.centered-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.centered-btn > span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

/* Main Card & Steps */
.main-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  padding: 20px;
}

.steps-wrapper {
  max-width: 800px;
  margin: 0 auto 40px;
}

.custom-steps {
  --el-color-primary: #2f6bff;
}

.form-container {
  max-width: 800px;
  margin: 0 auto;
}

/* Step Content */
.step-header {
  margin-bottom: 30px;
  border-left: 4px solid #2f6bff;
  padding-left: 16px;
}

.step-title {
  margin: 0;
  font-size: 18px;
  color: #1e293b;
  font-weight: 700;
}

.step-desc {
  margin: 8px 0 0;
  font-size: 14px;
  color: #64748b;
}

/* Task Cards */
.task-options {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
  width: 100%;
}

.task-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: white;
}

.task-card:hover:not(.disabled) {
  border-color: #2f6bff;
  background-color: #f0f7ff;
}

.task-card.active {
  border-color: #2f6bff;
  background-color: #eff6ff;
  box-shadow: 0 0 0 1px #2f6bff;
}

.task-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.task-icon {
  font-size: 24px;
  color: #64748b;
  transition: color 0.2s;
}

.task-card.active .task-icon {
  color: #2f6bff;
}

.task-info {
  text-align: center;
}

.task-label {
  font-weight: 700;
  color: #1e293b;
  font-size: 14px;
}

.task-val {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.active-check {
  position: absolute;
  top: 8px;
  right: 8px;
  color: #2f6bff;
  display: none;
}

.task-card.active .active-check {
  display: block;
}

/* Form Styles */
.modern-form :deep(.el-form-item__label) {
  font-weight: 700;
  color: #475569;
  padding-bottom: 8px;
}

.full-width-select {
  width: 100%;
}

.dataset-alert {
  margin-top: 12px;
}

.scan-btn {
  margin-top: 8px;
}

.preset-box {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.preset-actions {
  display: flex;
  gap: 8px;
}

.preset-alert {
  margin-top: 12px;
}

.metrics-group {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.metric-chip {
  appearance: none;
  border: 1px solid #cddcf7;
  background: #ffffff;
  color: #64748b;
  border-radius: 14px;
  min-width: 88px;
  height: 38px;
  padding: 0 18px;
  font-size: 14px;
  line-height: 38px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.metric-chip:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #2563eb;
}

.metric-chip.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.18);
}

.metric-chip.metric-chip-wide {
  min-width: 152px;
}

.metric-chip:disabled {
  cursor: not-allowed;
  opacity: 1;
}

.metric-chip.locked {
  background: #f8fbff;
  border-color: #cddcf7;
  color: #94a3b8;
}

.metric-chip.locked.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
}


/* Parameters Preview */
.readonly-param-container {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.param-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.param-info-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
}

.param-info-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.param-info-key {
  font-weight: 700;
  font-size: 13px;
  color: #334155;
}

.param-info-val {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #2563eb;
  font-size: 13px;
}

.param-info-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.readonly-empty {
  color: #94a3b8;
  text-align: center;
  padding: 20px;
}

.save-preset-row {
  display: flex;
  gap: 12px;
}

/* Footer & Tips */
.form-footer {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left, .footer-right {
  flex: 1;
}

.footer-center {
  flex: 2;
  display: flex;
  justify-content: center;
  gap: 16px;
}

.footer-right {
  display: flex;
  justify-content: flex-end;
}

.launch-btn {
  padding-left: 32px;
  padding-right: 32px;
  box-shadow: 0 4px 12px rgba(47, 107, 255, 0.25);
}

.page-tips {
  margin-top: 24px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
  justify-content: center;
}

.page-tips .el-icon {
  color: #2f6bff;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}

:deep(.el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px #2f6bff inset !important;
}
</style>
