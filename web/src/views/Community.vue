<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">社区中心</h2>
      <div class="subtitle">浏览社区公开的算法和数据集，支持搜索、筛选、排序和下载到当前账号。</div>
    </div>

    <div class="toolbar-card">
      <div class="toolbar-row">
        <el-input
          v-model="keyword"
          placeholder="搜索名称 / ID / 任务 / 实现方式"
          clearable
          class="search-input"
        />
        <el-select v-model="tab" class="tab-select">
          <el-option label="公开算法" value="algorithms" />
          <el-option label="公开数据集" value="datasets" />
        </el-select>
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
        <el-table-column prop="createdAt" label="发布时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="downloadAlgorithm(row)"
              :loading="downloadingAlgorithmIds.has(row.id)"
              :disabled="!store.user.isLoggedIn || isOwnedByCurrentUser(row) || isAlgorithmDownloaded(row)"
            >
              {{ isAlgorithmDownloaded(row) ? "已下载" : "下载" }}
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
        <el-table-column prop="createdAt" label="发布时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="downloadDataset(row)"
              :loading="downloadingDatasetIds.has(row.id)"
              :disabled="!store.user.isLoggedIn || isOwnedByCurrentUser(row) || isDatasetDownloaded(row)"
            >
              {{ isDatasetDownloaded(row) ? "已下载" : "下载" }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无符合条件的公开数据集" />
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { datasetsApi } from "../api/datasets";
import { algorithmsApi } from "../api/algorithms";
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

function isAlgorithmDownloaded(row) {
  if (locallyDownloadedAlgorithmIds.value.has(String(row?.id || ""))) return true;
  const currentUser = String(store.user?.username || "");
  return (store.algorithms || []).some((item) => {
    if (String(item?.uploaderId || "") !== currentUser) return false;
    if (String(item?.sourceUploaderId || "") !== String(row?.uploaderId || "")) return false;
    return String(item?.sourceAlgorithmId || "") === String(row?.id || "");
  });
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
      locallyDownloadedAlgorithmIds.value = new Set([...locallyDownloadedAlgorithmIds.value, String(row.id)]);
      await store.fetchAlgorithms();
      await loadCommunity();
      ElMessage({ type: "info", message: "该算法已下载到你的算法库中" });
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
  await Promise.all([store.fetchAlgorithms(), store.fetchDatasets()]);
  await loadCommunity();
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
    return byKeyword([item.name, item.id, item.task, item.impl, item.version, item.uploaderId]);
  });
  return sortItems(items);
});

const filteredDatasets = computed(() => {
  const items = publicDatasets.value.filter((item) => {
    if (datasetTypeFilter.value && item.type !== datasetTypeFilter.value) return false;
    return byKeyword([item.name, item.id, item.type, item.size, item.uploaderId]);
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

.tab-select,
.sort-select,
.filter-select {
  width: 160px;
}

.section {
  margin-bottom: 24px;
}

.data-table {
  width: 100%;
}
</style>
