<template>
  <el-container class="shell">
    <el-aside width="236px" class="sidebar">
      <div class="brand">
        <div class="brandIcon">◈</div>
        <div>
          <div class="brandTitle">图像算法评测平台</div>
          <div class="brandSub">Image Benchmark Studio</div>
        </div>
      </div>

      <el-menu :default-active="active" router class="menu">
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

// 监听登录状态变化，重新拉取数据
watch(() => store.user.isLoggedIn, async () => {
  await Promise.all([store.fetchDatasets(), store.fetchAlgorithms()]);
});

onMounted(async () => {
  try {
    await Promise.all([store.fetchDatasets(), store.fetchAlgorithms()]);
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
  border-right: 1px solid #dbe6ff;
  background: #ffffff;
  box-shadow: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 14px 14px;
}

.brandIcon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: #2f6bff;
  box-shadow: none;
}

.brandTitle {
  font-size: 16px;
  font-weight: 700;
  color: #1f2f57;
}

.brandSub {
  font-size: 12px;
  color: #6a7ca9;
}

.menu {
  border-right: none;
  background: transparent;
}

:deep(.el-menu-item) {
  margin: 6px 10px;
  border-radius: 10px;
}

:deep(.el-menu-item.is-active) {
  color: #2153d3;
  font-weight: 700;
  background: rgba(47, 107, 255, 0.1);
}

.mainWrap {
  overflow: hidden;
}

.topbar {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #dce7ff;
  background: #ffffff;
}

.headerRight {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;
}

.user-info:hover {
  background: rgba(0, 0, 0, 0.05);
}

.username {
  font-size: 14px;
  color: #1d3263;
  font-weight: 500;
}

.topTitle {
  font-size: 18px;
  font-weight: 700;
  color: #1d3263;
}

.topSub {
  margin-top: 3px;
  font-size: 12px;
  color: #7083ad;
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
</style>
