<template>
  <div class="login-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
    </div>
    
    <el-card class="login-card" shadow="always">
      <div class="header">
        <div class="logo">◈</div>
        <h2>算法评测平台</h2>
        <p>算法工程化主仓 · 统一评测体系</p>
      </div>
      
      <el-form :model="form" label-position="top" @keyup.enter="handleLogin" size="large">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" show-password />
        </el-form-item>
        
        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleLogin" class="submit-btn">立即登录</el-button>
          
          <div class="divider">
            <span>或其他方式</span>
          </div>
          
          <div class="links">
            <router-link to="/register" class="reg-link">没有账号？注册新用户</router-link>
            <el-button type="text" @click="continueAsGuest" class="guest-btn">以游客身份访问</el-button>
          </div>
        </div>
      </el-form>
    </el-card>
    
    <div class="footer-info">
      &copy; 2026 Algo Benchmark Platform · Graduation Project
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import { ElMessage } from "element-plus";

const router = useRouter();
const store = useAppStore();
const loading = ref(false);

const form = reactive({
  username: "",
  password: "",
});

async function handleLogin() {
  if (!form.username.trim() || !form.password.trim()) {
    return ElMessage.warning("请输入用户名和密码");
  }
  
  loading.value = true;
  try {
    await store.login(form.username, form.password);
    ElMessage.success("登录成功");
    router.push("/");
  } catch (e) {
    ElMessage.error(e?.detail || e || "登录失败");
  } finally {
    loading.value = false;
  }
}

function continueAsGuest() {
  store.logout();
  router.push("/");
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f7fb;
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
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

.login-card {
  width: 440px;
  padding: 30px 20px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  z-index: 1;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06) !important;
}

.header {
  text-align: center;
  margin-bottom: 40px;
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
  box-shadow: none;
}

.header h2 {
  margin: 0;
  font-size: 26px;
  color: #1f2f57;
  font-weight: 700;
  letter-spacing: 1px;
}

.header p {
  margin-top: 10px;
  color: #6a7ca9;
  font-size: 14px;
}

.actions {
  margin-top: 30px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
  background: #2f6bff;
  border: none;
  transition: none;
}

.submit-btn:hover {
  transform: none;
  box-shadow: none;
}

.divider {
  margin: 25px 0;
  text-align: center;
  position: relative;
}

.divider::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 1px;
  background: #ebeef5;
}

.divider span {
  position: relative;
  padding: 0 15px;
  background: white;
  color: #909399;
  font-size: 12px;
}

.links {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.reg-link {
  color: #409eff;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}

.reg-link:hover {
  text-decoration: underline;
}

.guest-btn {
  font-size: 14px;
  color: #606266;
}

.footer-info {
  margin-top: 30px;
  color: #909399;
  font-size: 12px;
  z-index: 1;
}
</style>
