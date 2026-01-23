<template>
  <div style="padding: 16px;">
    <h2 style="margin: 0 0 8px;">算法库</h2>
    <div style="color:#666; margin-bottom: 12px;">
      管理平台内置/接入的算法条目，后续评测时从这里选择算法。
    </div>

    <div style="display:flex; gap:8px; margin-bottom: 12px;">
      <button @click="openCreate" style="padding:6px 10px;">新增算法</button>
      <button @click="seedDemo" style="padding:6px 10px;">一键填充 Demo（占位）</button>
    </div>

    <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">
      <thead>
        <tr style="background:#f6f6f6;">
          <th align="left">任务</th>
          <th align="left">算法名称</th>
          <th align="left">实现方式</th>
          <th align="left">版本</th>
          <th align="left">创建时间</th>
          <th align="left" width="220">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in store.algorithms" :key="a.id">
          <td>{{ a.task }}</td>
          <td>{{ a.name }}</td>
          <td>{{ a.impl }}</td>
          <td>{{ a.version }}</td>
          <td>{{ a.createdAt }}</td>
          <td>
            <button @click="openEdit(a)" style="padding:4px 8px; margin-right:6px;">编辑</button>
            <button @click="remove(a.id)" style="padding:4px 8px;">删除</button>
          </td>
        </tr>
        <tr v-if="store.algorithms.length === 0">
          <td colspan="6" style="color:#888;">暂无算法条目</td>
        </tr>
      </tbody>
    </table>

    <!-- 新增算法弹窗 -->
    <div v-if="showCreate"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center;">
      <div style="background:#fff; padding:16px; width:460px; border-radius:10px;">
        <h3 style="margin:0 0 12px;">新增算法</h3>

        <div style="display:flex; flex-direction:column; gap:10px;">
          <label>
            任务类别：
            <select v-model="form.task" style="width:100%; padding:6px;">
              <option>去噪</option>
              <option>去模糊</option>
              <option>去雾</option>
              <option>超分辨率</option>
              <option>低照度增强</option>
              <option>视频去噪</option>
              <option>视频超分</option>
            </select>
          </label>

          <label>
            算法名称：
            <input v-model="form.name" placeholder="例如：DnCNN / DeblurGAN-v2 / RetinexNet"
              style="width:100%; padding:6px;" />
          </label>

          <label>
            实现方式：
            <select v-model="form.impl" style="width:100%; padding:6px;">
              <option>PyTorch</option>
              <option>TensorFlow</option>
              <option>OpenCV</option>
              <option>脚本调用</option>
            </select>
          </label>

          <label>
            版本：
            <input v-model="form.version" placeholder="例如：v1 / commit id / 论文年份"
              style="width:100%; padding:6px;" />
          </label>

          <label>
            默认参数(JSON)：
            <textarea
              v-model="form.defaultParamsText"
              rows="6"
              style="width:100%; padding:6px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;"
              placeholder='例如：{ "dcp_patch": 15, "dcp_omega": 0.95 }'
            />
          </label>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:12px;">
          <button @click="closeCreate" style="padding:6px 10px;">取消</button>
          <button @click="submitCreate" style="padding:6px 10px;">确认新增</button>
        </div>
      </div>
    </div>

    <!-- 编辑算法弹窗 -->
    <div v-if="showEdit"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center;">
      <div style="background:#fff; padding:16px; width:520px; border-radius:10px;">
        <h3 style="margin:0 0 12px;">编辑算法</h3>

        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="color:#666;">ID：{{ editForm.id }}</div>
          <label>
            任务类别：
            <select v-model="editForm.task" style="width:100%; padding:6px;">
              <option>去噪</option>
              <option>去模糊</option>
              <option>去雾</option>
              <option>超分辨率</option>
              <option>低照度增强</option>
              <option>视频去噪</option>
              <option>视频超分</option>
            </select>
          </label>

          <label>
            算法名称：
            <input v-model="editForm.name" style="width:100%; padding:6px;" />
          </label>

          <label>
            实现方式：
            <select v-model="editForm.impl" style="width:100%; padding:6px;">
              <option>PyTorch</option>
              <option>TensorFlow</option>
              <option>OpenCV</option>
              <option>脚本调用</option>
            </select>
          </label>

          <label>
            版本：
            <input v-model="editForm.version" style="width:100%; padding:6px;" />
          </label>

          <label>
            默认参数(JSON)：
            <textarea
              v-model="editForm.defaultParamsText"
              rows="8"
              style="width:100%; padding:6px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;"
            />
          </label>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:12px;">
          <button @click="closeEdit" style="padding:6px 10px;">取消</button>
          <button @click="submitEdit" style="padding:6px 10px;">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useAppStore } from "../stores/app";

