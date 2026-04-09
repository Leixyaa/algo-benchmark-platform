<template>
  <div class="login-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
    </div>

    <el-card class="login-card" shadow="always">
      <div class="header">
        <div class="logo">V</div>
        <h2>&#22270;&#20687;&#22797;&#21407;&#22686;&#24378;&#31639;&#27861;&#35780;&#27979;&#24179;&#21488;</h2>
        <p>&#32858;&#28966;&#22270;&#20687;&#22797;&#21407;&#19982;&#22686;&#24378;&#20219;&#21153;&#65292;&#32479;&#19968;&#35780;&#27979;&#27969;&#31243;</p>
      </div>

      <el-form :model="form" label-position="top" @keyup.enter="handleLogin" size="large">
        <el-form-item label="&#29992;&#25143;&#21517;">
          <el-input v-model="form.username" placeholder="&#35831;&#36755;&#20837;&#29992;&#25143;&#21517;" prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="&#23494;&#30721;">
          <el-input v-model="form.password" type="password" placeholder="&#35831;&#36755;&#20837;&#23494;&#30721;" prefix-icon="Lock" show-password />
        </el-form-item>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleLogin" class="submit-btn">&#31435;&#21363;&#30331;&#24405;</el-button>

          <div class="divider">
            <span>&#25110;&#20351;&#29992;&#20854;&#20182;&#26041;&#24335;</span>
          </div>

          <div class="links">
            <router-link to="/register" class="reg-link">&#27809;&#26377;&#36134;&#21495;&#65311;&#27880;&#20876;&#26032;&#29992;&#25143;</router-link>
            <div class="link-actions">
              <router-link to="/admin-login" class="admin-link">&#31649;&#29702;&#21592;&#30331;&#24405;</router-link>
              <el-button type="text" @click="continueAsGuest" class="guest-btn">&#20197;&#28216;&#23458;&#36523;&#20221;&#35775;&#38382;</el-button>
            </div>
          </div>
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
    ElMessage.error(e?.detail || e?.message || "登录失败");
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

.login-card {
  width: 460px;
  padding: 30px 20px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  z-index: 1;
}

.header {
  text-align: center;
  margin-bottom: 36px;
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

.actions {
  margin-top: 24px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
}

.divider {
  margin: 24px 0;
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
  gap: 12px;
}

.link-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.reg-link {
  color: #409eff;
  text-decoration: none;
}

.admin-link {
  color: #1f2f57;
  text-decoration: none;
}

.guest-btn {
  color: #64748b;
}
</style>
