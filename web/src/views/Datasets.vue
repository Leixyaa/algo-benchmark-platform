<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">数据集管理</h2>
      <div class="subtitle">
        支持创建、上传和扫描数据集，推荐通过 ZIP 导入并统一纳入平台管理。
      </div>
    </div>

    <div class="action-bar">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button type="primary" class="centered-btn action-btn" @click="openCreate" :disabled="!store.user.isLoggedIn">新建数据集</el-button>
          <el-button class="centered-btn action-btn" @click="chooseZipForNew" :disabled="!store.user.isLoggedIn">导入 ZIP</el-button>
        </div>
        <el-button @click="showDatasetLayoutGuide" class="guide-btn centered-btn action-btn">目录规范说明</el-button>
      </div>

      <div class="selector-row">
        <div class="selector-left">
          <span class="label">当前选择：</span>
          <el-select v-model="selectedDatasetId" placeholder="请选择数据集" class="select-box" filterable>
            <el-option v-for="d in ownedDatasets" :key="d.id" :label="`${d.name} (${d.id})`" :value="d.id" />
          </el-select>
          <el-checkbox v-model="overwriteOnImport" label="导入时覆盖原有目录内容" class="checkbox compact-checkbox" />
        </div>
        <el-button
          type="success"
          class="scan-btn centered-btn action-btn"
          :loading="selectedDatasetExists && scanningDatasets.has(selectedDatasetId)"
          :disabled="!store.user.isLoggedIn || !selectedDatasetExists"
          @click="scanCurrent"
        >
          {{ scanningDatasets.has(selectedDatasetId) ? "扫描中..." : "扫描当前数据集" }}
        </el-button>
      </div>
    </div>

    <div class="section-block">
      <el-tabs v-model="activeDatasetTab" class="resource-tabs">
        <el-tab-pane label="用户数据集" name="owned">
          <el-table :data="ownedDatasets" border stripe class="data-table">
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column prop="type" label="类型" width="110">
              <template #default="{ row }">
                <el-tag :type="row.type === '视频' ? 'warning' : 'success'" size="small">{{ row.type || "-" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="规模" width="190">
              <template #default="{ row }">
                <span class="size-cell" :title="row.size || '-'">{{ row.size || "-" }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="创建时间" width="180" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleDatasetAction(row.id, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="scanningDatasets.has(row.id) || exportingDatasets.has(row.id)" :disabled="!store.user.isLoggedIn">
                    管理<el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="id">查看/修改ID</el-dropdown-item>
                      <el-dropdown-item command="community">{{ row.visibility === "public" ? "更新社区信息" : "上传到社区" }}</el-dropdown-item>
                      <el-dropdown-item command="export">下载到本地</el-dropdown-item>
                      <el-dropdown-item command="scan">重新扫描</el-dropdown-item>
                      <el-dropdown-item command="zip">导入 ZIP</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无用户数据集" />
            </template>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="社区数据集" name="community">
          <el-table :data="downloadedDatasets" border stripe class="data-table">
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column prop="type" label="类型" width="110">
              <template #default="{ row }">
                <el-tag :type="row.type === '视频' ? 'warning' : 'success'" size="small">{{ row.type || "-" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="规模" width="190">
              <template #default="{ row }">
                <span class="size-cell" :title="row.size || '-'">{{ row.size || "-" }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="sourceUploaderId" label="上传者ID" width="140" />
            <el-table-column prop="createdAt" label="下载时间" width="180" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleDatasetAction(row.id, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="scanningDatasets.has(row.id) || exportingDatasets.has(row.id)" :disabled="!store.user.isLoggedIn">
                    管理<el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="export">下载到本地</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无社区数据集" />
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="showCreate" title="新建数据集" width="460px">
      <el-form :model="form" label-position="top">
        <el-form-item label="数据集名称">
          <el-input v-model="form.name" placeholder="例如：RESIDE Indoor 测试集" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="图像" value="图像" />
            <el-option label="视频" value="视频" />
            <el-option label="图像/视频" value="图像/视频" />
          </el-select>
        </el-form-item>
        <el-form-item label="规模描述">
          <el-input v-model="form.size" placeholder="例如：500 张 / 30 段" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="centered-btn" @click="closeCreate">取消</el-button>
        <el-button type="primary" class="centered-btn" @click="submitCreate">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, ElNotification } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { authFetch } from "../api/http";
import { datasetsApi } from "../api/datasets";
import { useAppStore } from "../stores/app";

const store = useAppStore();

const showCreate = ref(false);
const activeDatasetTab = ref("owned");
const selectedDatasetId = ref("");
const overwriteOnImport = ref(true);
const importTargetId = ref("");
const fileInputRef = ref(null);
const scanningDatasets = ref(new Set());
const exportingDatasets = ref(new Set());

const form = reactive({
  name: "",
  type: "图像",
  size: "",
});

const visibleDatasets = computed(() =>
  (store.datasets || []).filter((d) => String(d?.raw?.owner_id || "") === String(store.user?.username || ""))
);

const ownedDatasets = computed(() => visibleDatasets.value.filter((d) => !String(d?.sourceUploaderId || "").trim()));
const downloadedDatasets = computed(() => visibleDatasets.value.filter((d) => String(d?.sourceUploaderId || "").trim()));
const selectedDatasetExists = computed(() => ownedDatasets.value.some((d) => d.id === selectedDatasetId.value));

function getDatasetById(id) {
  return visibleDatasets.value.find((item) => item.id === id) || null;
}

function isDatasetEmpty(dataset) {
  if (!dataset) return true;
  const sizeText = String(dataset.size || "").trim();
  if (/^0\s*(张|段)?$/u.test(sizeText)) return true;
  const meta = dataset.raw?.meta && typeof dataset.raw.meta === "object" ? dataset.raw.meta : {};
  const countsByDir = meta.counts_by_dir && typeof meta.counts_by_dir === "object" ? meta.counts_by_dir : {};
  const hasPositiveCount = Object.values(countsByDir).some((value) => Number(value || 0) > 0);
  if (Object.keys(countsByDir).length) return !hasPositiveCount;
  return false;
}

onMounted(async () => {
  try {
    await store.fetchDatasets();
  } catch {
    // ignore
  }
});

watch(
  ownedDatasets,
  (datasets) => {
    const exists = (datasets || []).some((d) => d.id === selectedDatasetId.value);
    if (!exists) selectedDatasetId.value = "";
    if (!selectedDatasetId.value && (datasets || []).length) {
      selectedDatasetId.value = datasets[0].id;
    }
  },
  { deep: true, immediate: true }
);

function openCreate() {
  form.name = "";
  form.type = "图像";
  form.size = "";
  showCreate.value = true;
}

function closeCreate() {
  showCreate.value = false;
}

function showDatasetLayoutGuide() {
  ElMessageBox.alert(
    [
      "1) 推荐目录包含 gt 与任务输入目录，如 hazy/noisy/blur/lr/dark。",
      "2) 视频任务依靠创建 Run 时选择 video_denoise 或 video_sr 区分。",
      "3) 视频任务要求输入目录与 gt 目录中的视频文件同名配对。",
      "4) 推荐统一通过 ZIP 上传数据集，由平台自动管理存储目录。",
      "5) 本机数据若不能直接访问，请先使用 ZIP 导入。",
    ].join("\n"),
    "目录与上线说明",
    { confirmButtonText: "我知道了" }
  );
}

async function submitCreate() {
  if (!form.name.trim()) {
    ElMessage({ type: "warning", message: "请填写数据集名称" });
    return;
  }
  try {
    const created = await store.createDataset({
      name: form.name.trim(),
      type: String(form.type || "图像"),
      size: form.size.trim() || "-",
      visibility: "private",
      allowUse: false,
      allowDownload: false,
    });
    const finalId = created?.id || "";
    if (!finalId) {
      ElMessage({ type: "error", message: "创建成功但未返回数据集 ID" });
      return;
    }
    await scanOne(finalId, { silentStart: true });
    selectedDatasetId.value = finalId;
    showCreate.value = false;
    ElMessage({ type: "success", message: "数据集已创建并扫描完成，默认保存在用户数据集中" });
  } catch (e) {
    ElMessage({ type: "error", message: `创建失败：${e?.message || e}` });
  }
}

async function remove(id) {
  let deleteDisk = false;
  try {
    await ElMessageBox.confirm(
      "确认删除该数据集吗？\n选择“删除并删除磁盘”会同时移除当前账号下该数据集的磁盘目录。",
      "删除确认",
      {
        type: "warning",
        confirmButtonText: "删除并删除磁盘",
        cancelButtonText: "仅删除记录",
        distinguishCancelAndClose: true,
      }
    );
    deleteDisk = true;
  } catch (action) {
    if (action === "cancel") {
      deleteDisk = false;
    } else {
      return;
    }
  }

  try {
    await store.removeDataset(id, { deleteDisk });
    if (selectedDatasetId.value === id) {
      selectedDatasetId.value = "";
    }
    ElMessage({ type: "success", message: deleteDisk ? "数据集和磁盘目录已删除" : "数据集记录已删除" });
  } catch (e) {
    ElMessage({ type: "error", message: `删除失败：${e?.message || e}` });
  }
}

async function handleDatasetAction(id, command) {
  const owned = ownedDatasets.value.some((item) => item.id === id);
  if (!owned && ["id", "community", "scan", "zip"].includes(command)) {
    ElMessage({ type: "warning", message: "社区数据集不能修改，请先下载后在用户数据集中管理" });
    return;
  }
  if (command === "id") {
    await editDatasetId(id);
    return;
  }
  if (command === "community") {
    await uploadDatasetToCommunity(id);
    return;
  }
  if (command === "scan") {
    await scanOne(id);
    return;
  }
  if (command === "export") {
    await exportDatasetToLocal(id);
    return;
  }
  if (command === "zip") {
    chooseZipFor(id);
    return;
  }
  if (command === "delete") {
    await remove(id);
  }
}

async function exportDatasetToLocal(id) {
  if (!id) return;
  if (exportingDatasets.value.has(id)) return;
  const current = getDatasetById(id);
  if (isDatasetEmpty(current)) {
    ElMessage({ type: "warning", message: "空数据集不能下载到本地，请先导入 ZIP 或补充有效文件" });
    return;
  }
  try {
    const nextExporting = new Set(exportingDatasets.value);
    nextExporting.add(id);
    exportingDatasets.value = nextExporting;
    ElMessage({ type: "info", message: "正在准备下载数据集，请稍候..." });
    const result = await datasetsApi.exportDataset(id);
    ElMessage({
      type: "success",
      message: result?.savedWithPicker ? "数据集已保存到你选择的位置" : "数据集已开始下载到本地",
    });
  } catch (e) {
    ElMessage({ type: "error", message: `下载到本地失败：${e?.message || e}` });
  } finally {
    const nextExporting = new Set(exportingDatasets.value);
    nextExporting.delete(id);
    exportingDatasets.value = nextExporting;
  }
}

async function uploadDatasetToCommunity(id) {
  const current = ownedDatasets.value.find((item) => item.id === id);
  if (!current) {
    ElMessage({ type: "warning", message: "未找到当前数据集" });
    return;
  }
  if (isDatasetEmpty(current)) {
    ElMessage({ type: "warning", message: "空数据集不能上传到社区，请先导入 ZIP 或补充有效文件" });
    return;
  }
  try {
    const { value } = await ElMessageBox.prompt(
      "请输入数据集在社区中心展示的描述",
      current.visibility === "public" ? "更新社区信息" : "上传到社区",
      {
        inputType: "textarea",
        inputValue: String(current.description || ""),
        inputPlaceholder: "例如：适用于图像去雾任务，包含 gt 与 hazy 配对样本。",
        confirmButtonText: current.visibility === "public" ? "保存" : "上传",
        cancelButtonText: "取消",
      }
    );
    await store.updateDataset(id, {
      description: String(value || "").trim(),
      visibility: "public",
      allowUse: true,
      allowDownload: true,
    });
    ElMessage({ type: "success", message: current.visibility === "public" ? "社区信息已更新" : "数据集已上传到社区" });
  } catch (action) {
    if (action !== "cancel" && action !== "close") {
      ElMessage({ type: "error", message: `上传社区失败：${action?.message || action}` });
    }
  }
}

async function editDatasetId(id) {
  const current = visibleDatasets.value.find((item) => item.id === id);
  if (!current) {
    ElMessage({ type: "warning", message: "未找到当前数据集" });
    return;
  }
  try {
    const { value } = await ElMessageBox.prompt(
      `当前数据集 ID：${current.id}`,
      "查看/修改ID（测试开发）",
      {
        inputValue: current.id,
        confirmButtonText: "保存",
        cancelButtonText: "取消",
        inputPattern: /^[A-Za-z0-9._-]+$/,
        inputErrorMessage: "ID 仅支持字母、数字、点、下划线和短横线",
      }
    );
    const nextId = String(value || "").trim();
    if (!nextId || nextId === current.id) {
      ElMessage({ type: "info", message: "数据集ID未修改" });
      return;
    }
    const updated = await store.changeDatasetId(current.id, nextId);
    selectedDatasetId.value = updated?.id || nextId;
    ElMessage({ type: "success", message: "数据集ID已更新" });
  } catch (action) {
    if (action !== "cancel" && action !== "close") {
      ElMessage({ type: "error", message: `修改ID失败：${action?.message || action}` });
    }
  }
}

function ensureFileInput() {
  if (fileInputRef.value) return;
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".zip,application/zip";
  input.style.display = "none";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const dsId = importTargetId.value;
    if (!dsId) return;

    try {
      await ElMessageBox.confirm(
        `将向数据集 ${dsId} 导入 ZIP，${overwriteOnImport.value ? "会覆盖目录中的现有内容" : "不会先清空目录"}，是否继续？`,
        "导入确认",
        {
          type: "warning",
          confirmButtonText: "继续导入",
          cancelButtonText: "取消",
        }
      );
    } catch {
      return;
    }

    try {
      ElMessage({ type: "info", message: "正在导入 ZIP，请稍候..." });
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(
        `/datasets/${encodeURIComponent(dsId)}/import_zip_file`,
        {
          method: "POST",
          query: { overwrite: overwriteOnImport.value ? "true" : "false" },
          body: fd,
        }
      );
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const out = ct.includes("application/json") ? await res.json() : await res.text();
      if (!res.ok) {
        throw new Error(typeof out === "string" ? out : JSON.stringify(out));
      }
      await store.fetchDatasets();
      await scanOne(dsId, { silentStart: true });
      ElMessage({ type: "success", message: "ZIP 导入成功" });
    } catch (e) {
      ElMessage({ type: "error", message: `ZIP 导入失败：${e?.message || e}` });
    }
  });
  document.body.appendChild(input);
  fileInputRef.value = input;
}

function chooseZipFor(id) {
  importTargetId.value = id;
  ensureFileInput();
  fileInputRef.value.click();
}

function chooseZipForNew() {
  if (!selectedDatasetId.value) {
    ElMessage({ type: "warning", message: "请先选择一个数据集" });
    return;
  }
  chooseZipFor(selectedDatasetId.value);
}

async function scanOne(id, { silentStart = false } = {}) {
  if (!id) return null;
  if (scanningDatasets.value.has(id)) return null;
  try {
    const nextScanning = new Set(scanningDatasets.value);
    nextScanning.add(id);
    scanningDatasets.value = nextScanning;
    if (!silentStart) {
      ElMessage({ type: "info", message: `正在扫描数据集 ${id}...` });
    }
    const beforeType = getCurrentDatasetType(id, "");
    let ds = await store.scanDataset(id);
    ds = (await maybeSyncTypeByIdHint(id, ds, beforeType)) || ds;
    store.fetchDatasets().catch(() => {});
    const dtype = String(ds?.type || "");
    const tip = `${dtype || "-"}｜${ds?.size || "-"}`;
    const taskTip = formatScanTaskSummary(ds?.raw?.meta);
    ElMessage({ type: "success", message: taskTip ? `扫描完成：${tip}｜${taskTip}` : `扫描完成：${tip}` });
    return ds;
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
    return null;
  } finally {
    const nextScanning = new Set(scanningDatasets.value);
    nextScanning.delete(id);
    scanningDatasets.value = nextScanning;
  }
}

async function scanCurrent() {
  if (!selectedDatasetId.value) {
    ElMessage({ type: "warning", message: "请先选择一个数据集" });
    return;
  }
  await scanOne(selectedDatasetId.value);
}

function formatScanTaskSummary(meta) {
  const pairs = meta?.pairs_by_task && typeof meta.pairs_by_task === "object" ? meta.pairs_by_task : {};
  const labels = {
    dehaze: "去雾图片",
    denoise: "去噪图片",
    deblur: "去模糊图片",
    sr: "超分图片",
    lowlight: "低照度图片",
    video_denoise: "视频去噪",
    video_sr: "视频超分",
  };
  const unitOf = (key) => (String(key).startsWith("video_") ? "段" : "张");
  const items = Object.entries(pairs)
    .filter(([, count]) => Number(count || 0) > 0)
    .map(([key, count]) => `${labels[key] || key} ${count}${unitOf(key)}`);
  return items.join("，");
}

function guessTypeFromDatasetId(datasetId) {
  const value = String(datasetId || "").toLowerCase();
  if (/(video|vid|视频)/.test(value)) return "视频";
  if (/(image|img|图像|图片)/.test(value)) return "图像";
  return "";
}

function getCurrentDatasetType(datasetId, fallback = "") {
  const current = ownedDatasets.value.find((item) => item.id === datasetId);
  return String(current?.type || fallback || "");
}

async function maybeSyncTypeByIdHint(datasetId, scannedDataset, beforeType = "") {
  const ds = scannedDataset && typeof scannedDataset === "object" ? scannedDataset : null;
  if (!ds) return ds;
  const hinted = guessTypeFromDatasetId(datasetId);
  const currentType = String(ds?.type || beforeType || "").trim();
  const meta = ds?.raw?.meta && typeof ds.raw.meta === "object" ? ds.raw.meta : {};
  const inferred = String(meta?.inferred_type || "").trim();
  const mismatch = Boolean(meta?.type_mismatch) || Boolean(inferred && currentType && inferred !== currentType);
  if (!mismatch) return ds;
  if (hinted !== "视频" && !inferred) return ds;
  try {
    await ElMessageBox.confirm(
      `扫描识别类型为“${inferred || "未知"}”，当前类型为“${currentType || "未设置"}”。是否切换为“${inferred || "扫描类型"}”？`,
      "扫描类型确认",
      {
        type: "warning",
        confirmButtonText: `切换为${inferred || "扫描类型"}`,
        cancelButtonText: `保持${currentType || "当前类型"}`,
      }
    );
  } catch {
    ElNotification({
      title: "已保持当前类型",
      message: `当前保持“${currentType || "未设置"}”，仅更新了扫描统计。`,
      type: "info",
      duration: 2600,
    });
    return ds;
  }
  await store.updateDataset(datasetId, { type: inferred || currentType });
  const rescanned = await store.scanDataset(datasetId);
  await store.fetchDatasets();
  ElNotification({
    title: "类型已切换",
    message: `已切换为“${rescanned?.type || inferred}”，规模已按新类型口径重算。`,
    type: "success",
    duration: 3000,
  });
  return rescanned;
}
</script>

<style scoped>
.page {
  padding: 24px;
}

.header-section {
  margin-bottom: 24px;
}

.title {
  margin: 0 0 12px;
  font-size: 24px;
  font-weight: 700;
  color: #1f2f57;
}

.subtitle {
  color: #5b6b8b;
  line-height: 1.7;
}

.action-bar {
  margin-bottom: 24px;
  padding: 18px;
  background: #f8fbff;
  border: 1px solid #dce7ff;
  border-radius: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.selector-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.selector-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.label {
  color: #334466;
  font-weight: 600;
}

.select-box {
  width: 320px;
}

.section-block {
  margin-bottom: 24px;
}

.section-title {
  margin: 0 0 12px;
  color: #1f2f57;
}

.data-table {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.centered-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.action-btn {
  min-width: 132px;
  height: 42px;
  padding: 0 18px;
  border-radius: 12px;
}

.guide-btn,
.scan-btn {
  white-space: nowrap;
}

.scan-btn {
  min-width: 148px;
}

.compact-checkbox {
  min-height: 42px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
}

.checkbox {
  margin-left: 4px;
}

.size-cell {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-action-btn {
  min-width: 84px;
  justify-content: center;
}

.page :deep(.scan-result-box) {
  width: min(680px, calc(100vw - 32px));
  border-radius: 18px;
}

.page :deep(.scan-result-dialog) {
  display: grid;
  gap: 12px;
  padding-top: 4px;
}

.page :deep(.scan-result-row) {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.7;
  color: #334466;
  word-break: break-word;
}

.page :deep(.scan-result-label) {
  min-width: 72px;
  color: #1f2f57;
  font-weight: 700;
}

.data-table :deep(.el-table__cell) {
  height: 68px;
}

.data-table :deep(.cell) {
  white-space: nowrap;
}

@media (max-width: 768px) {
  .page {
    padding: 16px;
  }

  .select-box {
    width: 100%;
    min-width: 220px;
  }
}
</style>
