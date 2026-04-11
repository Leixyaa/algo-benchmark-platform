<template>
  <div class="page metrics-page">
    <div class="header-section">
      <h2 class="title">指标库</h2>
      <div class="subtitle">统一管理平台指标，提交自定义指标定义，并跟踪管理员审核与接入状态。</div>
    </div>

    <div class="metrics-layout">
      <el-card shadow="never" class="submit-card">
        <template #header>
          <div class="card-title">提交新指标</div>
        </template>

        <el-alert
          type="info"
          :closable="false"
          class="hint-box"
          title="第一版先支持“提交定义 + 管理员审核 + 接入目录”。指标代码可直接粘贴文本，也可上传代码文件。"
        />
        <div class="protocol-card">
          <div class="protocol-title">自定义指标代码协议</div>
          <div class="protocol-line">1. 仅 `Python 指标代码` 支持审核通过后接入真实 Run 执行。</div>
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

          <div class="form-actions">
            <el-button type="primary" :loading="submitting" @click="submitMetric">提交审核</el-button>
            <el-button @click="resetForm">重置</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card shadow="never" class="catalog-card">
        <template #header>
          <div class="card-title">平台已接入指标</div>
        </template>

        <el-table :data="platformMetrics" border stripe class="data-table">
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
        </el-table>
      </el-card>
    </div>

    <el-card shadow="never" class="my-card">
      <template #header>
        <div class="card-title">我的指标提交</div>
      </template>

      <el-table :data="myMetrics" border stripe class="data-table">
        <el-table-column prop="displayName" label="指标" min-width="160" />
        <el-table-column prop="metricKey" label="标识" width="180" />
        <el-table-column label="适用任务" min-width="180">
          <template #default="{ row }">
            {{ formatTaskTypes(row.taskTypes) }}
          </template>
        </el-table-column>
        <el-table-column label="审核状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="运行接入" width="120">
          <template #default="{ row }">
            <el-tag :type="row.runtimeReady ? 'success' : 'info'">{{ row.runtimeReady ? "已接入" : "未接入" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="代码文件" width="180">
          <template #default="{ row }">
            {{ row.codeFilename || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="社区发布" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.visibility === 'public'" type="success">已发布</el-tag>
            <el-tag v-else-if="row.sourceMetricId" type="info">社区副本</el-tag>
            <span v-else class="muted-text">未发布</span>
          </template>
        </el-table-column>
        <el-table-column prop="reviewNote" label="审核说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button
                size="small"
                type="primary"
                plain
                @click="publishMetric(row)"
                :disabled="!canPublishMetric(row)"
              >
                发布社区
              </el-button>
              <el-button size="small" type="danger" plain @click="removeMetric(row)" :disabled="row.uploaderId === 'system'">删除</el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="你还没有提交过指标定义" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";

const store = useAppStore();
const submitting = ref(false);
const codeInputMode = ref("text");
const codeFileInput = ref(null);
let metricsRefreshTimer = null;

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

const platformMetrics = computed(() =>
  (store.metricsCatalog || []).filter((item) => item.status === "approved" && item.runtimeReady)
);

const myMetrics = computed(() =>
  (store.metricsCatalog || []).filter((item) => item.uploaderId === String(store.user?.username || ""))
);

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
    ElMessage.success("指标定义已提交，等待管理员审核");
    resetForm();
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
  } catch (e) {
    if (e !== "cancel") {
      ElMessage.error(e?.message || "删除指标失败");
    }
  }
}

async function publishMetric(row) {
  if (!canPublishMetric(row)) {
    ElMessage.warning("只有已审核通过并接入运行链路的自有指标可以发布到社区");
    return;
  }
  try {
    await store.publishMetricToCommunity(row.id);
    await store.fetchMetrics();
    ElMessage.success("指标已发布到社区");
  } catch (e) {
    ElMessage.error(e?.message || "发布指标到社区失败");
  }
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

onMounted(async () => {
  await refreshMetricsSilently();
  document.addEventListener("visibilitychange", handleVisibilityChange);
  metricsRefreshTimer = window.setInterval(refreshMetricsSilently, 10000);
});

onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  if (metricsRefreshTimer) {
    window.clearInterval(metricsRefreshTimer);
    metricsRefreshTimer = null;
  }
});
</script>

<style scoped>
.metrics-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.metrics-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 18px;
}

.submit-card,
.catalog-card,
.my-card {
  border-radius: 16px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2f57;
}

.hint-box {
  margin-bottom: 16px;
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

.form-actions {
  display: flex;
  gap: 12px;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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

@media (max-width: 1080px) {
  .metrics-layout {
    grid-template-columns: 1fr;
  }
}
</style>
