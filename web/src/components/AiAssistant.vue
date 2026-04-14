<template>
  <div class="ai-assistant">
    <el-button class="assistant-trigger" type="primary" @click="toggleOpen">
      <span class="trigger-dot"></span>
      AI 客服
    </el-button>

    <transition name="fade-up">
      <div v-if="open" class="assistant-panel">
        <div class="panel-head">
          <div class="head-title">AI 客服</div>
          <el-button text @click="open = false">关闭</el-button>
        </div>
        <div class="head-sub">{{ serviceStatusText }}</div>
        <div v-if="isAdmin" class="source-toggle">
          <el-switch v-model="showSources" />
          <span>显示参考文档来源（仅管理员可见）</span>
        </div>

        <div ref="messagesRef" class="messages">
          <div v-for="item in messages" :key="item.id" class="msg-row" :class="`msg-row--${item.role}`">
            <div class="msg-bubble-wrap">
              <div class="msg-bubble">{{ item.content }}</div>
              <div v-if="isAdmin && showSources && item.role === 'assistant' && item.sources?.length" class="msg-sources">
                参考文档：{{ item.sources.join("、") }}
              </div>
            </div>
          </div>
          <div v-if="loading" class="msg-row msg-row--assistant">
            <div class="msg-bubble-wrap">
              <div class="msg-bubble">正在思考中...</div>
            </div>
          </div>
        </div>

        <div class="quick-actions">
          <el-button size="small" plain @click="askQuick('怎么发起评测？')">怎么发起评测</el-button>
          <el-button size="small" plain @click="askQuick('算法接入需要哪些步骤？')">算法接入步骤</el-button>
          <el-button size="small" plain @click="askQuick('任务状态一直排队怎么办？')">排队问题排查</el-button>
        </div>

        <div class="composer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="输入你的问题..."
            @keydown.enter.exact.prevent="send"
          />
          <el-button type="primary" :loading="loading" @click="send">发送</el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import { ElMessage } from "element-plus";
import { aiApi } from "../api/ai";

const props = defineProps({
  routePath: { type: String, default: "" },
  pageTitle: { type: String, default: "" },
  isLoggedIn: { type: Boolean, default: false },
  userRole: { type: String, default: "user" },
});

const open = ref(false);
const loading = ref(false);
const input = ref("");
const messagesRef = ref(null);
const messages = ref([
  {
    id: `assistant-${Date.now()}`,
    role: "assistant",
    content: "你好，我是平台 AI 客服。你可以问我评测流程、算法接入、任务状态等问题。",
  },
]);

const serviceStatusText = computed(() => {
  if (loading.value) return "AI 助手正在回复...";
  return "AI 助手在线";
});
const isAdmin = computed(() => String(props.userRole || "").toLowerCase() === "admin");
const showSources = ref(false);

function toggleOpen() {
  if (!props.isLoggedIn) return;
  open.value = !open.value;
  if (open.value) scrollToBottom();
}

function buildHistory() {
  return messages.value
    .filter((item) => item.role === "user" || item.role === "assistant")
    .slice(-10)
    .map((item) => ({ role: item.role, content: item.content }));
}

function appendMessage(role, content) {
  messages.value.push({
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
    role,
    content: String(content || "").trim(),
    sources: [],
  });
}

