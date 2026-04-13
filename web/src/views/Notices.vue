<template>
  <div class="notices-page">
    <div class="hero">
      <div>
        <div class="hero-title">我的通知</div>
        <div class="hero-subtitle">查看管理员处理结果、审核反馈和系统提醒，并按需标记已读。</div>
      </div>
      <div class="hero-actions">
        <el-tag type="danger" effect="light">未读 {{ unreadCount }}</el-tag>
        <el-button @click="loadNotices" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div v-if="!store.user.isLoggedIn" class="empty-card">
      请先登录后查看通知。
    </div>

    <template v-else>
      <div v-if="!loading && notices.length === 0" class="empty-card">
        当前暂无通知。
      </div>

      <div v-else class="notice-list">
        <div
          v-for="notice in notices"
          :key="notice.notice_id"
          class="notice-card"
          :class="{ 'notice-card--read': notice.read }"
        >
          <div class="notice-top">
            <div class="notice-meta">
              <el-tag size="small" :type="tagType(notice.kind)" effect="light">
                {{ kindLabel(notice.kind) }}
              </el-tag>
              <span class="notice-time">{{ formatTime(notice.created_at) }}</span>
            </div>
            <el-button
              v-if="!notice.read"
              type="primary"
              link
              @click="handleMarkRead(notice.notice_id)"
            >
              标记已读
            </el-button>
            <span v-else class="read-text">已读</span>
          </div>
          <div class="notice-title-row">
            <span v-if="!notice.read" class="unread-dot"></span>
            <div class="notice-title">{{ notice.title || "系统通知" }}</div>
          </div>
          <div class="notice-content">{{ notice.content || "暂无内容" }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
export default { name: "Notices" };
</script>
<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import http from "../api/http";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const loading = ref(false);
const notices = ref([]);

const unreadCount = computed(() => notices.value.filter((item) => !item?.read).length);

function kindLabel(kind) {
  const value = String(kind || "").toLowerCase();
  if (value === "warning") return "提醒";
  if (value === "success") return "成功";
  return "通知";
}

function tagType(kind) {
  const value = String(kind || "").toLowerCase();
  if (value === "warning") return "warning";
  if (value === "success") return "success";
  return "info";
}

function formatTime(ts) {
  const value = Number(ts || 0);
  if (!value) return "-";
  const d = new Date(value * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}:${pad(d.getSeconds())}`;
}

async function loadNotices() {
  if (!store.user.isLoggedIn) {
    notices.value = [];
    return;
  }
  loading.value = true;
  try {
    const items = await http.get("/me/notices", { unread_only: false });
    notices.value = Array.isArray(items) ? items : [];
    store.notices = notices.value.filter((item) => !item?.read);
  } catch (error) {
    ElMessage.error(`加载通知失败：${error?.message || error}`);
  } finally {
    loading.value = false;
  }
}

async function handleMarkRead(noticeId) {
  try {
    await store.markNoticeRead(noticeId);
    notices.value = notices.value.map((item) =>
      String(item?.notice_id || "") === String(noticeId) ? { ...item, read: true } : item
    );
    ElMessage.success("已标记为已读");
  } catch (error) {
    ElMessage.error(`标记已读失败：${error?.message || error}`);
  }
}

onMounted(loadNotices);
</script>

<style scoped>
.notices-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid #e3ebfb;
  border-radius: 18px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef4ff 100%);
}

.hero-title {
  font-size: 24px;
  font-weight: 700;
  color: #1f2f57;
}

.hero-subtitle {
  margin-top: 6px;
  color: #6d7fa8;
  font-size: 14px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.empty-card {
  padding: 48px 20px;
  text-align: center;
  color: #7183ac;
  border: 1px dashed #d6e2ff;
  border-radius: 18px;
  background: #fbfdff;
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.notice-card {
  padding: 18px 20px;
  border: 1px solid #e3ebfb;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(31, 47, 87, 0.05);
}

.notice-card--read {
  background: #fafcff;
  box-shadow: none;
}

.notice-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.notice-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.notice-time {
  color: #7c8cad;
  font-size: 13px;
}

.notice-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}

.unread-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ff6b6b;
  flex: 0 0 auto;
}

.notice-title {
  color: #203057;
  font-size: 18px;
  font-weight: 700;
}

.notice-content {
  margin-top: 10px;
  color: #4c5f88;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
}

.read-text {
  color: #8ea0c6;
  font-size: 13px;
}

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
