<template>
  <!-- 兼容旧路由：/tasks 以前叫任务中心。
       现在统一用 /runs 作为任务中心页面。
       如果你的 router 里还保留 /tasks，这个页面也能正常展示。 -->
  <Runs />
</template>

<script setup>
import Runs from "./Runs.vue";
</script>
