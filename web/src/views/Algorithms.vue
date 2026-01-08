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
          <th align="left" width="140">操作</th>
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
        </div>

        <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:12px;">
          <button @click="closeCreate" style="padding:6px 10px;">取消</button>
          <button @click="submitCreate" style="padding:6px 10px;">确认新增</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useAppStore } from "../stores/app";

const store = useAppStore();

const showCreate = ref(false);
const form = reactive({
  task: "去噪",
  name: "",
  impl: "PyTorch",
  version: "v1",
});

function openCreate() {
  form.task = "去噪";
  form.name = "";
  form.impl = "PyTorch";
  form.version = "v1";
  showCreate.value = true;
}
function closeCreate() {
  showCreate.value = false;
}

function submitCreate() {
  if (!form.name.trim()) {
    alert("请填写算法名称");
    return;
  }
  // 这里先直接调用 store 的 addAlgorithm（你 app.js 里已有）
  store.addAlgorithm({
    id: `alg_${Date.now()}`,
    task: form.task,
    name: form.name.trim(),
    impl: form.impl,
    version: form.version.trim() || "v1",
  });
  showCreate.value = false;
}

function remove(id) {
  const ok = confirm("确定删除该算法条目吗？");
  if (!ok) return;
  store.removeAlgorithm(id);
}

function seedDemo() {
  store.addAlgorithm({ id: `alg_${Date.now()}_1`, task: "去雾", name: "Dark Channel Prior(示例)", impl: "OpenCV", version: "2009" });
  store.addAlgorithm({ id: `alg_${Date.now()}_2`, task: "低照度增强", name: "RetinexNet(示例)", impl: "PyTorch", version: "2018" });
}
</script>
