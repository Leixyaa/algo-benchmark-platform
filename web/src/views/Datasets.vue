<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">数据集管理</h2>
      <div class="subtitle">
        支持创建、上传与管理数据集，推荐通过 ZIP 导入并统一纳入平台管理。
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
            <el-option
              v-for="d in ownedDatasets"
              :key="d.id"
              :label="datasetSelectLabel(d)"
              :value="d.id"
            />
          </el-select>
        </div>
        <el-button
          v-if="isDatasetAdmin"
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
            <el-table-column prop="type" label="介质" width="100">
              <template #default="{ row }">
                <el-tag :type="row.type === '视频' ? 'warning' : 'success'" size="small">{{ row.type || '-' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="适用任务" min-width="200">
              <template #default="{ row }">
                <span class="task-cell">{{ formatDatasetTaskTypes(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="规模" width="190">
              <template #default="{ row }">
                <span class="size-cell" :title="row.size || '-'">{{ row.size || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="创建时间" width="180" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleDatasetAction(row.id, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="scanningDatasets.has(row.id) || exportingDatasets.has(row.id)" :disabled="!store.user.isLoggedIn">
                    {{ exportingDatasets.has(row.id) ? "下载中" : "管理" }}<el-icon v-if="!exportingDatasets.has(row.id)" class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="isDatasetAdmin" command="id">查看/修改 ID</el-dropdown-item>
                      <el-dropdown-item command="edit-tasks">适用任务</el-dropdown-item>
                      <el-dropdown-item command="community">{{ isSelfPublishedDataset(row) ? "更新社区信息" : "上传到社区" }}</el-dropdown-item>
                      <el-dropdown-item v-if="isSelfPublishedDataset(row)" command="unpublish-community">下架社区</el-dropdown-item>
                      <el-dropdown-item command="export">下载到本地</el-dropdown-item>
                      <el-dropdown-item v-if="isDatasetAdmin" command="scan">重新扫描</el-dropdown-item>
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
            <el-table-column prop="type" label="介质" width="100">
              <template #default="{ row }">
                <el-tag :type="row.type === '视频' ? 'warning' : 'success'" size="small">{{ row.type || '-' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="适用任务" min-width="200">
              <template #default="{ row }">
                <span class="task-cell">{{ formatDatasetTaskTypes(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="规模" width="190">
              <template #default="{ row }">
                <span class="size-cell" :title="row.size || '-'">{{ row.size || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="sourceUploaderId" label="上传者" width="140" />
            <el-table-column prop="createdAt" label="下载时间" width="180" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleDatasetAction(row.id, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="scanningDatasets.has(row.id) || exportingDatasets.has(row.id)" :disabled="!store.user.isLoggedIn">
                    {{ exportingDatasets.has(row.id) ? "下载中" : "管理" }}<el-icon v-if="!exportingDatasets.has(row.id)" class="el-icon--right"><arrow-down /></el-icon>
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
        <el-form-item label="介质类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="图像" value="图像" />
            <el-option label="视频" value="视频" />
            <el-option label="图像/视频" value="图像/视频" />
          </el-select>
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="适用任务由系统在导入或扫描后按目录协议自动识别，无需在此填写。"
        />
        <el-form-item label="规模描述">
          <el-input v-model="form.size" placeholder="例如：500 张 / 30 段" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="centered-btn" @click="closeCreate">取消</el-button>
        <el-button type="primary" class="centered-btn" @click="submitCreate">确认创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showTaskTypesDialog" title="设置适用任务" width="480px" @closed="taskTypesEditId = ''">
      <p class="dialog-hint">默认由扫描自动识别；此处可手动覆盖，便于分类或与自动结果不一致时修正。</p>
      <el-select
        v-model="editTaskForm.taskTypes"
        multiple
        collapse-tags
        collapse-tags-tooltip
        placeholder="请选择"
        style="width: 100%"
      >
        <el-option v-for="(label, key) in TASK_LABEL_BY_TYPE" :key="key" :label="label" :value="key" />
      </el-select>
      <template #footer>
        <el-button @click="showTaskTypesDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTaskTypesEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
export default { name: "Datasets" };
</script>
<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, ElNotification } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { authFetch } from "../api/http";
import { datasetsApi } from "../api/datasets";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";
import { datasetHasRecognizedTasks } from "../utils/datasetTask";

const store = useAppStore();

/** 扫描 / 改 ID 等仅面向运维或开发，不对普通用户展示 */
const isDatasetAdmin = computed(() => String(store.user?.role || "") === "admin");

function datasetSelectLabel(d) {
  if (!d) return "";
  const name = String(d.name || "").trim() || "未命名数据集";
  if (isDatasetAdmin.value) return `${name} (${d.id})`;
  return name;
}

const showCreate = ref(false);
const activeDatasetTab = ref("owned");
const selectedDatasetId = ref("");
const importTargetId = ref("");
const fileInputRef = ref(null);
const scanningDatasets = ref(new Set());
const exportingDatasets = ref(new Set());

const form = reactive({
  name: "",
  type: "图像",
  size: "",
});

const showTaskTypesDialog = ref(false);
const taskTypesEditId = ref("");
const editTaskForm = reactive({ taskTypes: [] });

const visibleDatasets = computed(() =>
  (store.datasets || []).filter((d) => String(d?.raw?.owner_id || "") === String(store.user?.username || ""))
);

function isDownloadedCommunityDataset(dataset) {
  return Boolean(String(dataset?.sourceUploaderId || "").trim() || String(dataset?.sourceDatasetId || "").trim());
}

function isSelfPublishedDataset(dataset) {
  if (!dataset) return false;
  if (String(dataset?.uploaderId || "") !== String(store.user?.username || "")) return false;
  if (isDownloadedCommunityDataset(dataset)) return false;
  return String(dataset?.visibility || "").toLowerCase() === "public";
}

const ownedDatasets = computed(() => visibleDatasets.value.filter((d) => !isDownloadedCommunityDataset(d)));
const downloadedDatasets = computed(() => visibleDatasets.value.filter((d) => isDownloadedCommunityDataset(d)));
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

function isDatasetGoneError(error) {
  const text = String(error?.message || error || "");
  const code = String(
    error?.detail?.error_code ||
      error?.data?.detail?.error_code ||
      error?.data?.error_code ||
      error?.error_code ||
      ""
  );
  return text.includes("[404]") || code === "E_DATASET_NOT_FOUND";
}

onMounted(async () => {
  if (store.datasets?.length) {
    store.fetchDatasets().catch(() => {});
    return;
  }
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

function formatDatasetTaskTypes(row) {
  const raw = row?.raw?.task_types;
  const list = Array.isArray(row?.taskTypes) ? row.taskTypes : Array.isArray(raw) ? raw : [];
  if (list.length) return list.map((k) => TASK_LABEL_BY_TYPE[k] || k).join(" / ");
  const sup = row?.meta?.supported_task_types || row?.raw?.meta?.supported_task_types;
  if (Array.isArray(sup) && sup.length) return sup.map((k) => TASK_LABEL_BY_TYPE[k] || k).join(" / ");
  return "未识别（请先导入或扫描）";
}

function openCreate() {
  form.name = "";
  form.type = "图像";
  form.size = "";
  showCreate.value = true;
}

function openEditTaskTypes(id) {
  const d = getDatasetById(id);
  taskTypesEditId.value = id;
  const raw = d?.raw?.task_types;
  editTaskForm.taskTypes = Array.isArray(d?.taskTypes)
    ? [...d.taskTypes]
    : Array.isArray(raw)
      ? [...raw]
      : [];
  showTaskTypesDialog.value = true;
}

async function saveTaskTypesEdit() {
  if (!editTaskForm.taskTypes?.length) {
    ElMessage({ type: "warning", message: "请至少选择一种适用任务" });
    return;
  }
  try {
    await store.updateDataset(taskTypesEditId.value, { taskTypes: [...editTaskForm.taskTypes] });
    showTaskTypesDialog.value = false;
    ElMessage({ type: "success", message: "适用任务已更新" });
  } catch (e) {
    ElMessage({ type: "error", message: `保存失败：${e?.message || e}` });
  }
}

function closeCreate() {
  showCreate.value = false;
}

function showDatasetLayoutGuide() {
  ElMessageBox.alert(
    [
      "1) 推荐目录包含 gt 与任务输入目录，例如 hazy / noisy / blur / lr / dark。",
      "2) 视频任务依靠创建 Run 时选择 video_denoise 或 video_sr 区分。",
      "3) 视频任务要求输入目录中的视频文件与 gt 目录中的视频文件同名配对。",
      "4) 推荐统一通过 ZIP 上传数据集，由平台自动管理存储目录。",
      "5) 现在 ZIP 导入会默认替换当前数据集目录内容，请确认后再导入。",
    ].join("\n"),
    "目录与导入说明",
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
      ElMessage({ type: "error", message: "创建成功但未返回数据集编号，请刷新后重试" });
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
  if (!owned && ["id", "community", "unpublish-community", "scan", "zip"].includes(command)) {
    ElMessage({ type: "warning", message: "社区数据集不能直接修改，请先下载后在用户数据集中管理" });
    return;
  }
  if ((command === "id" || command === "scan") && !isDatasetAdmin.value) {
    return;
  }
  if (command === "id") {
    await editDatasetId(id);
    return;
  }
  if (command === "edit-tasks") {
    openEditTaskTypes(id);
    return;
  }
  if (command === "community") {
    await uploadDatasetToCommunity(id);
    return;
  }
  if (command === "unpublish-community") {
    await unpublishDatasetFromCommunity(id);
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

async function unpublishDatasetFromCommunity(id) {
  const current = ownedDatasets.value.find((item) => item.id === id);
  if (!current || !isSelfPublishedDataset(current)) {
    ElMessage({ type: "warning", message: "当前数据集未发布到社区" });
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确定将数据集“${current.name}”从社区下架吗？本地数据集记录会继续保留。`,
      "下架社区数据集",
      { type: "warning", confirmButtonText: "下架", cancelButtonText: "取消" }
    );
    await store.updateDataset(id, {
      visibility: "private",
      allowUse: false,
      allowDownload: false,
    });
    ElMessage({ type: "success", message: "数据集已从社区下架，本地记录已保留" });
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: `下架社区失败：${e?.message || e}` });
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
  let progressMessage = null;
  try {
    const nextExporting = new Set(exportingDatasets.value);
    nextExporting.add(id);
    exportingDatasets.value = nextExporting;
    progressMessage = ElMessage({
      type: "info",
      message: isDatasetAdmin.value ? `正在下载数据集 ${id}，请稍候...` : "正在下载数据集，请稍候...",
      duration: 0,
    });
    const result = await datasetsApi.exportDataset(id);
    progressMessage?.close?.();
    ElMessage({
      type: "success",
      message: result?.savedWithPicker ? "数据集已保存到你选择的位置" : "数据集下载完成，浏览器已开始保存",
    });
  } catch (e) {
    progressMessage?.close?.();
    if (isDatasetGoneError(e)) {
      await store.fetchDatasets();
      ElMessage({ type: "warning", message: "该数据集记录已失效，已从列表中同步移除" });
      return;
    }
    ElMessage({ type: "error", message: `下载到本地失败：${e?.message || e}` });
  } finally {
    progressMessage?.close?.();
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
  if (!datasetHasRecognizedTasks(current)) {
    ElMessage({
      type: "warning",
      message: "请先导入数据并执行扫描，使系统识别出适用任务；也可在「管理 → 适用任务」中手动指定后再发布。",
    });
    return;
  }
  const alreadyPublished = isSelfPublishedDataset(current);
  if (isDatasetEmpty(current)) {
    ElMessage({ type: "warning", message: "空数据集不能上传到社区，请先导入 ZIP 或补充有效文件" });
    return;
  }
  try {
    const { value } = await ElMessageBox.prompt(
      "请输入数据集在社区中心展示的描述，便于区分同名数据集",
      alreadyPublished ? "更新社区信息" : "上传到社区",
      {
        inputType: "textarea",
        inputValue: String(current.description || ""),
        inputPlaceholder: "例如：适用于图像去雾任务，包含 gt 与 hazy 配对样本。",
        confirmButtonText: alreadyPublished ? "保存" : "上传",
        cancelButtonText: "取消",
      }
    );
    await store.updateDataset(id, {
      description: String(value || "").trim(),
      visibility: "public",
      allowUse: true,
      allowDownload: true,
    });
    ElMessage({ type: "success", message: alreadyPublished ? "社区信息已更新" : "数据集已上传到社区" });
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
      `当前内部编号：${current.id}`,
      "查看/修改内部编号（测试开发）",
      {
        inputValue: current.id,
        confirmButtonText: "保存",
        cancelButtonText: "取消",
        inputPattern: /^[A-Za-z0-9._-]+$/,
        inputErrorMessage: "编号仅支持字母、数字、点、下划线和短横线",
      }
    );
    const nextId = String(value || "").trim();
    if (!nextId || nextId === current.id) {
      ElMessage({ type: "info", message: "数据集编号未修改" });
      return;
    }
    const updated = await store.changeDatasetId(current.id, nextId);
    selectedDatasetId.value = updated?.id || nextId;
    ElMessage({ type: "success", message: "数据集编号已更新" });
  } catch (action) {
    if (action !== "cancel" && action !== "close") {
      ElMessage({ type: "error", message: `修改编号失败：${action?.message || action}` });
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
        `将向数据集 ${dsId} 导入 ZIP，并自动替换当前目录内容，是否继续？`,
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
          body: fd,
        }
      );
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const out = ct.includes("application/json") ? await res.json() : await res.text();
      if (!res.ok) {
        const detail = out && typeof out === "object" ? (out.detail || out) : null;
        const message =
          detail?.message ||
          detail?.error_message ||
          detail?.error ||
          (typeof out === "string" ? out : JSON.stringify(out));
        throw new Error(String(message || "ZIP 导入失败"));
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
    dehaze: "去雾图像",
    denoise: "去噪图像",
    deblur: "去模糊图像",
    sr: "超分图像",
    lowlight: "低照度图像",
    video_denoise: "视频去噪",
    video_sr: "视频超分",
  };
  const unitOf = (key) => (String(key).startsWith("video_") ? "段" : "张");
  const items = Object.entries(pairs)
    .filter(([, count]) => Number(count || 0) > 0)
    .map(([key, count]) => `${labels[key] || key} ${count}${unitOf(key)}`);
  return items.join("；");
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
        confirmButtonText: `切换为 ${inferred || "扫描类型"}`,
        cancelButtonText: `保持 ${currentType || "当前类型"}`,
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
  --page-bg: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  --card-bg: rgba(255, 255, 255, 0.96);
  --card-border: #e2e8f0;
  --card-shadow: 0 10px 25px rgba(148, 163, 184, 0.08);
  --text-main: #1e293b;
  --text-soft: #64748b;
  --text-muted: #94a3b8;
  --accent: #3b82f6;
  --accent-deep: #2563eb;
  --accent-soft: #dbeafe;
  --success: #10b981;
  --success-deep: #059669;
  --warning: #f59e0b;
  --danger: #ef4444;
  padding: 24px;
  min-height: 100%;
  background: var(--page-bg);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.header-section {
  margin-bottom: 24px;
}

.title {
  margin: 0 0 12px;
  font-size: 28px;
  font-weight: 800;
  color: var(--text-main);
  line-height: 1.1;
}

.subtitle {
  color: var(--text-soft);
  line-height: 1.7;
  font-size: 16px;
  max-width: 800px;
}

.action-bar {
  margin-bottom: 24px;
  padding: 24px;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  box-shadow: var(--card-shadow);
  transition: all 0.3s ease;
}

.action-bar:hover {
  box-shadow: 0 15px 30px rgba(148, 163, 184, 0.12);
  transform: translateY(-2px);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
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
  gap: 16px;
  flex-wrap: wrap;
}

.label {
  color: var(--text-main);
  font-weight: 700;
  font-size: 14px;
  white-space: nowrap;
}

.select-box {
  width: 320px;
}

.section-block {
  margin-bottom: 24px;
}

.section-title {
  margin: 0 0 16px;
  color: var(--text-main);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.15;
}

.data-table {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.data-table:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.centered-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.action-btn {
  min-width: 140px;
  height: 44px;
  padding: 0 18px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.2s ease;
  font-size: 14px;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.guide-btn,
.scan-btn {
  white-space: nowrap;
}

.scan-btn {
  min-width: 160px;
}

.compact-checkbox {
  min-height: 44px;
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
  min-width: 90px;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s ease;
  height: 36px;
}

.table-action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.page :deep(.scan-result-box) {
  width: min(680px, calc(100vw - 32px));
  border-radius: 12px;
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
  color: var(--text-soft);
  word-break: break-word;
}

.page :deep(.scan-result-label) {
  min-width: 72px;
  color: var(--text-main);
  font-weight: 700;
}

.data-table :deep(.el-table__cell) {
  height: 64px;
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
}

.data-table :deep(.cell) {
  white-space: nowrap;
  font-size: 14px;
  color: var(--text-main);
}

.data-table :deep(.el-table th.el-table__cell) {
  color: var(--text-main);
  font-weight: 700;
  font-size: 14px;
  padding: 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

:deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 8px;
  box-shadow: none;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

:deep(.el-select__wrapper:hover) {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

:deep(.el-select__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

:deep(.el-button) {
  border-radius: 8px;
  transition: all 0.2s ease;
  font-weight: 600;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}

:deep(.el-dialog__header) {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  padding: 20px 24px;
}

:deep(.el-dialog__title) {
  color: var(--text-main);
  font-weight: 800;
  font-size: 18px;
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 0 24px 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item__label) {
  color: var(--text-main);
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: none;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
  min-height: 44px;
}

:deep(.el-input__wrapper:hover) {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

:deep(.el-select) {
  width: 100%;
}

:deep(.el-tabs__header) {
  margin-bottom: 0;
  padding: 0 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

:deep(.el-tabs__item) {
  font-weight: 600;
  font-size: 14px;
  padding: 16px 24px;
  color: var(--text-soft);
  transition: all 0.2s ease;
}

:deep(.el-tabs__item:hover) {
  color: var(--accent);
}

:deep(.el-tabs__item.is-active) {
  color: var(--accent);
  font-weight: 700;
}

:deep(.el-tabs__content) {
  padding: 16px;
}

:deep(.el-empty__description) {
  color: var(--text-muted);
  font-size: 14px;
}

@media (max-width: 768px) {
  .page {
    padding: 16px;
  }

  .title {
    font-size: 24px;
  }

  .subtitle {
    font-size: 14px;
  }

  .action-bar {
    padding: 20px;
  }

  .select-box {
    width: 100%;
    min-width: 220px;
  }

  .toolbar,
  .selector-row,
  .selector-left {
    flex-direction: column;
    align-items: stretch;
  }

  .action-btn {
    width: 100%;
  }

  :deep(.el-dialog) {
    width: 90% !important;
  }
}
</style>

