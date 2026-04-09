<template>
  <el-container class="shell">
    <el-aside width="236px" class="sidebar">
      <div class="brand">
        <div class="brandIcon">V</div>
        <div>
          <div class="brandTitle">图像复原增强算法评测平台</div>
          <div class="brandSub">Image Restoration Benchmark Studio</div>
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
          <div class="topSub">聚焦图像复原与增强任务，支持评测、对比与导出</div>
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
import { ElMessage } from "element-plus";

import { useAppStore } from "../stores/app";

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
  return map[route.path] ?? "图像复原增强算法评测平台";
});

async function handleLogout() {
  store.logout();
  ElMessage.success("已退出登录");
  router.push("/login");
}

watch(
  () => store.user.isLoggedIn,
  async () => {
    await Promise.all([store.fetchDatasets(), store.fetchAlgorithms()]);
  }
);

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
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 14px 14px;
}

.brandIcon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #2f6bff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 22px;
}

.brandTitle {
  color: #1f2f57;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
}

.brandSub {
  color: #7b8db5;
  font-size: 12px;
  margin-top: 4px;
}

.menu {
  border-right: none;
}

.mainWrap {
  background: #f5f7fb;
}

.topbar {
  height: 72px;
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
  gap: 4px;
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
  min-height: calc(100vh - 108px);
  background: #ffffff;
  border: 1px solid #e3ebfb;
  border-radius: 18px;
  padding: 18px;
}
</style>
