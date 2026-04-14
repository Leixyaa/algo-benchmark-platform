<template>
  <div class="profile-page">
    <div class="header-section profile-head">
      <h2 class="title">个人信息</h2>
      <p class="subtitle">维护显示名称、账号信息与登录密码。</p>
    </div>

    <div class="action-bar profile-action-bar">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="profile-badge">账号设置</div>
        </div>
        <div class="toolbar-right">
          <el-button class="refresh-btn" @click="loadProfile" :loading="loadingProfile">刷新信息</el-button>
        </div>
      </div>
    </div>

    <el-card shadow="never" class="main-card">
      <div v-if="!store.user.isLoggedIn" class="empty-card">请先登录后查看个人信息。</div>
      <template v-else>
        <div class="profile-grid">
          <div class="info-card">
            <div class="card-head">
              <div class="avatar-chip">{{ displayInitial(profile.display_name || profile.username) }}</div>
              <div>
                <div class="card-title">账号概览</div>
                <div class="card-sub">显示信息用于界面展示，不影响登录凭据</div>
              </div>
            </div>
            <div class="kv-list">
              <div class="kv-row"><span class="kv-label">显示名称</span><span class="kv-value">{{ profile.display_name || profile.username || "-" }}</span></div>
              <div class="kv-row"><span class="kv-label">用户名</span><span class="kv-value mono">{{ profile.username || "-" }}</span></div>
              <div class="kv-row"><span class="kv-label">角色</span><span class="kv-value">{{ roleLabel(profile.role) }}</span></div>
              <div class="kv-row"><span class="kv-label">注册时间</span><span class="kv-value">{{ formatTime(profile.created_at) }}</span></div>
            </div>
            <div class="profile-hint">提示：显示名称仅影响界面展示，不会修改登录用户名。</div>
          </div>

          <div class="pwd-card">
            <div class="card-title">资料设置</div>
            <el-form :model="profileForm" label-width="96px" class="profile-form">
              <el-form-item label="显示名称">
                <el-input v-model="profileForm.displayName" maxlength="32" show-word-limit placeholder="例如：张同学" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" class="primary-btn" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
              </el-form-item>
            </el-form>

            <div class="card-title">修改密码</div>
            <el-form :model="pwdForm" label-width="96px">
              <el-form-item label="旧密码">
                <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入旧密码" />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="至少 6 位" />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" class="primary-btn" :loading="savingPassword" @click="changePassword">保存新密码</el-button>
                <el-button @click="resetPwdForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script>
export default { name: "Profile" };
</script>
<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import http from "../api/http";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const loadingProfile = ref(false);
const savingProfile = ref(false);
const savingPassword = ref(false);
const profile = reactive({ username: "", display_name: "", role: "user", created_at: 0 });
const profileForm = reactive({ displayName: "" });
const pwdForm = reactive({ oldPassword: "", newPassword: "", confirmPassword: "" });

function roleLabel(role) {
  return String(role || "").toLowerCase() === "admin" ? "管理员" : "普通用户";
}

function displayInitial(name) {
  const text = String(name || "").trim();
  return text ? text.slice(0, 1).toUpperCase() : "U";
}

function formatTime(ts) {
  const value = Number(ts || 0);
  if (!value) return "-";
  const d = new Date(value * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function resetPwdForm() {
  pwdForm.oldPassword = "";
  pwdForm.newPassword = "";
  pwdForm.confirmPassword = "";
}

function humanizePasswordError(error) {
  const msg = String(error?.detail?.error_message || error?.data?.detail?.error_message || "");
  if (msg === "old_password_incorrect") return "旧密码不正确。";
  if (msg === "new_password_too_short") return "新密码长度至少 6 位。";
  if (msg === "new_password_same_as_old") return "新密码不能与旧密码相同。";
  return "修改密码失败，请稍后重试。";
}

function humanizeProfileError(error) {
  const msg = String(error?.detail?.error_message || error?.data?.detail?.error_message || "");
  if (msg === "display_name_required") return "显示名称不能为空。";
  if (msg === "display_name_too_long") return "显示名称最多 32 个字符。";
  return "保存资料失败，请稍后重试。";
}

async function loadProfile() {
  if (!store.user.isLoggedIn) return;
  loadingProfile.value = true;
  try {
    const out = await http.get("/me");
    profile.username = String(out?.username || "");
    profile.display_name = String(out?.display_name || out?.username || "");
    profile.role = String(out?.role || "user");
    profile.created_at = Number(out?.created_at || 0);
    profileForm.displayName = profile.display_name;
    store.setDisplayName(profile.display_name || profile.username);
  } catch (e) {
    ElMessage.error("加载个人信息失败，请稍后重试。");
  } finally {
    loadingProfile.value = false;
  }
}

async function saveProfile() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后再操作。");
    return;
  }
  const displayName = String(profileForm.displayName || "").trim();
  if (!displayName) {
    ElMessage.warning("显示名称不能为空。");
    return;
  }
  savingProfile.value = true;
  try {
    const out = await http.patch("/me/profile", { display_name: displayName });
    profile.display_name = String(out?.display_name || displayName);
    profileForm.displayName = profile.display_name;
    store.setDisplayName(profile.display_name || profile.username);
    ElMessage.success("资料已更新。");
  } catch (e) {
    ElMessage.error(humanizeProfileError(e));
  } finally {
    savingProfile.value = false;
  }
}

