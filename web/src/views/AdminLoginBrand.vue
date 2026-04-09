<template>
  <div class="login-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
    </div>

    <el-card class="login-card" shadow="always">
      <div class="header">
        <div class="logo">A</div>
        <h2>&#31649;&#29702;&#21592;&#30331;&#24405;</h2>
        <p>&#20351;&#29992;&#31649;&#29702;&#21592;&#36134;&#21495;&#30331;&#24405;&#65292;&#36827;&#20837;&#24179;&#21488;&#31649;&#29702;&#20837;&#21475;</p>
      </div>

      <el-form :model="form" label-position="top" @keyup.enter="handleLogin" size="large">
        <el-form-item label="&#36134;&#21495;">
          <el-input v-model="form.username" placeholder="&#35831;&#36755;&#20837;&#31649;&#29702;&#21592;&#36134;&#21495;" prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="&#23494;&#30721;">
          <el-input v-model="form.password" type="password" placeholder="&#35831;&#36755;&#20837;&#31649;&#29702;&#21592;&#23494;&#30721;" prefix-icon="Lock" show-password />
        </el-form-item>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleLogin" class="submit-btn">
            &#30331;&#24405;&#31649;&#29702;&#21592;
          </el-button>

          <div class="links">
            <router-link to="/login" class="back-link">&#36820;&#22238;&#26222;&#36890;&#29992;&#25143;&#30331;&#24405;</router-link>
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
  username: "admin",
  password: "Admin@123456",
});

async function handleLogin() {
  if (!form.username.trim() || !form.password.trim()) {
    return ElMessage.warning("\u8bf7\u8f93\u5165\u7ba1\u7406\u5458\u8d26\u53f7\u548c\u5bc6\u7801");
  }

  loading.value = true;
  try {
    await store.loginAdmin(form.username, form.password);
    ElMessage.success("\u7ba1\u7406\u5458\u767b\u5f55\u6210\u529f");
    router.push("/");
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || "\u7ba1\u7406\u5458\u767b\u5f55\u5931\u8d25");
  } finally {
    loading.value = false;
  }
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
  background: #1f2f57;
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

.links {
  margin-top: 20px;
  text-align: center;
}

.back-link {
  color: #409eff;
  text-decoration: none;
}
</style>
