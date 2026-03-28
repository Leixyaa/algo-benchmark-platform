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
        <div>
          <div class="topTitle">{{ title }}</div>
          <div class="topSub">图像与视频增强 · 评测 · 对比 · 导出</div>
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
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useAppStore } from "../stores/app";

const route = useRoute();
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
  background: linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%);
  box-shadow: 2px 0 16px rgba(33, 89, 201, 0.08);
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
  background: linear-gradient(135deg, #2f6bff 0%, #28c4ff 100%);
  box-shadow: 0 8px 16px rgba(47, 107, 255, 0.3);
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
  background: linear-gradient(90deg, rgba(47, 107, 255, 0.14) 0%, rgba(43, 197, 255, 0.08) 100%);
}

.mainWrap {
  overflow: hidden;
}

.topbar {
  height: 72px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid #dce7ff;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(8px);
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
  padding: 16px;
}

.contentCard {
  height: calc(100vh - 108px);
  overflow: auto;
  border-radius: 14px;
  padding: 16px;
  border: 1px solid #dbe6ff;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 16px 30px rgba(33, 89, 201, 0.08);
}
</style>
