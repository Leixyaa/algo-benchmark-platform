<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="border-right: 1px solid #eee">
      <div style="padding: 16px; font-weight: 700">算法评测平台</div>

      <el-menu
        :default-active="active"
        router
        style="border-right: none"
      >
        <el-menu-item index="/datasets">数据集管理</el-menu-item>
        <el-menu-item index="/algorithms">算法库</el-menu-item>
        <el-menu-item index="/new-run">发起评测</el-menu-item>
        <el-menu-item index="/runs">任务中心</el-menu-item>
        <el-menu-item index="/compare">结果对比</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="border-bottom: 1px solid #eee; display:flex; align-items:center;">
        <div style="font-weight: 600">{{ title }}</div>
      </el-header>

      <el-main style="background: #fafafa">
        <div style="background:#fff; padding:16px; border:1px solid #eee; border-radius:8px;">
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
