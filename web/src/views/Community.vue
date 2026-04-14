<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">社区中心</h2>
      <div class="subtitle">浏览社区公开的算法、数据集和指标，支持搜索、筛选、排序、查看详情和下载到当前账号。</div>
    </div>

    <div class="toolbar-card">
      <div class="toolbar-row">
        <el-input
          v-model="keyword"
          placeholder="搜索名称 / 任务 / 实现方式"
          clearable
          class="search-input"
        />
        <el-tabs v-model="tab" class="resource-switch-tabs">
          <el-tab-pane label="公开算法" name="algorithms" />
          <el-tab-pane label="公开数据集" name="datasets" />
          <el-tab-pane label="公开指标" name="metrics" />
        </el-tabs>
        <el-select v-model="sortBy" class="sort-select">
          <el-option label="最新发布" value="newest" />
          <el-option label="名称排序" value="name" />
        </el-select>
      </div>

      <div class="toolbar-row" v-if="tab === 'algorithms'">
        <el-select v-model="taskFilter" clearable placeholder="全部任务" class="filter-select">
          <el-option v-for="item in algorithmTaskOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="implFilter" clearable placeholder="全部实现" class="filter-select">
          <el-option v-for="item in algorithmImplOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </div>

      <div class="toolbar-row" v-else-if="tab === 'datasets'">
        <el-select v-model="datasetTypeFilter" clearable placeholder="全部介质" class="filter-select">
          <el-option label="图像" value="图像" />
          <el-option label="视频" value="视频" />
          <el-option label="图像/视频" value="图像/视频" />
        </el-select>
        <el-select v-model="datasetTaskFilter" clearable placeholder="全部任务" class="filter-select">
          <el-option v-for="(label, key) in TASK_LABEL_BY_TYPE" :key="key" :label="label" :value="key" />
        </el-select>
      </div>

      <div class="toolbar-row" v-else>
        <el-select v-model="metricDirectionFilter" clearable placeholder="全部方向" class="filter-select">
          <el-option label="越大越好" value="higher_better" />
          <el-option label="越小越好" value="lower_better" />
        </el-select>
      </div>
    </div>

    <div v-if="tab === 'algorithms'" class="section">
      <el-table
        v-loading="communityListLoading"
        element-loading-text="加载中..."
        :data="filteredAlgorithms"
        border
        stripe
        class="data-table"
      >
        <el-table-column prop="name" label="算法名称" min-width="220" />
        <el-table-column prop="task" label="任务" width="140" />
        <el-table-column prop="impl" label="实现方式" width="120" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="uploaderId" label="上传者" width="140" />
        <el-table-column prop="downloadCount" label="下载量" width="100" />
        <el-table-column prop="createdAt" label="发布时间" width="180" />
        <el-table-column label="操作" width="190">
          <template #default="{ row }">
            <el-button size="small" plain @click="openDetail('algorithm', row)">详情</el-button>
            <el-button
              size="small"
              type="primary"
              @click="downloadAlgorithm(row)"
              :loading="downloadingAlgorithmIds.has(row.id)"
              :disabled="!store.user.isLoggedIn || isOwnedByCurrentUser(row) || isAlgorithmDownloaded(row)"
            >
              {{ getAlgorithmActionLabel(row) }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无符合条件的公开算法" />
        </template>
      </el-table>
    </div>

    <div v-else-if="tab === 'datasets'" class="section">
      <el-table
        v-loading="communityListLoading"
        element-loading-text="加载中..."
        :data="filteredDatasets"
        border
        stripe
        class="data-table"
      >
        <el-table-column prop="name" label="数据集名称" min-width="220" />
        <el-table-column prop="type" label="介质" width="100" />
        <el-table-column label="适用任务" min-width="200">
          <template #default="{ row }">
            {{ formatDatasetTaskTypes(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="size" label="规模" width="140" />
        <el-table-column prop="uploaderId" label="上传者" width="140" />
        <el-table-column prop="downloadCount" label="下载量" width="100" />
        <el-table-column prop="createdAt" label="发布时间" width="180" />
        <el-table-column label="操作" width="190">
          <template #default="{ row }">
            <el-button size="small" plain @click="openDetail('dataset', row)">详情</el-button>
            <el-button
              size="small"
              type="primary"
              @click="downloadDataset(row)"
              :loading="downloadingDatasetIds.has(row.id)"
              :disabled="!store.user.isLoggedIn || isOwnedByCurrentUser(row) || isDatasetDownloaded(row)"
            >
              {{ getDatasetActionLabel(row) }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无符合条件的公开数据集" />
        </template>
      </el-table>
    </div>

    <div v-else class="section">
      <el-table
        v-loading="communityListLoading"
        element-loading-text="加载中..."
        :data="filteredMetrics"
        border
        stripe
        class="data-table"
      >
        <el-table-column prop="displayName" label="指标名称" min-width="180" />
        <el-table-column prop="metricKey" label="标识" width="170" />
        <el-table-column label="方向" width="120">
          <template #default="{ row }">
            {{ row.direction === "lower_better" ? "越小越好" : "越大越好" }}
          </template>
        </el-table-column>
        <el-table-column label="适用任务" min-width="180">
          <template #default="{ row }">
            {{ formatMetricTaskTypes(row.taskTypes) }}
          </template>
        </el-table-column>
        <el-table-column prop="uploaderId" label="上传者" width="140" />
        <el-table-column prop="downloadCount" label="下载量" width="100" />
        <el-table-column prop="createdAt" label="发布时间" width="180" />
        <el-table-column label="操作" width="190">
          <template #default="{ row }">
            <el-button size="small" plain @click="openDetail('metric', row)">详情</el-button>
            <el-button
              size="small"
              type="primary"
              @click="downloadMetric(row)"
              :loading="downloadingMetricIds.has(row.id)"
              :disabled="!store.user.isLoggedIn || isOwnedByCurrentUser(row) || isMetricDownloaded(row)"
            >
              {{ getMetricActionLabel(row) }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无符合条件的公开指标" />
        </template>
      </el-table>
    </div>

    <el-dialog v-model="detailVisible" :title="detailTitle" width="780px">
      <div v-if="detailItem" class="detail-panel">
        <div class="detail-summary">
          <div class="detail-name">{{ detailItem.name }}</div>
          <div class="detail-meta">
            <span>上传者：{{ detailItem.uploaderId || "-" }}</span>
            <span>下载量：{{ detailItem.downloadCount ?? 0 }}</span>
            <span>发布时间：{{ detailItem.createdAt || "-" }}</span>
          </div>
          <div class="detail-meta">
            <span v-if="detailType === 'algorithm'">任务：{{ detailItem.task || "-" }}</span>
            <span v-if="detailType === 'algorithm'">实现方式：{{ detailItem.impl || "-" }}</span>
            <span v-if="detailType === 'algorithm'">版本：{{ detailItem.version || "-" }}</span>
            <span v-if="detailType === 'dataset'">介质：{{ detailItem.type || "-" }}</span>
            <span v-if="detailType === 'dataset'">适用任务：{{ formatDatasetTaskTypes(detailItem) }}</span>
            <span v-if="detailType === 'dataset'">规模：{{ detailItem.size || "-" }}</span>
            <span v-if="detailType === 'metric'">标识：{{ detailItem.metricKey || "-" }}</span>
            <span v-if="detailType === 'metric'">方向：{{ detailItem.direction === "lower_better" ? "越小越好" : "越大越好" }}</span>
            <span v-if="detailType === 'metric'">GT：{{ detailItem.requiresReference ? "需要" : "不需要" }}</span>
          </div>
        </div>

        <div class="detail-block">
          <div class="block-head">
            <div class="block-title">社区说明</div>
            <el-button
              v-if="detailType !== 'metric'"
              size="small"
              plain
              type="danger"
              @click="openReportDialog('resource')"
              :disabled="!store.user.isLoggedIn"
            >
              举报
            </el-button>
          </div>
          <div v-if="detailIsUserPackage" class="package-detail-grid">
            <div class="package-detail-card package-detail-card-wide">
              <div class="package-detail-title">社区说明</div>
              <div class="package-detail-text">{{ detailItem.description || "暂无社区说明" }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">算法说明</div>
              <div class="package-detail-text">{{ cleanPackageDescription(detailItem) }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">依赖环境</div>
              <div class="package-detail-text">{{ detailItem.dependencyText || "未填写依赖说明" }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">入口说明</div>
              <div class="package-detail-text">{{ detailItem.entryText || "未填写入口说明" }}</div>
            </div>
            <div class="package-detail-card package-detail-card-wide">
              <div class="package-detail-title">代码包</div>
              <div class="package-archive-row">
                <span>{{ detailItem.archiveFilename || "未记录代码包文件名" }}</span>
                <span v-if="detailItem.archiveSha256" class="archive-digest">SHA256：{{ shortDigest(detailItem.archiveSha256) }}</span>
              </div>
              <div class="package-note">下载到算法库后，在算法库中导出会优先下载原始代码包；没有代码包时才回退导出 JSON 元信息。</div>
            </div>
          </div>
          <div v-else-if="detailType === 'metric'" class="package-detail-grid">
            <div class="package-detail-card package-detail-card-wide">
              <div class="package-detail-title">社区说明</div>
              <div class="package-detail-text">{{ detailItem.description || "暂无社区说明" }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">指标说明</div>
              <div class="package-detail-text">{{ detailItem.description || "暂无指标说明" }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">适用任务</div>
              <div class="package-detail-text">{{ formatMetricTaskTypes(detailItem.taskTypes) }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">实现方式</div>
              <div class="package-detail-text">{{ detailItem.implementationType === "formula" ? "公式 / 说明型指标" : "Python 指标代码" }}</div>
            </div>
            <div class="package-detail-card">
              <div class="package-detail-title">代码文件</div>
              <div class="package-detail-text">{{ detailItem.codeFilename || "未提供代码文件名" }}</div>
            </div>
          </div>
          <div v-else class="description-box">{{ detailItem.description || "暂无社区说明" }}</div>
        </div>

        <div v-if="detailType !== 'metric'" class="detail-block">
          <div class="block-title">评论区</div>
          <div v-loading="commentsLoading" class="comment-list">
            <div v-if="!detailComments.length" class="empty-text">暂无评论，欢迎发表第一条评论。</div>
            <div v-for="comment in detailComments" :key="comment.comment_id" class="comment-item">
              <div class="comment-head">
                <div class="comment-head-left">
                  <span class="comment-author">{{ comment.author_id }}</span>
                  <span class="comment-time">{{ formatTs(comment.created_at) }}</span>
                </div>
                <div class="comment-head-actions">
                  <el-button
                    v-if="store.user.isLoggedIn && canReportComment(comment)"
                    size="small"
                    text
                    type="warning"
                    @click="openReportDialog('comment', comment)"
                  >
                    举报
                  </el-button>
                  <el-button
                    v-if="canDeleteComment(comment)"
                    size="small"
                    text
                    type="danger"
                    @click="deleteComment(comment)"
                    :loading="deletingCommentIds.has(comment.comment_id)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
              <div class="comment-content">{{ comment.content }}</div>
            </div>
          </div>
          <div class="comment-editor">
            <el-input
              v-model="commentDraft"
              type="textarea"
              :rows="3"
              placeholder="写下你对这个算法或数据集的看法"
            />
            <div class="comment-actions">
              <el-button type="primary" @click="submitComment" :disabled="!store.user.isLoggedIn" :loading="commentSubmitting">
                发表评论
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="reportVisible" title="提交举报" width="520px">
      <el-form label-position="top">
        <el-form-item label="举报原因">
          <el-input
            v-model="reportReason"
            type="textarea"
            :rows="4"
            placeholder="请简要说明举报原因，例如侵权、内容不实、恶意评论等"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeReportDialog">取消</el-button>
        <el-button type="danger" @click="submitReport" :loading="reportSubmitting">提交举报</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
export default { name: "Community" };
</script>
<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { datasetsApi } from "../api/datasets";
import { algorithmsApi } from "../api/algorithms";
import { metricsApi } from "../api/metrics";
import { communityApi } from "../api/community";
import { TASK_LABEL_BY_TYPE, useAppStore } from "../stores/app";
import { datasetSupportsTaskType } from "../utils/datasetTask";

const store = useAppStore();
const communityAlgorithms = ref([]);
const communityDatasets = ref([]);
const communityMetrics = ref([]);
/** 首次进入与刷新列表时，避免在请求未完成前误显示「暂无数据」 */
const communityListLoading = ref(true);

const tab = ref("algorithms");
const keyword = ref("");
const sortBy = ref("newest");
const taskFilter = ref("");
const implFilter = ref("");
const datasetTypeFilter = ref("");
const datasetTaskFilter = ref("");
const metricDirectionFilter = ref("");
const downloadingAlgorithmIds = ref(new Set());
const downloadingDatasetIds = ref(new Set());
const downloadingMetricIds = ref(new Set());
const locallyDownloadedAlgorithmIds = ref(new Set());
const locallyDownloadedDatasetIds = ref(new Set());
const locallyDownloadedMetricIds = ref(new Set());
const detailVisible = ref(false);
const detailType = ref("algorithm");
const detailItem = ref(null);
const detailComments = ref([]);
const commentsLoading = ref(false);
const commentDraft = ref("");
const commentSubmitting = ref(false);
const deletingCommentIds = ref(new Set());
const reportVisible = ref(false);
const reportSubmitting = ref(false);
const reportReason = ref("");
const reportTarget = ref({ mode: "resource", comment: null });
/** keep-alive 缓存下，从其它页返回时需重新拉列表，否则会看到已下架/已删除前的旧数据 */
const communityWasLeftOnce = ref(false);

function formatTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(Number(unixSeconds) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function mapAlgorithm(x) {
  return {
    id: x.algorithm_id,
    task: x.task,
    name: x.name,
    impl: x.impl,
    version: x.version,
    description: x.description || "",
    dependencyText: String(x.dependency_text || ""),
    entryText: String(x.entry_text || ""),
    archiveFilename: String(x.archive_filename || ""),
    archiveSha256: String(x.archive_sha256 || ""),
    sourceSubmissionId: String(x.source_submission_id || ""),
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    uploaderId: String(x.owner_id || ""),
    createdAt: formatTs(x.created_at),
    raw: x,
  };
}

function mapDataset(x) {
  const meta = x.meta && typeof x.meta === "object" ? x.meta : {};
  return {
    id: x.dataset_id,
    name: x.name,
    type: x.type,
    size: x.size,
    description: x.description || "",
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    uploaderId: String(x.owner_id || ""),
    taskTypes: Array.isArray(x.task_types) ? x.task_types : [],
    meta,
    createdAt: formatTs(x.created_at),
    raw: x,
  };
}

function formatDatasetTaskTypes(row) {
  const rawTt = row?.raw?.task_types;
  const list = Array.isArray(row?.taskTypes) && row.taskTypes.length
    ? row.taskTypes
    : Array.isArray(rawTt)
      ? rawTt
      : [];
  if (list.length) return list.map((k) => TASK_LABEL_BY_TYPE[k] || k).join(" / ");
  const sup = row?.meta?.supported_task_types || row?.raw?.meta?.supported_task_types;
  if (Array.isArray(sup) && sup.length) return sup.map((k) => TASK_LABEL_BY_TYPE[k] || k).join(" / ");
  const pairs = row?.meta?.pairs_by_task || row?.raw?.meta?.pairs_by_task;
  if (pairs && typeof pairs === "object") {
    const keys = Object.keys(pairs).filter((k) => Number(pairs[k] ?? 0) > 0);
    if (keys.length) return keys.map((k) => TASK_LABEL_BY_TYPE[k] || k).join(" / ");
  }
  return "未标注";
}

function mapMetric(x) {
  return {
    id: x.metric_id,
    metricKey: String(x.metric_key || ""),
    name: String(x.name || ""),
    displayName: String(x.display_name || x.name || x.metric_key || ""),
    description: String(x.description || ""),
    taskTypes: Array.isArray(x.task_types) ? x.task_types : [],
    direction: String(x.direction || "higher_better"),
    requiresReference: Boolean(x.requires_reference),
    implementationType: String(x.implementation_type || "python"),
    formulaText: String(x.formula_text || ""),
    codeFilename: String(x.code_filename || ""),
    downloadCount: Number(x.download_count || 0),
    visibility: String(x.visibility || "private"),
    allowDownload: Boolean(x.allow_download),
    uploaderId: String(x.owner_id || ""),
    sourceOwnerId: String(x.source_owner_id || ""),
    sourceMetricId: String(x.source_metric_id || ""),
    createdAt: formatTs(x.created_at),
    raw: x,
  };
}

async function loadCommunity() {
  communityListLoading.value = true;
  try {
    const [algorithms, datasets, metrics] = await Promise.all([
      algorithmsApi.listAlgorithms({ limit: 500, scope: "community" }),
      datasetsApi.listDatasets({ limit: 200, scope: "community" }),
      metricsApi.listMetrics({ limit: 500, scope: "community" }),
    ]);
    communityAlgorithms.value = (algorithms || []).map(mapAlgorithm);
    communityDatasets.value = (datasets || []).map(mapDataset);
    communityMetrics.value = (metrics || []).map(mapMetric);
  } catch (e) {
    ElMessage({ type: "error", message: `加载社区资源失败：${e?.message || e}` });
    communityAlgorithms.value = [];
    communityDatasets.value = [];
    communityMetrics.value = [];
  } finally {
    communityListLoading.value = false;
  }
}

function setLoading(setRef, id, loading) {
  const next = new Set(setRef.value);
  if (loading) next.add(id);
  else next.delete(id);
  setRef.value = next;
}

function isOwnedByCurrentUser(item) {
  return String(item?.raw?.owner_id || "") === String(store.user?.username || "");
}

function getAlgorithmActionLabel(row) {
  if (isOwnedByCurrentUser(row)) return "自传";
  if (isAlgorithmDownloaded(row)) return "已下载";
  return "下载";
}

function getDatasetActionLabel(row) {
  if (isOwnedByCurrentUser(row)) return "自传";
  if (isDatasetDownloaded(row)) return "已下载";
  return "下载";
}

function getMetricActionLabel(row) {
  if (isOwnedByCurrentUser(row)) return "自传";
  if (isMetricDownloaded(row)) return "已下载";
  return "下载";
}

function findDownloadedAlgorithmCopy(row) {
  const currentUser = String(store.user?.username || "").trim();
  const sourceAlgorithmId = String(row?.id || "").trim();
  const sourceUploaderId = String(row?.uploaderId || "").trim();
  if (!currentUser || !sourceAlgorithmId || !sourceUploaderId) return null;
  return (
    (store.algorithms || []).find((item) => {
      if (String(item?.uploaderId || "").trim() !== currentUser) return false;
      if (String(item?.raw?.owner_id || "").trim() === "system") return false;
      if (String(item?.sourceAlgorithmId || "").trim() !== sourceAlgorithmId) return false;
      return String(item?.sourceUploaderId || "").trim() === sourceUploaderId;
    }) || null
  );
}

function isAlgorithmDownloaded(row) {
  if (locallyDownloadedAlgorithmIds.value.has(String(row?.id || ""))) return true;
  return Boolean(findDownloadedAlgorithmCopy(row));
}

function isDatasetDownloaded(row) {
  if (locallyDownloadedDatasetIds.value.has(String(row?.id || ""))) return true;
  const currentUser = String(store.user?.username || "");
  return (store.datasets || []).some((item) => {
    if (String(item?.uploaderId || "") !== currentUser) return false;
    if (String(item?.sourceUploaderId || "") !== String(row?.uploaderId || "")) return false;
    return String(item?.sourceDatasetId || "") === String(row?.id || "");
  });
}

function isMetricDownloaded(row) {
  if (locallyDownloadedMetricIds.value.has(String(row?.id || ""))) return true;
  const currentUser = String(store.user?.username || "");
  return (store.metricsCatalog || []).some((item) => {
    if (String(item?.uploaderId || "") !== currentUser) return false;
    if (String(item?.sourceOwnerId || "") !== String(row?.uploaderId || "")) return false;
    return String(item?.sourceMetricId || "") === String(row?.id || "");
  });
}

function formatMetricTaskTypes(list) {
  if (!Array.isArray(list) || !list.length) return "未限定";
  return list.map((item) => TASK_LABEL_BY_TYPE[item] || item).join(" / ");
}

function getErrorCode(error) {
  return String(
    error?.detail?.error_code ||
      error?.data?.detail?.error_code ||
      error?.data?.error_code ||
      error?.error_code ||
      ""
  );
}

function isResourceGoneError(error, resourceType = "") {
  const code = getErrorCode(error);
  const text = String(error?.message || error || "");
  if (text.includes("[404]")) return true;
  if (resourceType === "algorithm") {
    return code === "E_ALGORITHM_NOT_FOUND" || text.includes("algorithm_not_public");
  }
  if (resourceType === "dataset") {
    return code === "E_DATASET_NOT_FOUND" || text.includes("dataset_not_public") || text.includes("empty_dataset_not_allowed");
  }
  return false;
}

function setCommentDeleting(commentId, loading) {
  const next = new Set(deletingCommentIds.value);
  if (loading) next.add(String(commentId));
  else next.delete(String(commentId));
  deletingCommentIds.value = next;
}

function canDeleteComment(comment) {
  return String(comment?.author_id || "") === String(store.user?.username || "");
}

function canReportComment(comment) {
  return String(comment?.author_id || "") !== String(store.user?.username || "");
}

const detailTitle = computed(() => {
  if (detailType.value === "algorithm") return "算法详情";
  if (detailType.value === "metric") return "指标详情";
  return "数据集详情";
});
const detailIsUserPackage = computed(() => {
  const item = detailItem.value || {};
  return detailType.value === "algorithm" && (item.impl === "UserPackage" || Boolean(item.sourceSubmissionId));
});

function cleanPackageDescription(item) {
  let text = String(item?.description || "").trim();
  for (const token of ["依赖说明：", "入口说明：", "该算法来自", "该算法由用户"]) {
    const idx = text.indexOf(token);
    if (idx >= 0) text = text.slice(0, idx).trim();
  }
  return text || "暂无算法说明";
}

function shortDigest(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.length > 16 ? `${text.slice(0, 12)}...${text.slice(-6)}` : text;
}

async function openDetail(type, row) {
  detailType.value = type;
  detailItem.value = row;
  detailVisible.value = true;
  commentDraft.value = "";
  await loadComments();
}

async function loadComments() {
  if (!detailItem.value?.id) {
    detailComments.value = [];
    return;
  }
  commentsLoading.value = true;
  try {
    if (detailType.value === "metric") {
      detailComments.value = [];
      return;
    }
    detailComments.value =
      detailType.value === "algorithm"
        ? await communityApi.listAlgorithmComments(detailItem.value.id)
        : await communityApi.listDatasetComments(detailItem.value.id);
  } catch (e) {
    detailComments.value = [];
    const text = String(e?.message || e || "");
    if (text.includes("[403]") || text.includes("[404]")) {
      detailVisible.value = false;
      detailItem.value = null;
      await loadCommunity();
      ElMessage({ type: "warning", message: "该社区资源已下架或不可见，已从列表中同步移除" });
      return;
    }
    ElMessage({ type: "error", message: `加载评论失败：${e?.message || e}` });
  } finally {
    commentsLoading.value = false;
  }
}

async function syncCommunityState() {
  await Promise.all([
    loadCommunity(),
    store.warmSessionData({ includeNotices: false }),
  ]);
  if (!detailVisible.value || !detailItem.value?.id) return;
  const sourceList =
    detailType.value === "algorithm"
      ? communityAlgorithms.value
      : detailType.value === "metric"
        ? communityMetrics.value
        : communityDatasets.value;
  const latest = (sourceList || []).find((item) => String(item?.id || "") === String(detailItem.value?.id || ""));
  if (!latest) {
    detailVisible.value = false;
    detailItem.value = null;
    detailComments.value = [];
    ElMessage({ type: "warning", message: "该社区资源已下架或不可见，已从列表中同步移除" });
    return;
  }
  detailItem.value = latest;
  await loadComments();
}

async function handleWindowFocus() {
  await Promise.allSettled([
    loadCommunity(),
    store.warmSessionData({ includeNotices: false }),
  ]);
}

async function submitComment() {
  if (!store.user?.isLoggedIn) {
    ElMessage({ type: "warning", message: "请先登录后再发表评论" });
    return;
  }
  const content = String(commentDraft.value || "").trim();
  if (!content) {
    ElMessage({ type: "warning", message: "请先填写评论内容" });
    return;
  }
  commentSubmitting.value = true;
  try {
    if (detailType.value === "algorithm") {
      await communityApi.createAlgorithmComment(detailItem.value.id, content);
    } else {
      await communityApi.createDatasetComment(detailItem.value.id, content);
    }
    commentDraft.value = "";
    await loadComments();
    ElMessage({ type: "success", message: "评论已发布" });
  } catch (e) {
    ElMessage({ type: "error", message: `评论失败：${e?.message || e}` });
  } finally {
    commentSubmitting.value = false;
  }
}

async function deleteComment(comment) {
  const commentId = String(comment?.comment_id || "");
  if (!commentId || !detailItem.value?.id) return;
  try {
    setCommentDeleting(commentId, true);
    if (detailType.value === "algorithm") {
      await communityApi.deleteAlgorithmComment(detailItem.value.id, commentId);
    } else {
      await communityApi.deleteDatasetComment(detailItem.value.id, commentId);
    }
    detailComments.value = detailComments.value.filter((item) => String(item?.comment_id || "") !== commentId);
    ElMessage({ type: "success", message: "评论已删除" });
  } catch (e) {
    ElMessage({ type: "error", message: `删除评论失败：${e?.message || e}` });
  } finally {
    setCommentDeleting(commentId, false);
  }
}

function openReportDialog(mode, comment = null) {
  if (!store.user?.isLoggedIn) {
    ElMessage({ type: "warning", message: "请先登录后再举报" });
    return;
  }
  if (mode === "comment" && !canReportComment(comment)) {
    ElMessage({ type: "warning", message: "不能举报自己的评论" });
    return;
  }
  reportTarget.value = { mode, comment };
  reportReason.value = "";
  reportVisible.value = true;
}

function closeReportDialog() {
  reportVisible.value = false;
  reportReason.value = "";
  reportTarget.value = { mode: "resource", comment: null };
}

async function submitReport() {
  const reason = String(reportReason.value || "").trim();
  if (!reason) {
    ElMessage({ type: "warning", message: "请先填写举报原因" });
    return;
  }
  if (!detailItem.value?.id) return;
  const isComment = reportTarget.value.mode === "comment";
  const comment = reportTarget.value.comment;
  if (isComment && !canReportComment(comment)) {
    ElMessage({ type: "warning", message: "不能举报自己的评论" });
    return;
  }
  const payload = isComment
    ? {
        target_type: "comment",
        target_id: String(comment?.comment_id || ""),
        resource_type: detailType.value,
        resource_id: detailItem.value.id,
        reason,
      }
    : {
        target_type: detailType.value,
        target_id: detailItem.value.id,
        reason,
      };
  reportSubmitting.value = true;
  try {
    await communityApi.createReport(payload);
    ElMessage({ type: "success", message: "举报已提交，等待管理员处理" });
    closeReportDialog();
  } catch (e) {
    const text = String(e?.message || e || "");
    if (text.includes("report_already_exists")) {
      ElMessage({ type: "warning", message: "你已经提交过这条举报，等待管理员处理即可" });
      closeReportDialog();
      return;
    }
    ElMessage({ type: "error", message: `举报失败：${e?.message || e}` });
  } finally {
    reportSubmitting.value = false;
  }
}

async function downloadAlgorithm(row) {
  if (!store.user?.isLoggedIn) {
    ElMessage({ type: "warning", message: "请先登录后再下载算法" });
    return;
  }
  try {
    setLoading(downloadingAlgorithmIds, row.id, true);
    await algorithmsApi.downloadCommunityAlgorithm(row.id);
    locallyDownloadedAlgorithmIds.value = new Set([...locallyDownloadedAlgorithmIds.value, String(row.id)]);
    await store.fetchAlgorithms(500, { force: true });
    await loadCommunity();
    ElMessage({ type: "success", message: "已下载到你的算法库中" });
  } catch (e) {
    if (getErrorCode(e) === "E_HTTP" && String(e?.message || "").includes("algorithm_already_downloaded")) {
      await store.fetchAlgorithms(500, { force: true });
      await loadCommunity();
      if (findDownloadedAlgorithmCopy(row)) {
        locallyDownloadedAlgorithmIds.value = new Set([...locallyDownloadedAlgorithmIds.value, String(row.id)]);
        ElMessage({ type: "info", message: "该算法已存在于你的算法库中" });
      } else {
        ElMessage({ type: "warning", message: "后端判定该算法已有副本，但当前账号下未找到对应记录，已自动刷新算法库" });
      }
      return;
    }
    if (isResourceGoneError(e, "algorithm")) {
      await loadCommunity();
      ElMessage({ type: "warning", message: "该社区算法已下架或不可见，已从列表中同步移除" });
      return;
    }
    ElMessage({ type: "error", message: `下载算法失败：${e?.message || e}` });
  } finally {
    setLoading(downloadingAlgorithmIds, row.id, false);
  }
}

async function downloadDataset(row) {
  if (!store.user?.isLoggedIn) {
    ElMessage({ type: "warning", message: "请先登录后再下载数据集" });
    return;
  }
  try {
    setLoading(downloadingDatasetIds, row.id, true);
    await datasetsApi.downloadCommunityDataset(row.id);
    locallyDownloadedDatasetIds.value = new Set([...locallyDownloadedDatasetIds.value, String(row.id)]);
    await store.fetchDatasets();
    await loadCommunity();
    ElMessage({ type: "success", message: "已下载到你的数据集库中" });
  } catch (e) {
    if (getErrorCode(e) === "E_HTTP" && String(e?.message || "").includes("dataset_already_downloaded")) {
      locallyDownloadedDatasetIds.value = new Set([...locallyDownloadedDatasetIds.value, String(row.id)]);
      await store.fetchDatasets();
      await loadCommunity();
      ElMessage({ type: "info", message: "该数据集已下载到你的数据集库中" });
      return;
    }
    if (isResourceGoneError(e, "dataset")) {
      await store.fetchDatasets();
      await loadCommunity();
      ElMessage({ type: "warning", message: "该社区数据集已下架或源文件失效，已从列表中同步移除" });
      return;
    }
    ElMessage({ type: "error", message: `下载数据集失败：${e?.message || e}` });
  } finally {
    setLoading(downloadingDatasetIds, row.id, false);
  }
}

async function downloadMetric(row) {
  if (!store.user?.isLoggedIn) {
    ElMessage({ type: "warning", message: "请先登录后再下载指标" });
    return;
  }
  try {
    setLoading(downloadingMetricIds, row.id, true);
    await store.downloadCommunityMetric(row.id);
    locallyDownloadedMetricIds.value = new Set([...locallyDownloadedMetricIds.value, String(row.id)]);
    await store.fetchMetrics();
    await loadCommunity();
    ElMessage({ type: "success", message: "已下载到你的指标库中" });
  } catch (e) {
    const text = String(e?.message || e || "");
    if (getErrorCode(e) === "E_HTTP" && text.includes("metric_already_downloaded")) {
      locallyDownloadedMetricIds.value = new Set([...locallyDownloadedMetricIds.value, String(row.id)]);
      await store.fetchMetrics();
      await loadCommunity();
      ElMessage({ type: "info", message: "该指标已下载到你的指标库中" });
      return;
    }
    ElMessage({ type: "error", message: `下载指标失败：${e?.message || e}` });
  } finally {
    setLoading(downloadingMetricIds, row.id, false);
  }
}

onMounted(async () => {
  await syncCommunityState();
});

onActivated(() => {
  window.addEventListener("focus", handleWindowFocus);
  if (communityWasLeftOnce.value) {
    loadCommunity().catch(() => {});
  }
});

onDeactivated(() => {
  window.removeEventListener("focus", handleWindowFocus);
  communityWasLeftOnce.value = true;
});

onBeforeUnmount(() => {
  window.removeEventListener("focus", handleWindowFocus);
});

function byKeyword(textParts) {
  const kw = String(keyword.value || "").trim().toLowerCase();
  if (!kw) return true;
  return textParts.join(" ").toLowerCase().includes(kw);
}

function sortItems(items) {
  const list = [...items];
  if (sortBy.value === "name") {
    list.sort((a, b) => String(a?.name || "").localeCompare(String(b?.name || ""), "zh-Hans-CN-u-co-pinyin"));
    return list;
  }
  list.sort((a, b) => Number(b?.raw?.created_at || 0) - Number(a?.raw?.created_at || 0));
  return list;
}

const publicAlgorithms = computed(() =>
  (communityAlgorithms.value || []).filter((item) => {
    const ownerId = String(item?.raw?.owner_id || "");
    const visibility = String(item?.visibility || item?.raw?.visibility || "").toLowerCase();
    if (ownerId === "system") return false;
    return visibility === "public";
  })
);

const publicDatasets = computed(() =>
  (communityDatasets.value || []).filter((item) => {
    const ownerId = String(item?.raw?.owner_id || "");
    const visibility = String(item?.visibility || item?.raw?.visibility || "").toLowerCase();
    if (ownerId === "system") return false;
    return visibility === "public";
  })
);

const publicMetrics = computed(() =>
  (communityMetrics.value || []).filter((item) => {
    const ownerId = String(item?.raw?.owner_id || "");
    const visibility = String(item?.visibility || item?.raw?.visibility || "").toLowerCase();
    if (ownerId === "system") return false;
    return visibility === "public" && Boolean(item?.allowDownload);
  })
);

const algorithmTaskOptions = computed(() =>
  [...new Set(publicAlgorithms.value.map((item) => String(item?.task || "")).filter(Boolean))]
);

const algorithmImplOptions = computed(() =>
  [...new Set(publicAlgorithms.value.map((item) => String(item?.impl || "")).filter(Boolean))]
);

const filteredAlgorithms = computed(() => {
  const items = publicAlgorithms.value.filter((item) => {
    if (taskFilter.value && item.task !== taskFilter.value) return false;
    if (implFilter.value && item.impl !== implFilter.value) return false;
    return byKeyword([item.name, item.id, item.task, item.impl, item.version, item.description, item.uploaderId, item.downloadCount]);
  });
  return sortItems(items);
});

const filteredDatasets = computed(() => {
  const items = publicDatasets.value.filter((item) => {
    if (datasetTypeFilter.value && item.type !== datasetTypeFilter.value) return false;
    if (datasetTaskFilter.value) {
      if (!datasetSupportsTaskType(item, datasetTaskFilter.value)) return false;
    }
    return byKeyword([
      item.name,
      item.id,
      item.type,
      formatDatasetTaskTypes(item),
      item.size,
      item.description,
      item.uploaderId,
      item.downloadCount,
    ]);
  });
  return sortItems(items);
});

const filteredMetrics = computed(() => {
  const items = publicMetrics.value.filter((item) => {
    if (metricDirectionFilter.value && item.direction !== metricDirectionFilter.value) return false;
    return byKeyword([
      item.displayName,
      item.name,
      item.id,
      item.metricKey,
      item.direction,
      formatMetricTaskTypes(item.taskTypes),
      item.description,
      item.uploaderId,
      item.downloadCount,
    ]);
  });
  return sortItems(items);
});
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

.toolbar-card {
  background: #f8faff;
  padding: 20px;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 280px;
}

.sort-select,
.filter-select {
  width: 160px;
}

.resource-switch-tabs {
  min-width: 300px;
  margin: 0 8px;
}

:deep(.resource-switch-tabs .el-tabs__header) {
  margin: 0;
}

:deep(.resource-switch-tabs .el-tabs__nav-wrap::after) {
  display: none;
}

:deep(.resource-switch-tabs .el-tabs__item) {
  height: 40px;
  line-height: 40px;
  font-size: 14px;
}

:deep(.resource-switch-tabs .el-tabs__content) {
  display: none;
}

.section {
  margin-bottom: 24px;
}

.data-table {
  width: 100%;
}

.detail-panel {
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

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.block-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2f57;
}

.description-box {
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8fbff;
  border: 1px solid #dce7ff;
  line-height: 1.8;
  color: #334466;
  white-space: pre-wrap;
}

.package-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.package-detail-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #dce7ff;
}

.package-detail-card-wide {
  grid-column: 1 / -1;
}

.package-detail-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #2f6df6;
}

.package-detail-text {
  color: #334466;
  line-height: 1.8;
  white-space: pre-wrap;
}

.package-archive-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #1f2f57;
  font-weight: 700;
}

.archive-digest {
  color: #7b89a8;
  font-size: 12px;
  font-weight: 500;
}

.package-note {
  margin-top: 8px;
  color: #7b89a8;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .package-detail-grid {
    grid-template-columns: 1fr;
  }
}

.comment-list {
  display: grid;
  gap: 12px;
  min-height: 48px;
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

.comment-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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

.comment-editor {
  display: grid;
  gap: 10px;
}

.comment-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
