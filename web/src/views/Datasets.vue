<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">数据集管理</h2>
      <div class="subtitle">
        支持手动创建、磁盘快速登记、ZIP 导入与扫描。目录建议包含 gt/ 与输入目录（hazy/noisy/blur/lr/dark），视频任务使用 noisy/lr 与 gt 同文件名配对。
      </div>
    </div>

    <div class="action-bar">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button type="primary" icon="Plus" @click="openCreate">新建数据集</el-button>
          <el-button icon="Folder" @click="quickAddFromDisk">按ID登记磁盘目录</el-button>
          <el-button icon="Upload" @click="chooseZipForNew">导入 ZIP</el-button>
        </div>
        <el-button icon="QuestionFilled" @click="showDatasetLayoutGuide" class="guide-btn">目录规范说明</el-button>
      </div>

      <div class="selector-row">
        <div class="selector-left">
          <span class="label">当前选择：</span>
          <el-select v-model="selectedDatasetId" placeholder="请选择数据集" class="select-box" filterable>
            <el-option v-for="d in store.datasets" :key="d.id" :label="`${d.name}（${d.id}）`" :value="d.id" />
          </el-select>
          <el-checkbox v-model="overwriteOnImport" label="导入时覆盖原数据" class="checkbox" />
        </div>
        <el-button type="success" :loading="scanningDatasets.has(selectedDatasetId)" @click="scanCurrent" icon="Refresh" class="scan-btn">
          {{ scanningDatasets.has(selectedDatasetId) ? '扫描中...' : '扫描当前数据集' }}
        </el-button>
      </div>
    </div>

    <el-table :data="store.datasets" border style="width: 100%" class="data-table" stripe>
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.type === '视频' ? 'warning' : 'success'" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="size" label="规模" width="150" />
      <el-table-column prop="createdAt" label="创建时间" width="180" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(cmd) => handleDatasetAction(row.id, cmd)">
            <el-button size="small" :loading="scanningDatasets.has(row.id)">
              管理<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="scan" icon="Refresh" :disabled="scanningDatasets.has(row.id)">
                  扫描统计
                </el-dropdown-item>
                <el-dropdown-item command="zip" icon="Upload" :disabled="scanningDatasets.has(row.id)">
                  导入 ZIP
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided icon="Delete" type="danger" :disabled="scanningDatasets.has(row.id)">
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无数据集，请先创建或导入" />
      </template>
    </el-table>

    <el-dialog v-model="showCreate" title="新建数据集" width="460px" border-radius="12px">
      <el-form :model="form" label-position="top">
        <el-form-item label="数据集 ID">
          <el-input v-model="form.id" placeholder="如 ds_gopro_deblur_test（可选）" />
        </el-form-item>
        <el-form-item label="数据集名称">
          <el-input v-model="form.name" placeholder="如 RESIDE Indoor 测试集" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="图像" value="图像" />
            <el-option label="视频" value="视频" />
          </el-select>
        </el-form-item>
        <el-form-item label="规模描述">
          <el-input v-model="form.size" placeholder="如 500 张 / 30 段视频" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeCreate">取消</el-button>
        <el-button type="primary" @click="submitCreate">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useAppStore } from "../stores/app";
import { ElMessage, ElMessageBox, ElNotification } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";

const store = useAppStore();

const showCreate = ref(false);
const selectedDatasetId = ref("");
const overwriteOnImport = ref(true);
const importTargetId = ref("");
const fileInputRef = ref(null);
const form = reactive({
  id: "",
  name: "",
  type: "图像",
  size: "",
});

onMounted(async () => {
  try {
    await store.fetchDatasets();
    if (!selectedDatasetId.value && store.datasets?.length) {
      selectedDatasetId.value = store.datasets[0].id;
    }
  } catch {
    // ignore
  }
});

