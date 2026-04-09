<template>
  <div class="register-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
    </div>

    <el-card class="register-card" shadow="always">
      <div class="header">
        <div class="logo">V</div>
        <h2>注册账号</h2>
        <p>创建您的私有图像复原增强算法评测空间</p>
      </div>

      <el-form :model="form" label-position="top" @keyup.enter="handleRegister" size="large">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" show-password />
        </el-form-item>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleRegister" class="submit-btn">注册并登录</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { useAppStore } from "../stores/app";

const router = useRouter();
const store = useAppStore();
const loading = ref(false);

const form = reactive({
  username: "",
  password: "",
});

async function handleRegister() {
  if (!form.username.trim() || !form.password.trim()) {
    return ElMessage.warning("请输入用户名和密码");
  }

  loading.value = true;
  try {
    await store.register(form.username, form.password);
    await store.login(form.username, form.password);
    ElMessage.success("注册成功");
    router.push("/");
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || "注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fb;
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(47, 107, 255, 0.08);
}

.circle-1 {
  width: 400px;
  height: 400px;
  top: -100px;
  right: -100px;
}

.circle-2 {
  width: 300px;
  height: 300px;
  bottom: -50px;
  left: -50px;
}

.register-card {
  width: 460px;
  padding: 30px 20px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  z-index: 1;
}

.header {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  width: 50px;
  height: 50px;
  margin: 0 auto 15px;
  background: #2f6bff;
  color: white;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 15px;
  font-weight: 700;
}

.header h2 {
  margin: 0;
  font-size: 28px;
  color: #1f2f57;
}

.header p {
  margin-top: 10px;
  color: #6a7ca9;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
}
</style>
