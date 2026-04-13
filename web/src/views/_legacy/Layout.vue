<template>
  <el-container class="shell">
    <el-aside width="236px" class="sidebar">
      <div class="brand">
        <div class="brandIcon">V</div>
        <div>
          <div class="brandTitle">图像算法评测平台</div>
          <div class="brandSub">Image Benchmark Studio</div>
        </div>
      </div>

      <el-menu :default-active="active" router class="menu">
        <el-menu-item index="/community">社区中心</el-menu-item>
        <el-menu-item index="/datasets">数据集管理</el-menu-item>
        <el-menu-item index="/algorithms">算法库</el-menu-item>
        <el-menu-item index="/new-run">发起评测</el-menu-item>
        <el-menu-item index="/runs">任务中心</el-menu-item>
        <el-menu-item index="/compare">结果对比</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="mainWrap">
      <el-header class="topbar">
        <div class="headerLeft">
          <div class="topTitle">{{ title }}</div>
          <div class="topSub">图像与视频增强 · 评测 · 对比 · 导出</div>
        </div>

        <div class="headerRight">
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
            <el-button type="primary" size="small" @click="$router.push('/login')">登录</el-button>
            <el-button size="small" plain @click="$router.push('/register')">注册</el-button>
          </div>
        </div>
      </el-header>

      <el-main class="main">
        <div class="contentCard">
          <router-view />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import { ElMessage } from "element-plus";

const route = useRoute();
const router = useRouter();
const store = useAppStore();

const active = computed(() => route.path);

const title = computed(() => {
  const map = {
    "/community": "社区中心",
    "/datasets": "数据集管理",
    "/algorithms": "算法库",
    "/new-run": "发起评测",
    "/runs": "任务中心",
    "/compare": "结果对比",
  };
  return map[route.path] ?? "算法评测平台";
});

async function handleLogout() {
  store.logout();
  ElMessage.success("已退出登录");
  router.push("/login");
}

watch(
  () => store.user.isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn) return;
    await store.warmSessionData();
  }
);

onMounted(async () => {
  try {
    await store.warmSessionData();
  } catch {
    // ignore
  }
});
</script>

<style scoped>
.shell {
  height: 100vh;
  background: transparent;
}

.sidebar {
  border-right: 1px solid #e2e8f0;
  background: #ffffff;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.brandIcon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  font-weight: 800;
  font-size: 18px;
  transition: all 0.2s ease;
}

.brandIcon:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.2);
}

.brandTitle {
  font-size: 18px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.2;
}

.brandSub {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}

.menu {
  border-right: none;
  background: transparent;
  padding-top: 16px;
}

:deep(.el-menu-item) {
  margin: 6px 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  transition: all 0.2s ease;
  padding: 12px 16px;
}

:deep(.el-menu-item:hover) {
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

:deep(.el-menu-item.is-active) {
  color: #2563eb;
  font-weight: 700;
  background: rgba(59, 130, 246, 0.1);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}

.mainWrap {
  overflow: hidden;
}

.topbar {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.headerRight {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: all 0.2s ease;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.user-info:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.username {
  font-size: 14px;
  color: #1e293b;
  font-weight: 600;
}

.topTitle {
  font-size: 20px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.2;
}

.topSub {
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.4;
}

.main {
  padding: 0;
}

.contentCard {
  height: calc(100vh - 72px);
  overflow: auto;
  border-radius: 0;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
}

:deep(.el-button) {
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.2s ease;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-button--primary) {
  background: #3b82f6;
  border-color: #3b82f6;
}

:deep(.el-button--primary:hover) {
  background: #2563eb;
  border-color: #2563eb;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

:deep(.el-button--plain) {
  color: #1e293b;
  background: #f8fafc;
  border-color: #e2e8f0;
}

:deep(.el-button--plain:hover) {
  background: #f1f5f9;
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-avatar) {
  border: 2px solid #e2e8f0;
  transition: all 0.2s ease;
}

.user-info:hover :deep(.el-avatar) {
  border-color: #3b82f6;
}
</style>