const store = useAppStore();

const showCreate = ref(false);
const showEdit = ref(false);
const form = reactive({
  task: "去噪",
  name: "",
  impl: "PyTorch",
  version: "v1",
  defaultParamsText: "{}",
});

const editForm = reactive({
  id: "",
  task: "去噪",
  name: "",
  impl: "OpenCV",
  version: "v1",
  defaultParamsText: "{}",
});

onMounted(async () => {
  try {
    await store.fetchAlgorithms();
  } catch {
    // ignore
  }
});

function openCreate() {
  form.task = "去噪";
  form.name = "";
  form.impl = "PyTorch";
  form.version = "v1";
  form.defaultParamsText = "{}";
  showCreate.value = true;
}
function closeCreate() {
  showCreate.value = false;
}

function openEdit(a) {
  editForm.id = a?.id || "";
  editForm.task = a?.task || "去噪";
  editForm.name = a?.name || "";
  editForm.impl = a?.impl || "OpenCV";
  editForm.version = a?.version || "v1";
  const obj =
    a?.defaultParams && typeof a.defaultParams === "object" && !Array.isArray(a.defaultParams)
      ? a.defaultParams
      : {};
  editForm.defaultParamsText = JSON.stringify(obj, null, 2);
  showEdit.value = true;
}

function closeEdit() {
  showEdit.value = false;
}

async function submitEdit() {
  if (!editForm.id) return alert("缺少算法 ID");
  if (!editForm.name.trim()) return alert("请填写算法名称");
  let defaultParams = {};
  try {
    const s = String(editForm.defaultParamsText || "").trim();
    defaultParams = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`默认参数不是合法 JSON：${e?.message || e}`);
  }
  if (!defaultParams || typeof defaultParams !== "object" || Array.isArray(defaultParams)) {
    return alert("默认参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }");
  }

  try {
    await store.updateAlgorithm(editForm.id, {
      task: editForm.task,
      name: editForm.name.trim(),
      impl: editForm.impl,
      version: editForm.version.trim() || "v1",
      defaultParams,
    });
    showEdit.value = false;
  } catch (e) {
    alert(`保存失败：${e?.message || e}`);
  }
}

async function submitCreate() {
  if (!form.name.trim()) {
    alert("请填写算法名称");
    return;
  }
  let defaultParams = {};
  try {
    const s = String(form.defaultParamsText || "").trim();
    defaultParams = s ? JSON.parse(s) : {};
  } catch (e) {
    return alert(`默认参数不是合法 JSON：${e?.message || e}`);
  }
  if (!defaultParams || typeof defaultParams !== "object" || Array.isArray(defaultParams)) {
    return alert("默认参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }");
  }
  try {
    await store.createAlgorithm({
      task: form.task,
      name: form.name.trim(),
      impl: form.impl,
      version: form.version.trim() || "v1",
      defaultParams,
    });
    showCreate.value = false;
  } catch (e) {
    alert(`新增失败：${e?.message || e}`);
  }
}

async function remove(id) {
  const ok = confirm("确定删除该算法条目吗？");
  if (!ok) return;
  try {
    await store.removeAlgorithm(id);
  } catch (e) {
    alert(`删除失败：${e?.message || e}`);
  }
}

async function seedDemo() {
  try {
    await store.createAlgorithm({ task: "去雾", name: "Dark Channel Prior(示例)", impl: "OpenCV", version: "2009" });
    await store.createAlgorithm({ task: "低照度增强", name: "RetinexNet(示例)", impl: "PyTorch", version: "2018" });
  } catch (e) {
    alert(`填充失败：${e?.message || e}`);
  }
}
</script>
