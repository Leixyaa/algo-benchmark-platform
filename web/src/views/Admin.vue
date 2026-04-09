<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">管理后台</h2>
      <div class="subtitle">管理员可以在这里下架社区资源、处理举报，并在资源详情中删除违规评论。</div>
    </div>

    <el-alert
      v-if="store.user.role !== 'admin'"
      type="warning"
      :closable="false"
      title="当前账号不是管理员，无法使用后台治理能力。"
      class="warn-box"
    />

    <el-tabs v-model="tab" class="resource-tabs">
      <el-tab-pane label="社区算法" name="algorithms">
        <div class="toolbar">
          <el-input v-model="algorithmKeyword" placeholder="搜索算法名称 / 上传者ID" clearable class="search-input" />
        </div>
        <el-table :data="filteredAlgorithms" border stripe class="data-table">
          <el-table-column prop="name" label="算法名称" min-width="220" />
          <el-table-column prop="task" label="任务" width="120" />
          <el-table-column prop="uploaderId" label="上传者ID" width="140" />
          <el-table-column prop="downloadCount" label="下载量" width="100" />
          <el-table-column prop="createdAt" label="发布时间" width="180" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" plain @click="openResourceDetail('algorithm', row)">详情</el-button>
              <el-button
                size="small"
                type="danger"
                @click="takedownAlgorithm(row)"
                :loading="loadingAlgorithmIds.has(row.id)"
              >
                下架
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="社区数据集" name="datasets">
        <div class="toolbar">
          <el-input v-model="datasetKeyword" placeholder="搜索数据集名称 / 上传者ID" clearable class="search-input" />
        </div>
        <el-table :data="filteredDatasets" border stripe class="data-table">
          <el-table-column prop="name" label="数据集名称" min-width="220" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="size" label="规模" width="140" />
          <el-table-column prop="uploaderId" label="上传者ID" width="140" />
          <el-table-column prop="downloadCount" label="下载量" width="100" />
          <el-table-column prop="createdAt" label="发布时间" width="180" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" plain @click="openResourceDetail('dataset', row)">详情</el-button>
              <el-button
                size="small"
                type="danger"
                @click="takedownDataset(row)"
                :loading="loadingDatasetIds.has(row.id)"
              >
                下架
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="举报处理" name="reports">
        <div class="toolbar">
          <el-input v-model="pendingReportKeyword" placeholder="搜索待处理举报对象 / 举报人 / 原因" clearable class="search-input" />
        </div>
        <el-table :data="pendingReports" border stripe class="data-table">
          <el-table-column prop="targetTypeLabel" label="举报类型" width="120" />
          <el-table-column prop="targetId" label="举报对象ID" min-width="180" />
          <el-table-column prop="reporterId" label="举报人ID" width="140" />
          <el-table-column prop="reason" label="举报原因" min-width="260" show-overflow-tooltip />
          <el-table-column prop="createdAt" label="举报时间" width="180" />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                @click="openReportProcess(row)"
                :loading="resolvingReportIds.has(row.reportId)"
              >
                处理
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="处理日志" name="report-logs">
        <div class="toolbar">
          <el-input v-model="reportLogKeyword" placeholder="搜索处理记录 / 处理人 / 理由" clearable class="search-input" />
          <el-button
            plain
            class="clear-btn"
            @click="clearHandledReports"
            :disabled="!handledReportsCount"
            :loading="clearingReports"
          >
            清除记录
          </el-button>
        </div>
        <el-table :data="handledReports" border stripe class="data-table">
          <el-table-column prop="targetTypeLabel" label="举报类型" width="120" />
          <el-table-column prop="targetId" label="举报对象ID" min-width="180" />
          <el-table-column prop="reporterId" label="举报人ID" width="140" />
          <el-table-column prop="reason" label="举报原因" min-width="220" show-overflow-tooltip />
          <el-table-column prop="statusLabel" label="状态" width="100" />
          <el-table-column prop="resolution" label="处理理由" min-width="260" show-overflow-tooltip />
          <el-table-column prop="resolvedBy" label="处理人" width="120" />
          <el-table-column prop="resolvedAt" label="处理时间" width="180" />
          <el-table-column prop="createdAt" label="举报时间" width="180" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" :title="detailTitle" width="820px">
      <div v-if="detailItem" class="detail-panel">
        <div class="detail-summary">
          <div class="detail-name">{{ detailItem.name }}</div>
          <div class="detail-meta">
            <span>上传者ID：{{ detailItem.uploaderId || "-" }}</span>
            <span>下载量：{{ detailItem.downloadCount ?? 0 }}</span>
            <span>发布时间：{{ detailItem.createdAt || "-" }}</span>
          </div>
          <div class="detail-meta">
            <span v-if="detailType === 'algorithm'">任务：{{ detailItem.task || "-" }}</span>
            <span v-if="detailType === 'dataset'">类型：{{ detailItem.type || "-" }}</span>
            <span v-if="detailType === 'dataset'">规模：{{ detailItem.size || "-" }}</span>
          </div>
        </div>

        <div class="detail-block">
          <div class="block-title">详细描述</div>
          <div class="description-box">{{ detailItem.description || "暂无描述" }}</div>
        </div>

        <div class="detail-block">
          <div class="block-title">评论列表</div>
          <div v-if="!detailComments.length" class="empty-text">当前资源暂无评论。</div>
          <div v-for="comment in detailComments" :key="comment.commentId" class="comment-item">
            <div class="comment-head">
              <div class="comment-head-left">
                <span class="comment-author">{{ comment.authorId }}</span>
                <span class="comment-time">{{ comment.createdAt }}</span>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                @click="deleteComment(comment)"
                :loading="deletingCommentIds.has(comment.commentId)"
              >
                删除评论
              </el-button>
            </div>
            <div class="comment-content">{{ comment.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="reportProcessVisible" title="处理举报" width="640px">
      <div v-if="activeReport" class="process-panel">
        <div class="process-meta">
          <div>举报类型：{{ activeReport.targetTypeLabel }}</div>
          <div>举报对象ID：{{ activeReport.targetId }}</div>
          <div>举报人ID：{{ activeReport.reporterId }}</div>
        </div>

        <div v-if="reportTargetDetail" class="process-detail-card">
          <div class="process-detail-head">
            <div class="process-detail-title">资源详情</div>
            <template v-if="activeReport.targetType === 'dataset' && reportTargetDetail.storagePath">
              <el-button size="small" plain @click="copyDatasetPath(reportTargetDetail.storagePath)">复制路径</el-button>
              <el-button size="small" type="primary" plain @click="openDatasetFolder(reportTargetDetail.storagePath)">
                打开文件夹
              </el-button>
            </template>
          </div>

          <div class="process-detail-grid">
            <div>名称：{{ reportTargetDetail.name || "-" }}</div>
            <div>上传者ID：{{ reportTargetDetail.uploaderId || "-" }}</div>
            <div v-if="activeReport.targetType !== 'comment'">下载量：{{ reportTargetDetail.downloadCount ?? 0 }}</div>
            <div v-if="reportTargetDetail.createdAt">发布时间：{{ reportTargetDetail.createdAt }}</div>
            <div v-if="reportTargetDetail.task">任务：{{ reportTargetDetail.task }}</div>
            <div v-if="reportTargetDetail.type">类型：{{ reportTargetDetail.type }}</div>
            <div v-if="reportTargetDetail.size">规模：{{ reportTargetDetail.size }}</div>
          </div>

          <div class="process-detail-desc">{{ reportTargetDetail.description || "暂无描述" }}</div>
          <div
            v-if="activeReport.targetType === 'dataset' && reportTargetDetail.storagePath"
            class="process-path"
          >
            平台路径：{{ reportTargetDetail.storagePath }}
          </div>
          <div v-if="activeReport.targetType === 'comment' && reportTargetComment" class="process-comment-box">
            被举报评论：{{ reportTargetComment.content || "-" }}
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item label="处理动作">
            <el-select v-model="reportProcessAction" class="full-width">
              <el-option label="驳回举报" value="reject" />
              <el-option label="仅标记已处理" value="resolve" />
              <el-option v-if="activeReport.targetType === 'algorithm'" label="下架该算法" value="takedown_algorithm" />
              <el-option v-if="activeReport.targetType === 'dataset'" label="下架该数据集" value="takedown_dataset" />
              <el-option v-if="activeReport.targetType === 'comment'" label="删除该评论" value="delete_comment" />
            </el-select>
          </el-form-item>
          <el-form-item label="处理说明">
            <el-input
              v-model="reportProcessNote"
              type="textarea"
              :rows="4"
              placeholder="填写处理结果，便于后续留痕和通知举报人。"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeReportProcess">取消</el-button>
        <el-button type="primary" @click="submitReportProcess" :loading="reportProcessSubmitting">确认处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "../api/admin";
import { useAppStore } from "../stores/app";

const store = useAppStore();

const tab = ref("algorithms");
const algorithms = ref([]);
const datasets = ref([]);
const comments = ref([]);
const reports = ref([]);

const algorithmKeyword = ref("");
const datasetKeyword = ref("");
const pendingReportKeyword = ref("");
const reportLogKeyword = ref("");

const loadingAlgorithmIds = ref(new Set());
const loadingDatasetIds = ref(new Set());
const deletingCommentIds = ref(new Set());
const resolvingReportIds = ref(new Set());
const clearingReports = ref(false);

const detailVisible = ref(false);
const detailType = ref("algorithm");
const detailItem = ref(null);

const reportProcessVisible = ref(false);
const activeReport = ref(null);
const reportProcessAction = ref("resolve");
const reportProcessNote = ref("");
const reportProcessSubmitting = ref(false);
const reportTargetDetail = ref(null);
const reportTargetComment = ref(null);

function formatTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(Number(unixSeconds) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function setLoading(setRef, id, loading) {
  const next = new Set(setRef.value);
  if (loading) next.add(String(id));
  else next.delete(String(id));
  setRef.value = next;
}

function includesKeyword(parts, keyword) {
  const kw = String(keyword || "").trim().toLowerCase();
  if (!kw) return true;
  return parts.join(" ").toLowerCase().includes(kw);
}

function mapAlgorithm(x) {
  return {
    id: x.algorithm_id,
    name: x.name,
    task: x.task,
    description: x.description || "",
    uploaderId: String(x.owner_id || ""),
    downloadCount: Number(x.download_count || 0),
    createdAt: formatTs(x.created_at),
    storagePath: "",
  };
}

function mapDataset(x) {
  return {
    id: x.dataset_id,
    name: x.name,
    type: x.type,
    size: x.size,
    description: x.description || "",
    uploaderId: String(x.owner_id || ""),
    downloadCount: Number(x.download_count || 0),
    createdAt: formatTs(x.created_at),
    storagePath: x.storage_path || "",
  };
}

function mapComment(x) {
  const resourceType = String(x.resource_type || "");
  return {
    commentId: x.comment_id,
    resourceType,
    resourceTypeLabel: resourceType === "algorithm" ? "算法" : "数据集",
    resourceId: x.resource_id,
    authorId: x.author_id,
    content: x.content,
    createdAt: formatTs(x.created_at),
  };
}

function mapReport(x) {
  const targetType = String(x.target_type || "");
  const targetTypeLabel =
    targetType === "algorithm" ? "算法" :
    targetType === "dataset" ? "数据集" :
    "评论";
  const status = String(x.status || "pending");
  return {
    reportId: x.report_id,
    targetType,
    targetTypeLabel,
    targetId: x.target_id,
    resourceType: x.resource_type || "",
    resourceId: x.resource_id || "",
    reporterId: x.reporter_id,
    reason: x.reason,
    status,
    statusLabel: status === "resolved" ? "已处理" : status === "rejected" ? "已驳回" : "待处理",
    resolution: String(x.resolution || ""),
    resolvedBy: String(x.resolved_by || ""),
    resolvedAt: x.resolved_at ? formatTs(x.resolved_at) : "",
    createdAt: formatTs(x.created_at),
  };
}

function getReportProcessTemplate(action) {
  const key = String(action || "resolve");
  if (key === "reject") return "经核实，当前举报内容不成立，已驳回。";
  if (key === "takedown_algorithm") return "经核实，该算法存在违规问题，已下架处理。";
  if (key === "takedown_dataset") return "经核实，该数据集存在违规问题，已下架处理。";
  if (key === "delete_comment") return "经核实，该评论存在违规内容，已删除处理。";
  return "管理员已核实并处理该举报。";
}

const filteredAlgorithms = computed(() =>
  (algorithms.value || []).filter((item) =>
    includesKeyword([item.name, item.task, item.uploaderId], algorithmKeyword.value)
  )
);

const filteredDatasets = computed(() =>
  (datasets.value || []).filter((item) =>
    includesKeyword([item.name, item.type, item.uploaderId], datasetKeyword.value)
  )
);

const pendingReports = computed(() =>
  (reports.value || []).filter(
    (item) =>
      String(item.status || "") === "pending" &&
      includesKeyword([item.targetTypeLabel, item.targetId, item.reporterId, item.reason], pendingReportKeyword.value)
  )
);

const handledReports = computed(() =>
  (reports.value || []).filter(
    (item) =>
      String(item.status || "") !== "pending" &&
      includesKeyword(
        [item.targetTypeLabel, item.targetId, item.reporterId, item.reason, item.resolution, item.resolvedBy],
        reportLogKeyword.value
      )
  )
);

const handledReportsCount = computed(() =>
  (reports.value || []).filter((item) => String(item.status || "") !== "pending").length
);

const detailTitle = computed(() => (detailType.value === "algorithm" ? "算法详情" : "数据集详情"));

const detailComments = computed(() =>
  (comments.value || []).filter(
    (item) =>
      String(item.resourceType || "") === String(detailType.value || "") &&
      String(item.resourceId || "") === String(detailItem.value?.id || "")
  )
);

async function loadAll() {
  if (store.user.role !== "admin") return;
  const [algRes, dsRes, commentRes, reportRes] = await Promise.all([
    adminApi.listCommunityAlgorithms(),
    adminApi.listCommunityDatasets(),
    adminApi.listComments(),
    adminApi.listReports(),
  ]);
  algorithms.value = (algRes || []).map(mapAlgorithm);
  datasets.value = (dsRes || []).map(mapDataset);
  comments.value = (commentRes || []).map(mapComment);
  reports.value = (reportRes || []).map(mapReport);
}

function openResourceDetail(type, row) {
  detailType.value = type;
  detailItem.value = row;
  detailVisible.value = true;
}

async function takedownAlgorithm(row) {
  try {
    setLoading(loadingAlgorithmIds, row.id, true);
    await adminApi.takedownAlgorithm(row.id);
    algorithms.value = algorithms.value.filter((item) => item.id !== row.id);
    ElMessage.success("算法已下架");
  } catch (e) {
    ElMessage.error(e?.message || "算法下架失败");
  } finally {
    setLoading(loadingAlgorithmIds, row.id, false);
  }
}

async function takedownDataset(row) {
  try {
    setLoading(loadingDatasetIds, row.id, true);
    await adminApi.takedownDataset(row.id);
    datasets.value = datasets.value.filter((item) => item.id !== row.id);
    ElMessage.success("数据集已下架");
  } catch (e) {
    ElMessage.error(e?.message || "数据集下架失败");
  } finally {
    setLoading(loadingDatasetIds, row.id, false);
  }
}

async function deleteComment(row) {
  try {
    setLoading(deletingCommentIds, row.commentId, true);
    await adminApi.deleteComment(row.resourceType, row.resourceId, row.commentId);
    comments.value = comments.value.filter((item) => item.commentId !== row.commentId);
    if (reportTargetComment.value?.commentId === row.commentId) {
      reportTargetComment.value = null;
    }
    ElMessage.success("评论已删除");
  } catch (e) {
    ElMessage.error(e?.message || "删除评论失败");
  } finally {
    setLoading(deletingCommentIds, row.commentId, false);
  }
}

function openReportProcess(row) {
  activeReport.value = row;
  reportProcessAction.value =
    row?.targetType === "algorithm"
      ? "takedown_algorithm"
      : row?.targetType === "dataset"
        ? "takedown_dataset"
        : row?.targetType === "comment"
          ? "delete_comment"
          : "resolve";
  reportTargetDetail.value = null;
  reportTargetComment.value = null;
  reportProcessVisible.value = true;
  reportProcessNote.value = getReportProcessTemplate(reportProcessAction.value);
  loadReportTargetDetail(row);
}

function closeReportProcess() {
  reportProcessVisible.value = false;
  activeReport.value = null;
  reportProcessAction.value = "resolve";
  reportProcessNote.value = "";
  reportTargetDetail.value = null;
  reportTargetComment.value = null;
}

watch(reportProcessAction, (next) => {
  reportProcessNote.value = getReportProcessTemplate(next);
});

async function loadReportTargetDetail(row) {
  if (!row) return;
  try {
    if (row.targetType === "algorithm") {
      const x = await adminApi.getCommunityAlgorithmDetail(row.targetId);
      reportTargetDetail.value = mapAlgorithm(x);
      return;
    }
    if (row.targetType === "dataset") {
      const x = await adminApi.getCommunityDatasetDetail(row.targetId);
      reportTargetDetail.value = mapDataset(x);
      return;
    }
    if (row.targetType === "comment") {
      if (row.resourceType === "algorithm") {
        const x = await adminApi.getCommunityAlgorithmDetail(row.resourceId);
        reportTargetDetail.value = mapAlgorithm(x);
      } else if (row.resourceType === "dataset") {
        const x = await adminApi.getCommunityDatasetDetail(row.resourceId);
        reportTargetDetail.value = mapDataset(x);
      }
      reportTargetComment.value =
        (comments.value || []).find((item) => String(item.commentId || "") === String(row.targetId || "")) || null;
    }
  } catch {
    reportTargetDetail.value = null;
    reportTargetComment.value = null;
  }
}

async function copyDatasetPath(path) {
  const text = String(path || "").trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("路径已复制");
  } catch {
    ElMessage.warning("复制失败，请手动复制路径");
  }
}

function openDatasetFolder(path) {
  const text = String(path || "").trim();
  if (!text) return;
  const normalized = text.replace(/\\/g, "/");
  window.open(`file:///${normalized}`, "_blank");
  ElMessage.info("已尝试打开文件夹；如果浏览器拦截，请先复制路径再手动打开。");
}

async function submitReportProcess() {
  const row = activeReport.value;
  if (!row?.reportId) return;
  const action = String(reportProcessAction.value || "resolve");
  const note = String(reportProcessNote.value || "").trim() || getReportProcessTemplate(action);
  try {
    reportProcessSubmitting.value = true;
    setLoading(resolvingReportIds, row.reportId, true);

    if (action === "takedown_algorithm") {
      await adminApi.takedownAlgorithm(row.targetId);
      algorithms.value = algorithms.value.filter((item) => item.id !== row.targetId);
    } else if (action === "takedown_dataset") {
      await adminApi.takedownDataset(row.targetId);
      datasets.value = datasets.value.filter((item) => item.id !== row.targetId);
    } else if (action === "delete_comment") {
      await adminApi.deleteComment(row.resourceType, row.resourceId, row.targetId);
      comments.value = comments.value.filter((item) => item.commentId !== row.targetId);
      if (reportTargetComment.value?.commentId === row.targetId) {
        reportTargetComment.value = null;
      }
    }

    const status = action === "reject" ? "rejected" : "resolved";
    await adminApi.resolveReport(row.reportId, { status, resolution: note });
    reports.value = reports.value.map((item) =>
      item.reportId === row.reportId
        ? {
            ...item,
            status,
            statusLabel: status === "rejected" ? "已驳回" : "已处理",
            resolution: note,
            resolvedBy: String(store.user.username || ""),
            resolvedAt: formatTs(Math.floor(Date.now() / 1000)),
          }
        : item
    );
    ElMessage.success(status === "rejected" ? "举报已驳回" : "举报已处理");
    closeReportProcess();
  } catch (e) {
    ElMessage.error(e?.message || "处理举报失败");
  } finally {
    reportProcessSubmitting.value = false;
    setLoading(resolvingReportIds, row.reportId, false);
  }
}

async function clearHandledReports() {
  try {
    clearingReports.value = true;
    const res = await adminApi.clearReports("handled");
    reports.value = (reports.value || []).filter((item) => String(item.status || "") === "pending");
    ElMessage.success(`已清除 ${Number(res?.deleted || 0)} 条处理记录`);
  } catch (e) {
    ElMessage.error(e?.message || "清除记录失败");
  } finally {
    clearingReports.value = false;
  }
}

onMounted(loadAll);
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
}

.warn-box {
  margin-bottom: 20px;
}

.toolbar {
  margin-bottom: 14px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  max-width: 420px;
}

.clear-btn {
  margin-left: auto;
}

.data-table {
  width: 100%;
}

.detail-panel,
.process-panel {
  display: grid;
  gap: 18px;
}

.detail-summary {
  display: grid;
  gap: 10px;
}

.detail-name {
  font-size: 22px;
  font-weight: 700;
  color: #1f2f57;
}

.detail-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: #5d6c8c;
}

.detail-block {
  display: grid;
  gap: 10px;
}

.block-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2f57;
}

.description-box,
.process-detail-desc,
.process-path,
.process-comment-box,
.process-meta {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fbff;
  border: 1px solid #dce7ff;
  color: #334466;
  line-height: 1.7;
  white-space: pre-wrap;
}

.process-detail-card {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e6eeff;
}

.process-detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.process-detail-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2f57;
  margin-right: auto;
}

.process-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px 16px;
  color: #334466;
}

.full-width {
  width: 100%;
}

.comment-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e6eeff;
}

.comment-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  color: #5d6c8c;
}

.comment-head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.comment-author {
  font-weight: 700;
  color: #1f2f57;
}

.comment-content {
  color: #334466;
  line-height: 1.7;
  white-space: pre-wrap;
}

.empty-text {
  color: #7b89a8;
}
</style>