function openCreate() {
  form.id = "";
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
      "1) 图像/视频任务目录都可复用：gt + noisy/lr 等输入目录。",
      "2) 视频去噪与视频超分不是靠目录名区分，而是靠创建Run时选择任务类型（video_denoise / video_sr）。",
      "3) 视频任务要求：输入目录与 gt 目录中的视频文件必须同文件名配对。",
      "4) 上线Web后不能直接扫描访问用户本机磁盘，只能扫描服务器上的目录。",
      "5) 若要导入本机数据，请使用“导入ZIP”上传到服务器后再扫描。"
    ].join("\n"),
    "目录与上线说明",
    {
      confirmButtonText: "我知道了",
    }
  );
}

async function submitCreate() {
  if (!form.name.trim()) {
    ElMessage({ type: "warning", message: "请填写数据集名称" });
    return;
  }
  const wantedId = form.id.trim() || "";
  const wantedName = form.name.trim();
  let wantedType = String(form.type || "图像");
  let keepSelectedTypeAfterScan = false;
  const hintedType = guessTypeFromDatasetId(wantedId);
  if (hintedType && hintedType !== wantedType) {
    try {
      await ElMessageBox.confirm(
        `检测到数据集ID更像“${hintedType}”类型，但你当前选择的是“${wantedType}”。是否继续按当前类型创建？`,
        "创建前确认",
        {
          type: "warning",
          confirmButtonText: `继续按${wantedType}创建`,
          cancelButtonText: `转换为${hintedType}后创建`,
          distinguishCancelAndClose: true,
        }
      );
      keepSelectedTypeAfterScan = true;
    } catch (action) {
      if (action === "cancel") {
        wantedType = hintedType;
        form.type = hintedType;
        ElMessage({ type: "info", message: `已切换为${hintedType}类型并继续创建` });
      } else {
        return;
      }
    }
  }
  let created = false;
  let createdDsId = "";
  try {
    const res = await store.createDataset({
      id: wantedId || undefined,
      name: wantedName,
      type: wantedType,
      size: form.size.trim() || "-",
    });
    created = true;
    createdDsId = res?.id || wantedId;
  } catch (e) {
    const code = getApiErrorCode(e);
    if (code !== "E_DATASET_ID_EXISTS") {
      ElMessage({ type: "error", message: `创建数据集失败：${e?.message || e}` });
      return;
    }
    createdDsId = wantedId;
  }
  const finalId = createdDsId;
  if (!finalId) {
    showCreate.value = false;
    return;
  }
  try {
    const beforeType = created ? wantedType : getCurrentDatasetType(finalId, wantedType);
    const scanned = await store.scanDataset(finalId);
    await store.fetchDatasets();
    selectedDatasetId.value = finalId;
    if (keepSelectedTypeAfterScan && beforeType) {
      const nowType = getCurrentDatasetType(finalId, scanned?.type || "");
      if (nowType !== beforeType) {
        await store.updateDataset(finalId, { type: beforeType });
        await store.fetchDatasets();
      }
      ElMessage({ type: "info", message: `已按你的选择保持“${beforeType}”类型` });
    } else {
      await maybeSyncTypeByIdHint(finalId, scanned, beforeType);
    }
    ElMessage({
      type: "success",
      message: created ? "数据集创建并扫描完成" : "数据集已存在，已完成重新扫描",
    });
    showCreate.value = false;
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
  }
}