function appendAssistantMessage(content, sources = []) {
  messages.value.push({
    id: `assistant-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
    role: "assistant",
    content: String(content || "").trim(),
    sources: Array.isArray(sources) ? sources.slice(0, 3).map((x) => String(x || "").trim()).filter(Boolean) : [],
  });
}

function humanizeAiError(error) {
  const detail = error?.detail || error?.data?.detail || {};
  const code = String(detail?.error_code || "").trim();
  const message = String(detail?.error_message || "").trim();
  const hint = String(detail?.error_detail?.hint || "").trim();
  if (code === "E_HTTP" && hint.includes("ABP_AI_API_KEY")) {
    return "AI 服务未配置密钥，请联系管理员设置后重试。";
  }
  if (code === "E_HTTP" && hint.includes("ABP_AI_BASE_URL")) {
    return "AI 服务地址未配置，请联系管理员检查后端配置。";
  }
  if (code === "E_HTTP" && hint.includes("ABP_AI_MODEL")) {
    return "AI 模型未配置，请联系管理员检查后端配置。";
  }
  if (message === "ai_service_disabled") {
    return "AI 客服当前已关闭，请稍后再试。";
  }
  if (message === "ai_upstream_http_error") {
    return "AI 服务暂时繁忙，请稍后重试。";
  }
  if (message === "ai_upstream_network_error") {
    return "AI 服务网络连接异常，请稍后重试。";
  }
  if (message === "ai_upstream_invalid_json" || message === "ai_upstream_empty_choices" || message === "ai_upstream_empty_message") {
    return "AI 服务返回异常，请稍后重试。";
  }
  if (message === "message_required" || message === "empty_user_message") {
    return "请输入问题后再发送。";
  }
  if (code === "E_HTTP") {
    return "AI 服务暂时不可用，请稍后再试。";
  }
  if (String(error?.message || "").includes("503")) {
    return "AI 服务繁忙或未配置，请稍后再试。";
  }
  return "AI 服务暂时不可用，请稍后再试。";
}

async function scrollToBottom() {
  await nextTick();
  const el = messagesRef.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function askQuick(text) {
  input.value = text;
  await send();
}

async function send() {
  if (!props.isLoggedIn) {
    ElMessage.warning("请先登录后使用 AI 客服。");
    return;
  }
  const question = String(input.value || "").trim();
  if (!question || loading.value) return;
  input.value = "";
  appendMessage("user", question);
  await scrollToBottom();

  loading.value = true;
  try {
    const out = await aiApi.chat({
      message: question,
      history: buildHistory(),
      include_sources: isAdmin.value && showSources.value,
      context: {
        route_path: props.routePath,
        page_title: props.pageTitle,
        logged_in: props.isLoggedIn,
      },
    });
    const reply = String(out?.reply || "").trim() || "暂时没有返回有效回复，请稍后重试。";
    appendAssistantMessage(reply, out?.sources || []);
  } catch (e) {
    const msg = humanizeAiError(e);
    appendAssistantMessage(msg, []);
    ElMessage.error(msg);
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 2000;
}

.assistant-trigger {
  height: 56px;
  padding: 0 18px;
  border-radius: 999px;
  border: 0;
  background: linear-gradient(135deg, #2f6bff 0%, #5b8dff 100%);
  box-shadow: 0 10px 24px rgba(47, 107, 255, 0.38);
  font-weight: 700;
  letter-spacing: 0.2px;
}

.assistant-trigger:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(47, 107, 255, 0.42);
}

.trigger-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  background: #d7e7ff;
  box-shadow: 0 0 0 3px rgba(215, 231, 255, 0.25);
}

.assistant-panel {
  position: absolute;
  right: 0;
  bottom: 70px;
  width: 480px;
  max-width: calc(100vw - 20px);
  background: #fff;
  border: 1px solid #dbe6ff;
  border-radius: 16px;
  box-shadow: 0 22px 50px rgba(17, 24, 39, 0.2);
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.head-title {
  font-weight: 700;
  color: #1f2f57;
}

.head-sub {
  color: #6a7ca9;
  font-size: 12px;
  margin-bottom: 8px;
}

.source-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5d709c;
  font-size: 12px;
  margin-bottom: 8px;
}

.messages {
  height: 430px;
  overflow: auto;
  padding: 10px 6px;
  background: #f8faff;
  border: 1px solid #ecf2ff;
  border-radius: 12px;
}

.msg-row {
  display: flex;
  margin: 8px 6px;
  min-width: 0;
}

.msg-row--user {
  justify-content: flex-end;
}

.msg-row--assistant {
  justify-content: flex-start;
}

/* 统一由外层控制最大宽度，避免用户气泡在 flex 下被压得过窄（与 overflow-wrap:anywhere 叠加） */
.msg-bubble-wrap {
  max-width: min(92%, 448px);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.msg-bubble {
  max-width: 100%;
  padding: 10px 12px;
  line-height: 1.5;
  border-radius: 12px;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
}

.msg-row--user .msg-bubble {
  background: #2f6bff;
  color: #fff;
  min-width: 56px;
  margin-left: auto;
  border-top-right-radius: 6px;
}

.msg-row--user .msg-bubble-wrap {
  align-items: flex-end;
}

.msg-row--assistant .msg-bubble {
  background: #ffffff;
  border: 1px solid #dbe6ff;
  color: #1f2f57;
  border-top-left-radius: 6px;
}

.msg-sources {
  margin-top: 4px;
  color: #7b8db5;
  font-size: 11px;
  line-height: 1.4;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.composer {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

@media (max-width: 768px) {
  .ai-assistant {
    right: 10px;
    bottom: 10px;
  }

  .assistant-panel {
    width: min(94vw, 480px);
  }

  .messages {
    height: 360px;
  }
}

.fade-up-enter-active,
.fade-up-leave-active {
  transition: all 0.2s ease;
}

.fade-up-enter-from,
.fade-up-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>

