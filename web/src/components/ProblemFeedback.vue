<template>
  <div class="problem-feedback">
    <el-button class="feedback-trigger" plain @click="open">问题反馈</el-button>

    <el-dialog v-model="visible" title="问题反馈" width="520px" destroy-on-close @closed="reset">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="类型">
          <el-select v-model="form.category" style="width: 100%">
            <el-option label="功能异常 / Bug" value="bug" />
            <el-option label="功能建议" value="suggestion" />
            <el-option label="界面与体验" value="ux" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述（至少 3 字）">
          <el-input
            v-model="form.message"
            type="textarea"
            :rows="6"
            maxlength="4000"
            show-word-limit
            placeholder="请描述复现步骤、期望行为或建议，便于我们跟进。"
          />
        </el-form-item>
        <el-form-item label="联系方式（选填）">
          <el-input v-model="form.contact" maxlength="200" placeholder="邮箱 / 手机等，便于回访" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { feedbackApi } from "../api/feedback";

const visible = ref(false);
const submitting = ref(false);
const form = reactive({
  category: "other",
  message: "",
  contact: "",
});

function reset() {
  form.category = "other";
  form.message = "";
  form.contact = "";
}

function open() {
  visible.value = true;
}

async function submit() {
  const msg = String(form.message || "").trim();
  if (msg.length < 3) {
    ElMessage.warning("请至少输入 3 个字的描述");
    return;
  }
  submitting.value = true;
  try {
    await feedbackApi.submit({
      message: msg,
      category: form.category,
      contact: String(form.contact || "").trim(),
    });
    ElMessage.success("感谢反馈，我们已收到");
    visible.value = false;
    reset();
  } catch (e) {
    ElMessage.error("提交失败：" + String((e && e.message) || e));
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.problem-feedback {
  display: inline-flex;
}

.feedback-trigger {
  border-color: #d6e3ff;
  color: #35518c;
}
</style>