async function changePassword() {
  if (!store.user.isLoggedIn) {
    ElMessage.warning("请先登录后再操作。");
    return;
  }
  const oldPassword = String(pwdForm.oldPassword || "");
  const newPassword = String(pwdForm.newPassword || "");
  const confirmPassword = String(pwdForm.confirmPassword || "");
  if (!oldPassword || !newPassword || !confirmPassword) {
    ElMessage.warning("请完整填写密码信息。");
    return;
  }
  if (newPassword !== confirmPassword) {
    ElMessage.warning("两次输入的新密码不一致。");
    return;
  }
  savingPassword.value = true;
  try {
    await http.post("/me/password", { old_password: oldPassword, new_password: newPassword });
    ElMessage.success("密码修改成功，请使用新密码重新登录。");
    store.logout();
    resetPwdForm();
  } catch (e) {
    ElMessage.error(humanizePasswordError(e));
  } finally {
    savingPassword.value = false;
  }
}

onMounted(loadProfile);
</script>

<style scoped>
.profile-page { display: flex; flex-direction: column; gap: 16px; padding: 6px 2px; }
.title { margin: 0; font-size: 28px; color: #1f2f57; font-weight: 700; line-height: 1.2; }
.subtitle { margin: 8px 0 0; color: #6c7ea8; font-size: 14px; }
.action-bar { border: 1px solid #e3ebfb; border-radius: 16px; background: linear-gradient(135deg, #f8fbff 0%, #f1f6ff 100%); padding: 12px 14px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.profile-badge { padding: 6px 12px; border-radius: 999px; font-size: 12px; color: #385081; background: #eaf1ff; border: 1px solid #d6e4ff; }
.refresh-btn { border-color: #d7e2ff; color: #35518c; }
.main-card { border-radius: 18px; border: 1px solid #e3ebfb; background: #fcfdff; }
.empty-card { padding: 42px 16px; text-align: center; color: #7183ac; }
.profile-grid { display: grid; grid-template-columns: 1fr 1.25fr; gap: 18px; }
.info-card,.pwd-card { border: 1px solid #e8efff; border-radius: 14px; padding: 18px; background: #fff; box-shadow: 0 10px 24px rgba(38, 64, 122, 0.05); }
.card-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.avatar-chip { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #3a6dff 0%, #6f95ff 100%); color: #fff; font-size: 18px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.card-title { font-size: 16px; font-weight: 700; color: #1f2f57; margin-bottom: 12px; }
.card-sub { color: #7a8caf; font-size: 12px; }
.kv-list { display: flex; flex-direction: column; gap: 12px; margin-top: 8px; }
.kv-row { display: flex; justify-content: space-between; gap: 16px; padding-bottom: 8px; border-bottom: 1px dashed #edf2ff; }
.kv-label { color: #6d7fa8; }
.kv-value { color: #2b3f6f; font-weight: 600; text-align: right; }
.profile-hint { margin-top: 12px; font-size: 12px; color: #8294bc; }
.profile-form { margin-bottom: 18px; padding-bottom: 6px; border-bottom: 1px solid #eef3ff; }
.primary-btn { min-width: 104px; }
.mono { font-family: Consolas, "Courier New", monospace; }
@media (max-width: 900px) {
  .profile-grid { grid-template-columns: 1fr; }
  .kv-value { text-align: left; }
}
</style>
