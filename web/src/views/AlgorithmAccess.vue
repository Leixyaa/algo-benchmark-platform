<template>
  <div class="page access-page">
    <div class="header-section">
      <h2 class="title">算法接入</h2>
      <div class="subtitle">提交算法代码包、补充依赖与入口说明，并跟踪管理员审核与平台收录状态。</div>
    </div>

    <div class="access-layout">
      <el-card shadow="never" class="submit-card">
        <template #header>
          <div class="card-title">提交算法代码包</div>
        </template>

        <el-alert
          type="info"
          :closable="false"
          class="hint-box"
          title="当前先走“代码包存档 + 管理员审核 + 平台受控收录”流程，暂不直接放开任意用户算法自动执行。"
        />

        <div class="protocol-card">
          <div class="protocol-title">提交说明</div>
          <div class="protocol-line">1. 推荐上传 `.zip` 代码包，也支持单文件代码包。</div>
          <div class="protocol-line">2. 请说明依赖环境、入口文件和启动方式，便于后续接入运行链路。</div>
          <div class="protocol-line">3. 审核通过后会生成平台留档记录，但默认仍处于“待接入运行时”状态。</div>
        </div>

        <el-form label-position="top" class="submit-form">
          <div class="inline-grid">
            <el-form-item label="适用任务">
              <el-select v-model="form.taskType" class="full-width">
                <el-option v-for="item in taskOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="版本号">
              <el-input v-model="form.version" placeholder="例如：v1 / 2026.04" />
            </el-form-item>
          </div>

          <el-form-item label="算法名称">
            <el-input v-model="form.name" placeholder="例如：MyDehazeNet / 自定义去噪算法" />
          </el-form-item>

          <el-form-item label="算法说明">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              placeholder="说明算法作用、适用场景、主要思路。"
            />
          </el-form-item>

          <el-form-item label="依赖说明">
            <el-input
              v-model="form.dependencyText"
              type="textarea"
              :rows="3"
              placeholder="例如：Python 3.10、torch 2.1、opencv-python、CUDA 12.1。"
            />
          </el-form-item>

          <el-form-item label="入口说明">
            <el-input
              v-model="form.entryText"
              type="textarea"
              :rows="3"
              placeholder="例如：主入口为 `infer.py`，命令行为 `python infer.py --input ... --output ...`。"
            />
          </el-form-item>

          <el-form-item label="代码包文件">
            <div class="file-upload-row">
              <input
                ref="archiveInput"
                type="file"
                class="hidden-file-input"
                accept=".zip,.py,.txt,.rar,.7z"
                @change="handleArchiveChange"
              />
              <el-button plain @click="triggerArchiveSelect">选择文件</el-button>
              <span class="file-name">{{ form.archiveFilename || "未选择文件" }}</span>
              <el-button v-if="form.archiveFilename" text type="danger" @click="clearArchive">清除</el-button>
            </div>
            <div class="file-tip">建议上传 zip 包，前端会按 Base64 发送到后端进行存档。</div>
          </el-form-item>

          <div class="form-actions">
            <el-button type="primary" :loading="submitting" @click="submit">提交审核</el-button>
            <el-button @click="resetForm">重置</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card shadow="never" class="record-card">
        <template #header>
          <div class="card-title">我的算法接入申请</div>
        </template>

        <el-table :data="submissions" border stripe class="data-table">
          <el-table-column prop="name" label="算法名称" min-width="170" />
          <el-table-column prop="taskLabel" label="任务" width="110" />
          <el-table-column prop="version" label="版本" width="100" />
          <el-table-column prop="archiveFilename" label="代码包" min-width="180" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="提交时间" width="170" />
          <el-table-column prop="reviewNote" label="审核说明" min-width="220" show-overflow-tooltip />
          <el-table-column label="平台留档" min-width="180">
            <template #default="{ row }">
              {{ row.platformAlgorithmId || "待审核 / 未生成" }}
            </template>
          </el-table-column>
          <el-table-column label="社区发布" min-width="180">
            <template #default="{ row }">
              <el-tag v-if="row.communityAlgorithmId" type="success">已发布</el-tag>
              <span v-else class="publish-placeholder">未发布</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" plain @click="downloadArchive(row)">下载代码包</el-button>
              <el-button
                v-if="row.status === 'approved'"
                size="small"
                type="primary"
                plain
                :disabled="Boolean(row.communityAlgorithmId)"
                @click="publishToCommunity(row)"
              >
                {{ row.communityAlgorithmId ? "已发布社区" : "发布到社区" }}
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="你还没有提交过算法代码包" />
          </template>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";
import { algorithmSubmissionsApi } from "../api/algorithmSubmissions";

const store = useAppStore();
const submitting = ref(false);
const archiveInput = ref(null);
const submissions = ref([]);

const form = reactive({
  taskType: "denoise",
  name: "",
  version: "v1",
  description: "",
  dependencyText: "",
  entryText: "",
  archiveFilename: "",
  archiveB64: "",
});

