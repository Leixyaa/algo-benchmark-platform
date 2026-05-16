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
        <template v-for="item in menuItems" :key="item.path">
          <el-menu-item v-if="!item.adminOnly || store.user.role === 'admin'" :index="item.path">
            <span class="menuIcon">{{ item.icon }}</span>
            <span class="menuText">{{ item.label }}</span>
            <span v-if="item.hot" class="menuPill">{{ item.hot }}</span>
          </el-menu-item>
        </template>
      </el-menu>

      <div class="sidebarStatus">
        <div class="statusTop">
          <span class="statusDot"></span>
          <span>平台运行中</span>
        </div>
        <div class="statusText">数据集、算法、指标与任务状态自动同步</div>
      </div>
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

          <ProblemFeedback v-if="store.user.isLoggedIn" />

          <el-dropdown v-if="store.user.isLoggedIn">
            <span class="user-info">
              <el-avatar :size="34" class="user-avatar">{{ userAvatarText }}</el-avatar>
              <span class="username">{{ store.user.displayName || store.user.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/profile')">个人信息</el-dropdown-item>
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
    <AiAssistant
      v-if="store.user.isLoggedIn"
      :route-path="route.path"
      :page-title="title"
      :is-logged-in="store.user.isLoggedIn"
      :user-role="store.user.role"
    />
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElNotification } from "element-plus";

import { useAppStore } from "../stores/app";
import AiAssistant from "../components/AiAssistant.vue";
import ProblemFeedback from "../components/ProblemFeedback.vue";

const route = useRoute();
const router = useRouter();
const store = useAppStore();
const notifiedIds = new Set();

const menuItems = [
  { path: "/community", label: "社区中心", icon: "C" },
  { path: "/datasets", label: "数据集", icon: "D" },
  { path: "/algorithms", label: "算法库", icon: "A" },
  { path: "/metrics", label: "指标库", icon: "M" },
  { path: "/new-run", label: "发起评测", icon: "R" },
  { path: "/runs", label: "任务中心", icon: "T" },
  { path: "/compare", label: "结果对比", icon: "K" },
  { path: "/admin", label: "管理后台", icon: "G", adminOnly: true },
];

/** 缓存主区页面实例，避免每次切换路由都销毁重建、重复打全量接口。
 * 社区中心（Community）不缓存，进入即重新请求列表，避免已下架数据残留。 */
const layoutCachedPageNames = [
  "Datasets",
  "Algorithms",
  "Metrics",
  "NewRun",
  "Compare",
  "Runs",
  "Profile",
  "Notices",
  "Admin",
];

const active = computed(() => route.path);
const unreadCount = computed(() => (Array.isArray(store.notices) ? store.notices.length : 0));
const userAvatarText = computed(() => {
  const raw = String(store.user.displayName || store.user.username || "U").trim();
  const ascii = raw.match(/[A-Za-z0-9]/);
  return (ascii?.[0] || raw.slice(0, 1) || "U").toUpperCase();
});

const title = computed(() => {
  const map = {
    "/community": "社区中心",
    "/datasets": "数据集",
    "/algorithms": "算法库",
    "/metrics": "指标库",
    "/new-run": "发起评测",
    "/runs": "任务中心",
    "/compare": "结果对比",
    "/profile": "个人信息",
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
  position: relative;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(214, 226, 255, 0.85);
  background:
    radial-gradient(circle at 18% 8%, rgba(47, 107, 255, 0.12), transparent 28%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 52%, #f3f7ff 100%);
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.8);
  overflow: hidden;
}

.sidebar::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
  background-image:
    linear-gradient(rgba(47, 107, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(47, 107, 255, 0.035) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.55), transparent 58%);
}

.brand {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 24px 18px 22px;
  text-align: center;
}

.brandIcon {
  width: 64px;
  height: 64px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 30% 24%, rgba(255, 255, 255, 0.4), transparent 26%),
    linear-gradient(135deg, #1d4eff 0%, #4a82ff 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 31px;
  box-shadow: 0 14px 30px rgba(47, 107, 255, 0.28);
}

.brandText {
  width: 100%;
}

.brandTitle {
  color: #1f2f57;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brandSub {
  margin-top: 6px;
  color: #7a8caf;
  font-size: 12.5px;
  line-height: 1.3;
  letter-spacing: 0.2px;
}

.menu {
  position: relative;
  z-index: 1;
  border-right: none;
  flex: 1;
  padding: 10px 14px 0;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  position: relative;
  height: 54px;
  margin: 9px 0;
  padding: 0 14px !important;
  border-radius: 18px;
  color: #243655;
  font-weight: 700;
  letter-spacing: 0.2px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  column-gap: 12px;
  align-items: center;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(239, 246, 255, 0.9);
  color: #2459d6;
  transform: translateX(2px);
}

.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #eef5ff 0%, #e7f0ff 100%);
  color: #1f5eff;
  box-shadow: 0 10px 22px rgba(47, 107, 255, 0.1);
}

.menu :deep(.el-menu-item.is-active)::before {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 8px;
  width: 3px;
  border-radius: 999px;
  background: #2f6bff;
  content: "";
}

.menuIcon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(47, 107, 255, 0.09);
  color: #2f6bff;
  font-size: 12px;
  font-weight: 900;
}

.menu :deep(.el-menu-item.is-active) .menuIcon {
  background: #2f6bff;
  color: #ffffff;
  box-shadow: 0 8px 16px rgba(47, 107, 255, 0.2);
}

.menuText {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menuPill {
  width: 52px;
  padding: 3px 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #e7f0ff;
  color: #2f6bff;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.menu :deep(.el-menu-item:not(.is-active)) .menuPill {
  opacity: 0.62;
}

.menu :deep(.el-menu-item.is-active) .menuPill {
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(47, 107, 255, 0.12);
}

.sidebarStatus {
  position: relative;
  z-index: 1;
  margin: 18px 16px 20px;
  padding: 14px 15px;
  border: 1px solid rgba(196, 212, 244, 0.85);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  box-shadow: 0 10px 26px rgba(51, 84, 140, 0.08);
}

.statusTop {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1f2f57;
  font-size: 13px;
  font-weight: 800;
}

.statusDot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #21c45d;
  box-shadow: 0 0 0 5px rgba(33, 196, 93, 0.13);
}

.statusText {
  margin-top: 8px;
  color: #7586aa;
  font-size: 12px;
  line-height: 1.55;
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

.user-avatar {
  background:
    radial-gradient(circle at 30% 24%, rgba(255, 255, 255, 0.38), transparent 28%),
    linear-gradient(135deg, #2f6bff 0%, #66a3ff 100%);
  box-shadow: 0 8px 18px rgba(47, 107, 255, 0.2);
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
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