async function quickAddFromDisk() {
  const id = prompt("请输入数据集ID（对应 backend/data/<id> 目录）");
  const datasetId = String(id || "").trim();
  if (!datasetId) return;

  const name = prompt("请输入数据集名称", datasetId);
  const datasetName = String(name || "").trim() || datasetId;
  let datasetType = "图像";
  let keepSelectedTypeAfterScan = false;
  const hintedType = guessTypeFromDatasetId(datasetId);
  if (hintedType && hintedType !== datasetType) {
    try {
      await ElMessageBox.confirm(
        `检测到数据集ID更像“${hintedType}”类型。是否继续按“${datasetType}”登记？`,
        "登记前确认",
        {
          type: "warning",
          confirmButtonText: `继续按${datasetType}登记`,
          cancelButtonText: `转换为${hintedType}后登记`,
          distinguishCancelAndClose: true,
        }
      );
      keepSelectedTypeAfterScan = true;
    } catch (action) {
      if (action === "cancel") {
        datasetType = hintedType;
        ElMessage({ type: "info", message: `已切换为${hintedType}类型并继续登记` });
      } else {
        return;
      }
    }
  }

  let created = false;
  try {
    await store.createDataset({ id: datasetId, name: datasetName, type: datasetType, size: "-" });
    created = true;
  } catch (e) {
    const code = getApiErrorCode(e);
    if (code !== "E_DATASET_ID_EXISTS") {
      ElMessage({ type: "error", message: `快速登记失败：${e?.message || e}` });
      return;
    }
  }
  try {
    const beforeType = created ? datasetType : getCurrentDatasetType(datasetId, datasetType);
    const scanned = await store.scanDataset(datasetId);
    await store.fetchDatasets();
    selectedDatasetId.value = datasetId;
    if (keepSelectedTypeAfterScan && beforeType) {
      const nowType = getCurrentDatasetType(datasetId, scanned?.type || "");
      if (nowType !== beforeType) {
        await store.updateDataset(datasetId, { type: beforeType });
        await store.fetchDatasets();
      }
      ElMessage({ type: "info", message: `已按你的选择保持“${beforeType}”类型` });
    } else {
      await maybeSyncTypeByIdHint(datasetId, scanned, beforeType);
    }
    ElMessage({
      type: "success",
      message: created ? "数据集创建并扫描完成" : "数据集已存在，已完成重新扫描",
    });
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
  }
}

function getApiErrorCode(e) {
  return String(
    e?.detail?.error_code ||
      e?.data?.detail?.error_code ||
      e?.data?.error_code ||
      e?.error_code ||
      ""
  );
}

async function remove(id) {
  try {
    await ElMessageBox.confirm("确认删除该数据集吗？", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await store.removeDataset(id);
  } catch (e) {
    ElMessage({ type: "error", message: `删除失败：${e?.message || e}` });
  }
}

async function handleDatasetAction(id, command) {
  if (command === "scan") {
    await scanOne(id);
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

function _ensureFileInput() {
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
        `将导入 ZIP 到数据集 ${dsId}，${overwriteOnImport.value ? "会覆盖同名文件" : "不会覆盖同名文件"}，是否继续？`,
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
      const res = await fetch(`http://127.0.0.1:8000/datasets/${encodeURIComponent(dsId)}/import_zip_file?overwrite=${overwriteOnImport.value ? "true" : "false"}`, {
        method: "POST",
        body: fd,
      });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const out = ct.includes("application/json") ? await res.json() : await res.text();
      if (!res.ok) {
        throw new Error(typeof out === "string" ? out : JSON.stringify(out));
      }
      const ds = out && typeof out === "object" ? out : null;
      if (ds?.dataset_id) {
        await store.fetchDatasets();
      }
      const meta =
        (ds?.raw?.meta && typeof ds.raw.meta === "object" ? ds.raw.meta : null) ||
        (ds?.meta && typeof ds.meta === "object" ? ds.meta : {});
      const pairs = meta?.pairs_by_task && typeof meta.pairs_by_task === "object" ? meta.pairs_by_task : {};
      const counts = meta?.counts_by_dir && typeof meta.counts_by_dir === "object" ? meta.counts_by_dir : {};
      const pairTotal = Object.values(pairs).reduce((sum, v) => sum + Number(v || 0), 0);
      const gtCount = Number(counts.gt || 0);
      if (pairTotal <= 0) {
        ElMessage({
          type: "warning",
          message: `ZIP 已导入，但可用配对为 0（gt: ${gtCount}）。请检查压缩包内是否同时包含 gt 与输入目录（hazy/noisy/blur/lr/dark）且同名。`,
        });
      } else {
        ElMessage({ type: "success", message: `ZIP 导入成功：${ds?.size || "-"}，可用配对 ${pairTotal}（gt: ${gtCount}）` });
      }
      await scanOne(dsId);
    } catch (e) {
      ElMessage({ type: "error", message: `ZIP 导入失败：${e?.message || e}` });
    }
  });
  document.body.appendChild(input);
  fileInputRef.value = input;
}