const taskOptions = computed(() =>
  Object.entries(TASK_LABEL_BY_TYPE).map(([value, label]) => ({ value, label }))
);

function formatTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(Number(unixSeconds) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function mapSubmission(x) {
  return {
    id: String(x.submission_id || ""),
    taskType: String(x.task_type || ""),
    taskLabel: String(x.task_label || TASK_LABEL_BY_TYPE[x.task_type] || x.task_type || ""),
    name: String(x.name || ""),
    version: String(x.version || ""),
    description: String(x.description || ""),
    dependencyText: String(x.dependency_text || ""),
    entryText: String(x.entry_text || ""),
    archiveFilename: String(x.archive_filename || ""),
    archiveSize: Number(x.archive_size || 0),
    archiveSha256: String(x.archive_sha256 || ""),
    status: String(x.status || "pending"),
    reviewNote: String(x.review_note || ""),
    reviewedBy: String(x.reviewed_by || ""),
    reviewedAt: x.reviewed_at ? formatTs(x.reviewed_at) : "",
    createdAt: formatTs(x.created_at),
    platformAlgorithmId: String(x.platform_algorithm_id || ""),
    communityAlgorithmId: String(x.community_algorithm_id || ""),
    communityPublishedAt: x.community_published_at ? formatTs(x.community_published_at) : "",
  };
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

function resetForm() {
  form.taskType = "denoise";
  form.name = "";
  form.version = "v1";
  form.description = "";
  form.dependencyText = "";
  form.entryText = "";
  form.archiveFilename = "";
  form.archiveB64 = "";
  if (archiveInput.value) {
    archiveInput.value.value = "";
  }
}

async function loadSubmissions() {
  if (!store.user.isLoggedIn) {
    submissions.value = [];
    return;
  }
  const list = await algorithmSubmissionsApi.listMine();
  submissions.value = (list || []).map(mapSubmission);
}

function triggerArchiveSelect() {
  archiveInput.value?.click();
}

function clearArchive() {
  form.archiveFilename = "";
  form.archiveB64 = "";
  if (archiveInput.value) {
    archiveInput.value.value = "";
  }
}

async function handleArchiveChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  try {
    const buffer = await file.arrayBuffer();
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.slice(i, i + chunkSize));
    }
    form.archiveFilename = file.name;
    form.archiveB64 = btoa(binary);
    ElMessage.success(`已读取代码包：${file.name}`);
  } catch {
    clearArchive();
    ElMessage.error("读取代码包失败");
  }
}

async function submit() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后再提交算法代码包");
    return;
  }
  if (!String(form.name || "").trim()) {
    ElMessage.warning("请先填写算法名称");
    return;
  }
  if (!String(form.archiveFilename || "").trim() || !String(form.archiveB64 || "").trim()) {
    ElMessage.warning("请先选择代码包文件");
    return;
  }
  submitting.value = true;
  try {
    await algorithmSubmissionsApi.createSubmission({
      task_type: form.taskType,
      name: form.name,
      version: form.version,
      description: form.description,
      dependency_text: form.dependencyText,
      entry_text: form.entryText,
      archive_filename: form.archiveFilename,
      archive_b64: form.archiveB64,
    });
    ElMessage.success("算法代码包已提交，等待管理员审核");
    resetForm();
    await loadSubmissions();
  } catch (e) {
    ElMessage.error(e?.message || "提交算法代码包失败");
  } finally {
    submitting.value = false;
  }
}

async function downloadArchive(row) {
  try {
    await algorithmSubmissionsApi.downloadArchive(row.id, row.archiveFilename || "algorithm_package.zip");
  } catch (e) {
    ElMessage.error(e?.message || "下载代码包失败");
  }
}

async function publishToCommunity(row) {
  try {
    const out = await algorithmSubmissionsApi.publishToCommunity(row.id, {});
    submissions.value = submissions.value.map((item) => (item.id === row.id ? mapSubmission(out) : item));
    await store.fetchAlgorithms();
    ElMessage.success("已发布到社区算法");
  } catch (e) {
    ElMessage.error(e?.message || "发布到社区失败");
  }
}

onMounted(loadSubmissions);
</script>

<style scoped>
.access-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.access-layout {
  display: grid;
  grid-template-columns: minmax(360px, 440px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.submit-card,
.record-card {
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
  color: #5d6c8c;
  line-height: 1.7;
}

.submit-form {
  display: grid;
  gap: 2px;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.full-width {
  width: 100%;
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
  color: #3b4b72;
  font-size: 13px;
}

.file-tip {
  margin-top: 8px;
  color: #7d8cac;
  font-size: 13px;
}

.publish-placeholder {
  color: #7d8cac;
}

.form-actions {
  display: flex;
  gap: 12px;
}

@media (max-width: 1080px) {
  .access-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .inline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
