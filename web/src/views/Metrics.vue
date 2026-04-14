<template>
  <div class="page metrics-page">
    <div class="header-section">
      <h2 class="title">指标库</h2>
      <div class="subtitle">
        上方为平台内置指标（只读）；下方「我的指标库」展示你本人提交的指标，可在此管理。自定义指标请通过「指标接入」提交；「指标提交记录」仅查看历史状态。
      </div>
    </div>

    <div class="action-bar">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button
            type="primary"
            class="centered-btn action-btn"
            :disabled="!store.user.isLoggedIn"
            @click="openMetricAccessDialog"
          >
            指标接入
          </el-button>
          <el-button
            plain
            class="centered-btn action-btn"
            :disabled="!store.user.isLoggedIn"
            @click="openMetricSubmissionHistoryDialog"
          >
            指标提交记录
          </el-button>
        </div>
      </div>
    </div>

    <div class="catalog-section">
      <div class="section-header">
        <div class="section-title">平台内置指标</div>
        <div class="section-sub">平台默认提供的 PSNR、SSIM、NIQE 等内置指标（只读）。发起评测时与「我的指标库」中已接入的自定义指标一并选用。</div>
      </div>
      <el-table :data="builtinPlatformMetrics" border stripe class="data-table">
        <el-table-column prop="displayName" label="指标" min-width="140" />
        <el-table-column label="方向" width="120">
          <template #default="{ row }">
            {{ row.direction === "lower_better" ? "越小越好" : "越大越好" }}
          </template>
        </el-table-column>
        <el-table-column label="GT" width="90">
          <template #default="{ row }">
            {{ row.requiresReference ? "需要" : "不需要" }}
          </template>
        </el-table-column>
        <el-table-column label="适用任务" min-width="220">
          <template #default="{ row }">
            {{ formatTaskTypes(row.taskTypes) }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <template #empty>
          <el-empty description="暂无平台内置指标" />
        </template>
      </el-table>
    </div>

    <div class="my-metrics-section">
      <div class="section-header">
        <div class="section-title">我的指标库</div>
        <div class="section-sub">仅包含你本人提交的指标（含审核中、已接入、社区副本等）。可在此查看详情、下载代码、发布或下架社区、删除。</div>
      </div>
      <div class="my-metrics-table-wrap">
        <el-table :data="myMetricLibrary" border stripe class="data-table my-metrics-table">
          <el-table-column prop="displayName" label="指标" min-width="160" />
          <el-table-column label="适用任务" min-width="200">
            <template #default="{ row }">
              {{ formatTaskTypes(row.taskTypes) }}
            </template>
          </el-table-column>
          <el-table-column label="审核状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="运行接入" width="100">
            <template #default="{ row }">
              <el-tag :type="row.runtimeReady ? 'success' : 'info'">{{ row.runtimeReady ? "已接入" : "未接入" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="社区发布" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.visibility === 'public'" type="success">已发布</el-tag>
              <el-tag v-else-if="row.sourceMetricId" type="info">社区副本</el-tag>
              <span v-else class="muted-text">未发布</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="360" fixed="right" align="left">
            <template #default="{ row }">
              <div class="my-metric-actions">
                <el-button size="small" plain @click="openMetricSubmissionDetail(row)">详情</el-button>
                <el-button size="small" plain @click="downloadMetricCode(row)" :disabled="!canDownloadMetricCode(row)">
                  下载代码
                </el-button>
                <el-button
                  v-if="canUnpublishMetric(row)"
                  size="small"
                  type="warning"
                  plain
                  @click="unpublishMetric(row)"
                >
                  下架社区
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  plain
                  @click="publishMetric(row)"
                  :disabled="!canPublishMetric(row)"
                >
                  发布社区
                </el-button>
                <el-button size="small" type="danger" plain @click="removeMetric(row)" :disabled="row.uploaderId === 'system'">
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="store.user.isLoggedIn ? '你还没有提交过指标定义' : '登录后可提交与管理自定义指标'" />
          </template>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="showMetricAccessDialog" title="指标接入" width="980px" top="4vh" destroy-on-close @closed="onMetricAccessDialogClosed">
      <div class="metric-access-dialog">
        <el-alert
          type="info"
          :closable="false"
          class="hint-box"
          title="提交指标定义后由管理员审核，审核通过后即可接入目录并用于评测。指标代码可直接粘贴文本，也可上传代码文件。"
        />
        <div class="protocol-card">
          <div class="protocol-title">自定义指标代码协议</div>
          <div class="protocol-line">1. 仅「Python 指标代码」支持审核通过后接入真实 Run 执行。</div>
          <div class="protocol-line">2. 请定义 `compute_metric(...)` 函数，并返回单个数值结果。</div>
          <div class="protocol-line">3. 推荐签名：`def compute_metric(gt_bgr_u8, pred_bgr_u8, sample_name="", task_type=""):`</div>
          <div class="protocol-line">4. 需要 GT 的指标请使用 `gt_bgr_u8` 与 `pred_bgr_u8`；无 GT 指标可只使用 `pred_bgr_u8`。</div>
          <div class="protocol-line">5. 运行环境会注入 `np`、`cv2`、`math` 等对象，返回值必须是有限数值。</div>
        </div>

        <el-form label-position="top" class="metric-form">
          <el-form-item label="指标标识">
            <el-input v-model="form.metricKey" placeholder="例如：MY_METRIC_A，留空会自动生成" />
          </el-form-item>

          <el-form-item label="显示名称">
            <el-input v-model="form.name" placeholder="例如：边缘保持分数" />
          </el-form-item>

          <el-form-item label="适用任务">
            <el-select v-model="form.taskTypes" multiple placeholder="选择适用任务" class="full-width">
              <el-option v-for="item in taskOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>

          <div class="inline-grid">
            <el-form-item label="指标方向">
              <el-select v-model="form.direction" class="full-width">
                <el-option label="越大越好" value="higher_better" />
                <el-option label="越小越好" value="lower_better" />
              </el-select>
            </el-form-item>
            <el-form-item label="是否需要 GT">
              <el-switch v-model="form.requiresReference" inline-prompt active-text="需要" inactive-text="不需要" />
            </el-form-item>
          </div>

          <el-form-item label="实现方式">
            <el-select v-model="form.implementationType" class="full-width">
              <el-option label="Python 指标代码" value="python" />
              <el-option label="公式 / 说明型指标" value="formula" />
            </el-select>
          </el-form-item>

          <el-form-item label="指标描述">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              placeholder="说明指标含义、输入输出、适用场景。"
            />
          </el-form-item>

          <el-form-item v-if="form.implementationType === 'formula'" label="公式或说明">
            <el-input
              v-model="form.formulaText"
              type="textarea"
              :rows="4"
              placeholder="填写公式、伪代码或计算口径说明。"
            />
          </el-form-item>

          <template v-else>
            <el-form-item label="代码提交方式">
              <el-radio-group v-model="codeInputMode">
                <el-radio-button label="text">直接粘贴文本</el-radio-button>
                <el-radio-button label="file">上传代码文件</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="codeInputMode === 'file'" label="代码文件">
              <div class="file-upload-row">
                <input
                  ref="codeFileInput"
                  type="file"
                  class="hidden-file-input"
                  accept=".py,.txt,.md,.json"
                  @change="handleCodeFileChange"
                />
                <el-button plain @click="triggerCodeFileSelect">选择文件</el-button>
                <span class="file-name">{{ form.codeFilename || "未选择文件" }}</span>
                <el-button v-if="form.codeFilename" text type="danger" @click="clearCodeFile">清除</el-button>
              </div>
            </el-form-item>

            <el-form-item label="代码内容">
              <el-input
                v-model="form.codeText"
                type="textarea"
                :rows="8"
                :placeholder="codeInputMode === 'file' ? '选择文件后会自动读取内容。' : '粘贴指标代码片段或函数签名说明。第一版仅存档与审核，不直接执行。'"
              />
            </el-form-item>
          </template>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeMetricAccessDialog">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMetric">提交审核</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMetricSubmissionHistoryDialog" title="指标提交记录" width="1100px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="history-hint"
        title="该页面仅用于历史查看：支持查看当次指标说明、下载当次代码。可使用“清空历史记录”一次性清理。"
      />
      <el-table
        :data="metricHistoryRows"
        border
        stripe
        class="data-table submission-table history-readonly-table"
        :row-key="(row) => row.historyId || row.id"
        @selection-change="onMetricHistorySelectionChange"
      >
        <el-table-column type="selection" width="52" />
        <el-table-column prop="displayName" label="指标" min-width="180" />
        <el-table-column label="适用任务" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="history-task-text">{{ formatTaskTypes(row.taskTypes) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="提交时间" width="170" />
        <el-table-column label="操作" width="340">
          <template #default="{ row }">
            <div class="history-actions">
              <el-button size="small" plain @click="openMetricSubmissionDetail(row)">指标说明</el-button>
              <el-button size="small" plain @click="downloadMetricCode(row)" :disabled="!canDownloadMetricCode(row)">
                下载代码
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                class="history-delete-btn"
                @click="deleteSingleMetricHistory(row)"
                :disabled="!String(row.historyId || '').trim()"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无提交记录" />
        </template>
      </el-table>
      <template #footer>
        <el-button
          type="danger"
          plain
          :disabled="!selectedMetricHistoryIds.length"
          @click="deleteSelectedMetricHistory"
        >
          删除选中
        </el-button>
        <el-button
          type="danger"
          plain
          :loading="clearingMetricHistory"
          :disabled="!metricHistoryRows.length"
          @click="clearMetricSubmissionHistory"
        >
          清空历史记录
        </el-button>
        <el-button @click="showMetricSubmissionHistoryDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMetricDetailDialog" title="指标提交详情" width="760px">
      <el-descriptions v-if="selectedMetricSubmission" border :column="2" class="metric-detail-desc">
        <el-descriptions-item label="指标名称">{{ selectedMetricSubmission.displayName || "—" }}</el-descriptions-item>
        <el-descriptions-item label="指标标识">{{ selectedMetricSubmission.metricKey || "—" }}</el-descriptions-item>
        <el-descriptions-item label="适用任务" :span="2">
          {{ formatTaskTypes(selectedMetricSubmission.taskTypes) }}
        </el-descriptions-item>
        <el-descriptions-item label="指标方向">
          {{ selectedMetricSubmission.direction === "lower_better" ? "越小越好" : "越大越好" }}
        </el-descriptions-item>
        <el-descriptions-item label="是否需要 GT">
          {{ selectedMetricSubmission.requiresReference ? "需要" : "不需要" }}
        </el-descriptions-item>
        <el-descriptions-item label="实现方式">{{ implementationTypeLabel(selectedMetricSubmission.implementationType) }}</el-descriptions-item>
        <el-descriptions-item label="审核说明" :span="2">
          {{ selectedMetricSubmission.reviewNote || "暂无" }}
        </el-descriptions-item>
        <el-descriptions-item label="代码文件" :span="2">
          {{ selectedMetricSubmission.codeFilename || "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="指标描述" :span="2">
          {{ selectedMetricSubmission.description || "—" }}
        </el-descriptions-item>
        <el-descriptions-item v-if="selectedMetricSubmission.implementationType === 'formula'" label="公式或说明" :span="2">
          {{ selectedMetricSubmission.formulaText || "—" }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showMetricDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
export default { name: "Metrics" };
</script>
<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { metricsApi } from "../api/metrics";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";

const store = useAppStore();
const submitting = ref(false);
const clearingMetricHistory = ref(false);
const metricHistoryRows = ref([]);
const selectedMetricHistoryIds = ref([]);
const codeInputMode = ref("text");
const codeFileInput = ref(null);
let metricsRefreshTimer = null;

const showMetricAccessDialog = ref(false);
const showMetricSubmissionHistoryDialog = ref(false);
const showMetricDetailDialog = ref(false);
const selectedMetricSubmission = ref(null);

const form = reactive({
  metricKey: "",
  name: "",
  taskTypes: ["denoise"],
  direction: "higher_better",
  requiresReference: true,
  implementationType: "python",
  description: "",
  formulaText: "",
  codeText: "",
  codeFilename: "",
});

const taskOptions = computed(() =>
  Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label }))
);

/** 与发起评测页一致：平台内置三指标 */
const BUILTIN_METRIC_KEYS = ["PSNR", "SSIM", "NIQE"];

const builtinPlatformMetrics = computed(() => {
  const order = BUILTIN_METRIC_KEYS.map((k) => k.toUpperCase());
  const keySet = new Set(order);
  const rows = (store.metricsCatalog || []).filter((item) => {
    const key = String(item.metricKey || "").toUpperCase();
    return (
      item.status === "approved" &&
      item.runtimeReady &&
      String(item.uploaderId || "") === "system" &&
      keySet.has(key)
    );
  });
  return [...rows].sort(
    (a, b) =>
      order.indexOf(String(a.metricKey || "").toUpperCase()) -
      order.indexOf(String(b.metricKey || "").toUpperCase())
  );
});

/** 当前用户自有指标（与上方内置表互斥，避免重复展示） */
const myMetricLibrary = computed(() =>
  (store.metricsCatalog || []).filter((item) => item.uploaderId === String(store.user?.username || ""))
);

function formatMetricHistoryTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(Number(unixSeconds) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function mapMetricHistoryRow(row) {
  const src = row && typeof row === "object" ? row : {};
  const createdAtTs = Number(src.created_at || 0);
  return {
    id: String(src.metric_id || "").trim(),
    historyId: String(src.history_id || "").trim(),
    metricKey: String(src.metric_key || "").trim(),
    displayName: String(src.display_name || src.name || "").trim(),
    taskTypes: Array.isArray(src.task_types) ? [...src.task_types] : [],
    createdAt: formatMetricHistoryTs(createdAtTs),
    createdAtTs,
    direction: String(src.direction || ""),
    requiresReference: Boolean(src.requires_reference),
    implementationType: String(src.implementation_type || "python"),
    description: String(src.description || ""),
    formulaText: String(src.formula_text || ""),
    codeText: String(src.code_text || ""),
    codeFilename: String(src.code_filename || "").trim(),
    reviewNote: "",
    status: "history",
    runtimeReady: true,
  };
}

async function loadMetricHistoryRows() {
  if (!store.user.isLoggedIn) {
    metricHistoryRows.value = [];
    selectedMetricHistoryIds.value = [];
    return;
  }
  try {
    const list = await metricsApi.listSubmissionHistory();
    metricHistoryRows.value = Array.isArray(list)
      ? list.map(mapMetricHistoryRow).sort((a, b) => Number(b?.createdAtTs || 0) - Number(a?.createdAtTs || 0))
      : [];
    selectedMetricHistoryIds.value = [];
  } catch (e) {
    metricHistoryRows.value = [];
    selectedMetricHistoryIds.value = [];
    ElMessage.error(e?.message || "加载指标历史记录失败");
  }
}

function openMetricAccessDialog() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后再提交指标");
    return;
  }
  showMetricAccessDialog.value = true;
}

async function openMetricSubmissionHistoryDialog() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后查看提交记录");
    return;
  }
  try {
    await store.fetchMetrics();
  } catch {
    // ignore
  }
  await loadMetricHistoryRows();
  showMetricSubmissionHistoryDialog.value = true;
}

function onMetricHistorySelectionChange(rows) {
  selectedMetricHistoryIds.value = Array.isArray(rows)
    ? rows.map((item) => String(item?.historyId || "").trim()).filter(Boolean)
    : [];
}

function closeMetricAccessDialog() {
  showMetricAccessDialog.value = false;
}

function onMetricAccessDialogClosed() {
  if (codeFileInput.value) {
    codeFileInput.value.value = "";
  }
}

function openMetricSubmissionDetail(row) {
  selectedMetricSubmission.value = row;
  showMetricDetailDialog.value = true;
}

function implementationTypeLabel(t) {
  if (t === "formula") return "公式 / 说明型指标";
  return "Python 指标代码";
}

function resetForm() {
  form.metricKey = "";
  form.name = "";
  form.taskTypes = ["denoise"];
  form.direction = "higher_better";
  form.requiresReference = true;
  form.implementationType = "python";
  form.description = "";
  form.formulaText = "";
  form.codeText = "";
  form.codeFilename = "";
  codeInputMode.value = "text";
  if (codeFileInput.value) {
    codeFileInput.value.value = "";
  }
}

function formatTaskTypes(list) {
  if (!Array.isArray(list) || !list.length) return "未限定";
  return list.map((item) => TASK_LABEL_BY_TYPE[item] || item).join(" / ");
}

function statusLabel(status) {
  if (status === "approved") return "已通过";
  if (status === "rejected") return "已驳回";
  return "待审核";
}

function statusTagType(status) {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  return "warning";
}

function canPublishMetric(row) {
  if (!row || row.uploaderId === "system") return false;
  if (row.sourceMetricId) return false;
  if (row.visibility === "public") return false;
  if (row.status !== "approved") return false;
  if (row.implementationType === "python" && !row.runtimeReady) return false;
  return true;
}

function canUnpublishMetric(row) {
  if (!row || row.uploaderId === "system") return false;
  if (row.sourceMetricId) return false;
  if (String(row.uploaderId || "") !== String(store.user?.username || "")) return false;
  return String(row.visibility || "").toLowerCase() === "public";
}

function canDownloadMetricCode(row) {
  return Boolean(String(row?.codeText || "").trim());
}

function downloadMetricCode(row) {
  const codeText = String(row?.codeText || "");
  const fileName = String(row?.codeFilename || row?.metricKey || "metric_code.py").trim() || "metric_code.py";
  if (!codeText) {
    ElMessage.warning("当前没有可下载的代码内容");
    return;
  }
  const blob = new Blob([codeText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function triggerCodeFileSelect() {
  codeFileInput.value?.click();
}

function clearCodeFile() {
  form.codeFilename = "";
  form.codeText = "";
  if (codeFileInput.value) {
    codeFileInput.value.value = "";
  }
}

async function handleCodeFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  try {
    form.codeText = await file.text();
    form.codeFilename = file.name;
    ElMessage.success(`已读取文件：${file.name}`);
  } catch {
    ElMessage.error("读取代码文件失败");
    clearCodeFile();
  }
}

async function submitMetric() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后再提交指标");
    return;
  }
  if (!String(form.name || "").trim()) {
    ElMessage.warning("请先填写指标名称");
    return;
  }
  if (!Array.isArray(form.taskTypes) || !form.taskTypes.length) {
    ElMessage.warning("请至少选择一个适用任务");
    return;
  }
  if (form.implementationType === "formula" && !String(form.formulaText || "").trim()) {
    ElMessage.warning("请填写公式或说明");
    return;
  }
  if (form.implementationType === "python" && !String(form.codeText || "").trim()) {
    ElMessage.warning(codeInputMode.value === "file" ? "请先选择代码文件" : "请填写代码内容或函数说明");
    return;
  }
  submitting.value = true;
  try {
    await store.createMetric({
      metricKey: form.metricKey,
      name: form.name,
      displayName: form.name,
      taskTypes: [...form.taskTypes],
      direction: form.direction,
      requiresReference: form.requiresReference,
      implementationType: form.implementationType,
      description: form.description,
      formulaText: form.formulaText,
      codeText: form.codeText,
      codeFilename: form.codeFilename,
    });
    await store.fetchMetrics();
    await loadMetricHistoryRows();
    ElMessage.success("指标定义已提交，等待管理员审核");
    resetForm();
    showMetricAccessDialog.value = false;
  } catch (e) {
    ElMessage.error(e?.message || "提交指标失败");
  } finally {
    submitting.value = false;
  }
}

async function removeMetric(row) {
  try {
    await ElMessageBox.confirm(`确定删除指标“${row.displayName}”吗？`, "删除指标", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    await store.removeMetric(row.id);
    ElMessage.success("指标已删除");
    if (selectedMetricSubmission.value?.id === row.id) {
      showMetricDetailDialog.value = false;
      selectedMetricSubmission.value = null;
    }
  } catch (e) {
    if (e !== "cancel") {
      ElMessage.error(e?.message || "删除指标失败");
    }
  }
}

async function clearMetricSubmissionHistory() {
  if (!metricHistoryRows.value.length) {
    ElMessage.info("暂无可清理的历史记录");
    return;
  }
  try {
    await ElMessageBox.confirm(
      "确定清空指标接入历史记录吗？",
      "清空历史记录",
      { type: "warning", confirmButtonText: "清空", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  clearingMetricHistory.value = true;
  try {
    const out = await metricsApi.clearSubmissionHistory();
    const removed = Number(out?.removed || 0);
    metricHistoryRows.value = [];
    selectedMetricHistoryIds.value = [];
    if (showMetricDetailDialog.value) {
      showMetricDetailDialog.value = false;
      selectedMetricSubmission.value = null;
    }
    ElMessage.success(`历史记录已清理 ${removed} 条`);
  } catch (e) {
    ElMessage.error(e?.message || "清空历史记录失败");
  } finally {
    clearingMetricHistory.value = false;
  }
}

async function deleteSingleMetricHistory(row) {
  const historyId = String(row?.historyId || "").trim();
  if (!historyId) return;
  try {
    await ElMessageBox.confirm("确定删除这条指标历史记录吗？", "删除历史记录", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    const out = await metricsApi.deleteSubmissionHistoryItem(historyId);
    metricHistoryRows.value = metricHistoryRows.value.filter((item) => String(item?.historyId || "") !== historyId);
    selectedMetricHistoryIds.value = selectedMetricHistoryIds.value.filter((id) => id !== historyId);
    if (selectedMetricSubmission.value && String(selectedMetricSubmission.value.historyId || "") === historyId) {
      showMetricDetailDialog.value = false;
      selectedMetricSubmission.value = null;
    }
    ElMessage.success(`已删除 ${Number(out?.removed || 1)} 条历史记录`);
  } catch (e) {
    ElMessage.error(e?.message || "删除历史记录失败");
  }
}

async function deleteSelectedMetricHistory() {
  if (!selectedMetricHistoryIds.value.length) {
    ElMessage.info("请先勾选要删除的历史记录");
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedMetricHistoryIds.value.length} 条指标历史记录吗？`,
      "批量删除历史记录",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  try {
    const ids = [...selectedMetricHistoryIds.value];
    const out = await metricsApi.deleteSubmissionHistoryBatch(ids);
    const idSet = new Set(ids);
    metricHistoryRows.value = metricHistoryRows.value.filter((item) => !idSet.has(String(item?.historyId || "")));
    selectedMetricHistoryIds.value = [];
    if (selectedMetricSubmission.value && idSet.has(String(selectedMetricSubmission.value.historyId || ""))) {
      showMetricDetailDialog.value = false;
      selectedMetricSubmission.value = null;
    }
    ElMessage.success(`已删除 ${Number(out?.removed || 0)} 条历史记录`);
  } catch (e) {
    ElMessage.error(e?.message || "批量删除历史记录失败");
  }
}

async function publishMetric(row) {
  if (!canPublishMetric(row)) {
    ElMessage.warning("只有已审核通过并接入运行链路的自有指标可以发布到社区");
    return;
  }
  try {
    const alreadyPublished = String(row?.visibility || "").toLowerCase() === "public";
    const { value } = await ElMessageBox.prompt(
      "请输入指标在社区中心展示的说明，便于区分同名指标。",
      alreadyPublished ? "更新社区说明" : "发布到社区",
      {
        inputType: "textarea",
        inputValue: String(row.description || ""),
        inputPlaceholder: "例如：更关注纹理保真度，适合去噪任务单图排序。",
        confirmButtonText: alreadyPublished ? "保存" : "发布",
        cancelButtonText: "取消",
      }
    );
    await store.publishMetricToCommunity(row.id, {
      community_description: String(value || "").trim(),
    });
    await store.fetchMetrics();
    ElMessage.success(alreadyPublished ? "社区说明已更新" : "指标已发布到社区");
    syncSelectedMetricAfterMutation(row.id);
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage.error(e?.message || "发布指标到社区失败");
  }
}

async function unpublishMetric(row) {
  if (!canUnpublishMetric(row)) {
    ElMessage.warning("只有已发布到社区的自有指标可以下架");
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确定将指标“${row.displayName}”从社区下架吗？本地指标记录会继续保留。`,
      "下架社区指标",
      { type: "warning", confirmButtonText: "下架", cancelButtonText: "取消" }
    );
    await store.unpublishMetricFromCommunity(row.id);
    await store.fetchMetrics();
    ElMessage.success("指标已从社区下架，本地记录已保留");
    syncSelectedMetricAfterMutation(row.id);
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error(e?.message || "下架社区指标失败");
    }
  }
}

function syncSelectedMetricAfterMutation(metricId) {
  if (!metricId || !selectedMetricSubmission.value) return;
  if (selectedMetricSubmission.value.id !== metricId) return;
  const next = (store.metricsCatalog || []).find((m) => m.id === metricId);
  if (next) selectedMetricSubmission.value = next;
}

async function refreshMetricsSilently() {
  try {
    await store.fetchMetrics();
  } catch {
    // ignore
  }
}

function handleVisibilityChange() {
  if (document.visibilityState === "visible") {
    refreshMetricsSilently();
  }
}

watch(
  () => store.metricsCatalog,
  () => {
    syncSelectedMetricAfterMutation(selectedMetricSubmission.value?.id);
  },
  { deep: true }
);

function startMetricsBackgroundSync() {
  if (metricsRefreshTimer) return;
  document.addEventListener("visibilitychange", handleVisibilityChange);
  metricsRefreshTimer = window.setInterval(refreshMetricsSilently, 10000);
}

function stopMetricsBackgroundSync() {
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  if (metricsRefreshTimer) {
    window.clearInterval(metricsRefreshTimer);
    metricsRefreshTimer = null;
  }
}

onMounted(async () => {
  if (store.metricsCatalog?.length) {
    refreshMetricsSilently();
  } else {
    await refreshMetricsSilently();
  }
});

onActivated(() => {
  startMetricsBackgroundSync();
  refreshMetricsSilently();
});

onDeactivated(() => {
  stopMetricsBackgroundSync();
});

onBeforeUnmount(() => {
  stopMetricsBackgroundSync();
});
</script>

<style scoped>
.metrics-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.header-section {
  margin-bottom: 8px;
}

.title {
  margin: 0 0 16px;
  font-size: 28px;
  font-weight: 700;
  color: #1f2f57;
  line-height: 1.2;
}

.subtitle {
  color: #6a7ca9;
  font-size: 14px;
  line-height: 1.6;
  max-width: 800px;
  margin: 0;
}

.centered-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  text-align: center;
  white-space: nowrap;
}

.centered-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.centered-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.action-btn {
  width: 156px;
  height: 44px;
  padding: 0 14px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
}

.action-bar {
  background: #f8faff;
  padding: 28px;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  margin-bottom: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  gap: 16px;
  flex: 1;
  flex-wrap: wrap;
}

.catalog-section,
.my-metrics-section {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.my-metrics-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.my-metric-actions {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  justify-content: flex-start;
}

.my-metric-actions :deep(.el-button) {
  margin: 0;
  width: 88px;
  height: 32px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.history-hint {
  margin-bottom: 14px;
}

.history-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.history-actions :deep(.el-button) {
  min-width: 92px;
  height: 32px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.history-delete-btn {
  min-width: 66px !important;
  padding: 0 6px !important;
}

.history-task-text {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  vertical-align: middle;
}

.section-header {
  margin-bottom: 18px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2f57;
}

.section-sub {
  margin-top: 6px;
  font-size: 13px;
  color: #6a7ca9;
  line-height: 1.5;
}

.hint-box {
  margin-bottom: 16px;
}

.metric-access-dialog {
  max-height: 72vh;
  overflow-y: auto;
  padding-right: 4px;
}

.protocol-card {
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid #dbe7ff;
  border-radius: 14px;
  background: #f7faff;
}

.protocol-title {
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #1f2f57;
}

.protocol-line {
  margin-bottom: 6px;
  color: #4f6185;
  line-height: 1.7;
}

.protocol-line:last-child {
  margin-bottom: 0;
}

.inline-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.full-width {
  width: 100%;
}

.muted-text {
  color: #7b89a8;
}

.file-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.hidden-file-input {
  display: none;
}

.file-name {
  color: #5b6b8b;
}

.metric-detail-desc {
  margin-top: 4px;
}

@media (max-width: 1080px) {
  .inline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
