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
        <p>创建您的私有算法评测空间</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" @keyup.enter="handleRegister" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="建议使用学号或英文名" prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" prefix-icon="Lock" show-password />
        </el-form-item>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleRegister" class="submit-btn">注册并登录</el-button>

          <div class="divider">
            <span>已有账号？</span>
          </div>

          <div class="links">
            <router-link to="/login" class="login-link">返回登录</router-link>
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
const formRef = ref(null);

const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
});

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
  confirmPassword: [
    { required: true, message: "请再次输入密码", trigger: "blur" },
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error("两次输入的密码不一致"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
};

async function handleRegister() {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid) => {
    if (!valid) return;

    loading.value = true;
    try {
      await store.register(form.username, form.password);
      await store.login(form.username, form.password);
      ElMessage.success("注册成功");
      router.push("/");
    } catch (e) {
      ElMessage.error(e?.detail || e || "注册失败");
    } finally {
      loading.value = false;
    }
  });
}

function continueAsGuest() {
  store.logout();
  router.push("/");
}
</script>

<style scoped>
.register-container {
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

.register-card {
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
  margin-bottom: 30px;
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
  font-weight: 700;
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
  margin-top: 20px;
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

.login-link {
  color: #409eff;
  text-decoration: none;
  font-size: 14px;
}

.guest-btn {
  color: #64748b;
}

.footer-info {
  margin-top: 24px;
  color: #94a3b8;
  font-size: 12px;
  z-index: 1;
}
</style>