function chooseZipFor(id) {
  importTargetId.value = id;
  _ensureFileInput();
  fileInputRef.value.click();
}

function chooseZipForNew() {
  if (!selectedDatasetId.value) {
    ElMessage({ type: "warning", message: "请先选择一个数据集" });
    return;
  }
  chooseZipFor(selectedDatasetId.value);
}

// 扫描状态管理
const scanningDatasets = ref(new Set());

async function scanOne(id) {
  try {
    // 添加到扫描中集合
    scanningDatasets.value.add(id);
    ElMessage({ type: "info", message: `正在扫描数据集 ${id}...` });
    
    const beforeType = getCurrentDatasetType(id, "");
    let ds = await store.scanDataset(id);
    ds = (await maybeSyncTypeByIdHint(id, ds, beforeType)) || ds;
    const meta = ds?.raw?.meta && typeof ds.raw.meta === "object" ? ds.raw.meta : {};
    const pairs = meta?.pairs_by_task && typeof meta.pairs_by_task === "object" ? meta.pairs_by_task : {};
    const denoise = Number(pairs.video_denoise ?? 0);
    const vsr = Number(pairs.video_sr ?? 0);
    const dehaze = Number(pairs.dehaze ?? 0);
    const imgDenoise = Number(pairs.denoise ?? 0);
    const deblur = Number(pairs.deblur ?? 0);
    const sr = Number(pairs.sr ?? 0);
    const lowlight = Number(pairs.lowlight ?? 0);
    const imagePairTotal = Object.entries(pairs).reduce((sum, [k, v]) => {
      if (String(k).startsWith("video_")) return sum;
      return sum + Number(v || 0);
    }, 0);
    const dtype = String(ds?.type || "");
    const tip = `${dtype || "-"}｜${ds?.size || "-"}`;
    let extra = "";
    if (dtype === "图像") {
      extra = `图像总配对 ${imagePairTotal}（去雾 ${dehaze}，去噪 ${imgDenoise}，去模糊 ${deblur}，超分 ${sr}，低照度 ${lowlight}）`;
    } else if (dtype === "视频") {
      extra = `视频去噪 ${denoise}，视频超分 ${vsr}`;
    } else {
      extra = `图像总配对 ${imagePairTotal}（去雾 ${dehaze}，去噪 ${imgDenoise}，去模糊 ${deblur}，超分 ${sr}，低照度 ${lowlight}），视频去噪 ${denoise}，视频超分 ${vsr}`;
    }
    ElMessage({ type: "success", message: `扫描完成：${tip}（${extra}）` });
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
  } finally {
    // 从扫描中集合移除
    scanningDatasets.value.delete(id);
  }
}

function guessTypeFromDatasetId(datasetId) {
  const s = String(datasetId || "").toLowerCase();
  if (/(video|vid|视频)/.test(s)) return "视频";
  if (/(image|img|图像|图片)/.test(s)) return "图像";
  return "";
}

function getCurrentDatasetType(datasetId, fallback = "") {
  const current = store.datasets.find((d) => d.id === datasetId);
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

async function scanCurrent() {
  if (!selectedDatasetId.value) {
    ElMessage({ type: "warning", message: "请先选择一个数据集" });
    return;
  }
  await scanOne(selectedDatasetId.value);
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
  color: #6a7ca9;
  font-size: 14px;
  line-height: 1.6;
  max-width: 800px;
}

.action-bar {
  background: #f8faff;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex: 1;
  flex-wrap: wrap;
}

.guide-btn {
  margin-left: auto;
}

.selector-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding-top: 20px;
  border-top: 1px dashed #dce7ff;
}

.selector-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  flex-wrap: wrap;
}

.scan-btn {
  margin-left: auto;
}

.label {
  font-size: 14px;
  color: #1f2f57;
  font-weight: 600;
}

.select-box {
  width: 300px;
  max-width: 100%;
}

.checkbox {
  margin-right: 8px;
}

.data-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.data-table :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

:deep(.el-table__header) {
  background-color: #f5f7fa;
}

:deep(.el-table__header th) {
  font-weight: 700;
  color: #1f2f57;
}
</style>
