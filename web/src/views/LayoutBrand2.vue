<template>
  <el-container class="shell">
    <el-aside width="280px" class="sidebar">
      <div class="brand">
        <div class="brandIcon">V</div>
        <div class="brandText">
          <div class="brandTitle">图像增强与复原算法评测平台</div>
          <div class="brandSub">Image Benchmark Studio</div>
        </div>
      </div>

      <el-menu :default-active="active" router class="menu">
        <el-menu-item index="/community">社区中心</el-menu-item>
        <el-menu-item index="/datasets">数据集管理</el-menu-item>
        <el-menu-item index="/algorithms">算法库</el-menu-item>
        <el-menu-item index="/metrics">指标库</el-menu-item>
        <el-menu-item index="/new-run">发起评测</el-menu-item>
        <el-menu-item index="/runs">任务中心</el-menu-item>
        <el-menu-item index="/compare">结果对比</el-menu-item>
        <el-menu-item index="/notices">
          我的通知
          <el-badge
            v-if="store.user.isLoggedIn && unreadCount > 0"
            :value="unreadCount"
            :max="99"
            class="menu-badge"
          />
        </el-menu-item>
        <el-menu-item v-if="store.user.role === 'admin'" index="/admin">管理后台</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="mainWrap">
      <el-header class="topbar">
        <div class="headerLeft">
          <div class="topTitle">{{ title }}</div>
          <div class="topSub">聚焦图像增强与复原任务，支持评测、对比、推荐与导出</div>
        </div>

        <div class="headerRight">
          <el-button
            v-if="store.user.isLoggedIn"
            class="notice-button"
            plain
            @click="router.push('/notices')"
          >
            我的通知
            <el-badge v-if="unreadCount > 0" :value="unreadCount" :max="99" class="header-badge" />
          </el-button>

          <el-dropdown v-if="store.user.isLoggedIn">
            <span class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <span class="username">{{ store.user.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <div v-else class="guest-actions">
            <el-button type="primary" size="small" @click="router.push('/login')">登录</el-button>
            <el-button size="small" plain @click="router.push('/register')">注册</el-button>
          </div>
        </div>
      </el-header>

      <el-main class="main">
        <div class="contentCard">
          <router-view v-slot="{ Component }">
            <keep-alive :include="layoutCachedPageNames">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElNotification } from "element-plus";

import { useAppStore } from "../stores/app";

const route = useRoute();
const router = useRouter();
const store = useAppStore();
const notifiedIds = new Set();

/** 缓存主区页面实例，避免每次切换路由都销毁重建、重复打全量接口 */
const layoutCachedPageNames = [
  "Community",
  "Datasets",
  "Algorithms",
  "Metrics",
  "NewRun",
  "Compare",
  "Runs",
  "Notices",
  "Admin",
];

const active = computed(() => route.path);
const unreadCount = computed(() => (Array.isArray(store.notices) ? store.notices.length : 0));

const title = computed(() => {
  const map = {
    "/community": "社区中心",
    "/datasets": "数据集管理",
    "/algorithms": "算法库",
    "/metrics": "指标库",
    "/new-run": "发起评测",
    "/runs": "任务中心",
    "/compare": "结果对比",
    "/notices": "我的通知",
    "/admin": "管理后台",
  };
  return map[route.path] ?? "图像增强与复原算法评测平台";
});

function noticeType(kind) {
  const value = String(kind || "").toLowerCase();
  if (value === "warning") return "warning";
  if (value === "success") return "success";
  return "info";
}

async function handleLogout() {
  store.logout();
  notifiedIds.clear();
  ElMessage.success("已退出登录");
  router.push("/login");
}

async function syncShellData() {
  try {
    await Promise.all([store.fetchDatasets(), store.fetchAlgorithms(), store.fetchMetrics()]);
  } catch {
    // ignore
  }
  if (!store.user.isLoggedIn) return;
  try {
    const notices = await store.fetchUnreadNotices();
    for (const notice of notices || []) {
      const noticeId = String(notice?.notice_id || "");
      if (!noticeId || notifiedIds.has(noticeId)) continue;
      notifiedIds.add(noticeId);
      ElNotification({
        title: notice?.title || "系统通知",
        message: notice?.content || "",
        type: noticeType(notice?.kind),
        duration: 5000,
      });
    }
  } catch {
    // ignore
  }
}

async function handleWindowFocus() {
  await syncShellData();
}

watch(
  () => store.user.isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn) notifiedIds.clear();
    await syncShellData();
  }
);

onMounted(async () => {
  window.addEventListener("focus", handleWindowFocus);
  await syncShellData();
});

onBeforeUnmount(() => {
  window.removeEventListener("focus", handleWindowFocus);
});
</script>

<style scoped>
.shell {
  height: 100vh;
  background: transparent;
}

.sidebar {
  border-right: 1px solid #dbe6ff;
  background: #ffffff;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 18px 18px;
  text-align: center;
}

.brandIcon {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  background: #2f6bff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 30px;
}

.brandText {
  width: 100%;
}

.brandTitle {
  color: #1f2f57;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brandSub {
  margin-top: 4px;
  color: #7b8db5;
  font-size: 12px;
  line-height: 1.3;
}

.menu {
  border-right: none;
  padding: 8px 10px 0;
}

.menu-badge {
  margin-left: 10px;
}

.mainWrap {
  background: #f5f7fb;
}

.topbar {
  height: 78px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.88);
  border-bottom: 1px solid #dbe6ff;
}

.headerLeft {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.topTitle {
  color: #1f2f57;
  font-size: 22px;
  font-weight: 700;
}

.topSub {
  color: #7586aa;
  font-size: 13px;
}

.headerRight {
  display: flex;
  align-items: center;
  gap: 12px;
}

.notice-button {
  position: relative;
  border-color: #d6e3ff;
  color: #35518c;
}

.header-badge {
  margin-left: 10px;
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.username {
  color: #31456f;
  font-weight: 600;
}

.guest-actions {
  display: flex;
  gap: 10px;
}

.main {
  padding: 18px;
}

.contentCard {
  min-height: calc(100vh - 114px);
  background: #ffffff;
  border: 1px solid #e3ebfb;
  border-radius: 18px;
  padding: 18px;
}
</style>
