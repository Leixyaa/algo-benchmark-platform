<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">社区中心</h2>
      <div class="subtitle">浏览社区公开的算法和数据集，支持搜索、筛选、排序、查看详情和下载到当前账号。</div>
    </div>

    <div class="toolbar-card">
      <div class="toolbar-row">
        <el-input
          v-model="keyword"
          placeholder="搜索名称 / ID / 任务 / 实现方式"
          clearable
          class="search-input"
        />
        <el-tabs v-model="tab" class="resource-switch-tabs">
          <el-tab-pane label="公开算法" name="algorithms" />
          <el-tab-pane label="公开数据集" name="datasets" />
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

      <div class="toolbar-row" v-else>
        <el-select v-model="datasetTypeFilter" clearable placeholder="全部类型" class="filter-select">
          <el-option label="图像" value="图像" />
          <el-option label="视频" value="视频" />
        </el-select>
      </div>
    </div>

    <div v-if="tab === 'algorithms'" class="section">
      <el-table :data="filteredAlgorithms" border stripe class="data-table">
        <el-table-column prop="name" label="算法名称" min-width="220" />
        <el-table-column prop="task" label="任务" width="140" />
        <el-table-column prop="impl" label="实现方式" width="120" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="uploaderId" label="上传者ID" width="140" />
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

    <div v-else class="section">
      <el-table :data="filteredDatasets" border stripe class="data-table">
        <el-table-column prop="name" label="数据集名称" min-width="220" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="size" label="规模" width="140" />
        <el-table-column prop="uploaderId" label="上传者ID" width="140" />
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

    <el-dialog v-model="detailVisible" :title="detailTitle" width="780px">
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
            <span v-if="detailType === 'algorithm'">实现方式：{{ detailItem.impl || "-" }}</span>
            <span v-if="detailType === 'algorithm'">版本：{{ detailItem.version || "-" }}</span>
            <span v-if="detailType === 'dataset'">类型：{{ detailItem.type || "-" }}</span>
            <span v-if="detailType === 'dataset'">规模：{{ detailItem.size || "-" }}</span>
          </div>
        </div>

        <div class="detail-block">
          <div class="block-head">
            <div class="block-title">详细描述</div>
            <el-button
              size="small"
              plain
              type="danger"
              @click="openReportDialog('resource')"
              :disabled="!store.user.isLoggedIn"
            >
              举报
            </el-button>
          </div>
          <div class="description-box">{{ detailItem.description || "暂无描述" }}</div>
        </div>

        <div class="detail-block">
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

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { datasetsApi } from "../api/datasets";
import { algorithmsApi } from "../api/algorithms";
import { communityApi } from "../api/community";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const communityAlgorithms = ref([]);
const communityDatasets = ref([]);

const tab = ref("algorithms");
const keyword = ref("");
const sortBy = ref("newest");
const taskFilter = ref("");
const implFilter = ref("");
const datasetTypeFilter = ref("");
const downloadingAlgorithmIds = ref(new Set());
const downloadingDatasetIds = ref(new Set());
const locallyDownloadedAlgorithmIds = ref(new Set());
const locallyDownloadedDatasetIds = ref(new Set());
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
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    uploaderId: String(x.owner_id || ""),
    createdAt: formatTs(x.created_at),
    raw: x,
  };
}

function mapDataset(x) {
  return {
    id: x.dataset_id,
    name: x.name,
    type: x.type,
    size: x.size,
    description: x.description || "",
    downloadCount: Number(x.download_count || 0),
    visibility: x.visibility || "private",
    uploaderId: String(x.owner_id || ""),
    createdAt: formatTs(x.created_at),
    raw: x,
  };
}

async function loadCommunity() {
  const [algorithms, datasets] = await Promise.all([
    algorithmsApi.listAlgorithms({ limit: 500, scope: "community" }),
    datasetsApi.listDatasets({ limit: 200, scope: "community" }),
  ]);
  communityAlgorithms.value = (algorithms || []).map(mapAlgorithm);
  communityDatasets.value = (datasets || []).map(mapDataset);
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

function getErrorCode(error) {
  return String(
    error?.detail?.error_code ||
      error?.data?.detail?.error_code ||
      error?.data?.error_code ||
      error?.error_code ||
      ""
  );
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

const detailTitle = computed(() => (detailType.value === "algorithm" ? "算法详情" : "数据集详情"));

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
  await Promise.all([store.fetchAlgorithms(), store.fetchDatasets()]);
  await loadCommunity();
  if (!detailVisible.value || !detailItem.value?.id) return;
  const sourceList = detailType.value === "algorithm" ? communityAlgorithms.value : communityDatasets.value;
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
  await syncCommunityState();
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
    await store.fetchAlgorithms();
    await loadCommunity();
    ElMessage({ type: "success", message: "已下载到数据库中" });
  } catch (e) {
    if (getErrorCode(e) === "E_HTTP" && String(e?.message || "").includes("algorithm_already_downloaded")) {
      await store.fetchAlgorithms();
      await loadCommunity();
      if (findDownloadedAlgorithmCopy(row)) {
        locallyDownloadedAlgorithmIds.value = new Set([...locallyDownloadedAlgorithmIds.value, String(row.id)]);
        ElMessage({ type: "info", message: "该算法已存在于你的算法库中" });
      } else {
        ElMessage({ type: "warning", message: "后端判定该算法已有副本，但当前账号下未找到对应记录，已自动刷新算法库" });
      }
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
    ElMessage({ type: "success", message: "已下载到数据库中" });
  } catch (e) {
    if (getErrorCode(e) === "E_HTTP" && String(e?.message || "").includes("dataset_already_downloaded")) {
      locallyDownloadedDatasetIds.value = new Set([...locallyDownloadedDatasetIds.value, String(row.id)]);
      await store.fetchDatasets();
      await loadCommunity();
      ElMessage({ type: "info", message: "该数据集已下载到你的数据集库中" });
      return;
    }
    ElMessage({ type: "error", message: `下载数据集失败：${e?.message || e}` });
  } finally {
    setLoading(downloadingDatasetIds, row.id, false);
  }
}

onMounted(async () => {
  window.addEventListener("focus", handleWindowFocus);
  await syncCommunityState();
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
    if (ownerId === "system") return true;
    return visibility === "public";
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
    return byKeyword([item.name, item.id, item.type, item.size, item.description, item.uploaderId, item.downloadCount]);
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
  min-width: 220px;
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
