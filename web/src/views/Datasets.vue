<template>
  <div style="padding: 16px;">
    <h2 style="margin: 0 0 8px;">数据集管理</h2>
    <div style="color:#666; margin-bottom: 12px;">
      管理评测数据集：新增、删除、查看元信息。上传功能后续接后端。
    </div>

    <div style="display:flex; gap:8px; margin-bottom: 12px;">
      <button @click="openCreate" style="padding:6px 10px;">新增数据集</button>
      <button @click="fakeUpload" style="padding:6px 10px;">上传数据集（占位）</button>
    </div>

    <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">
      <thead>
        <tr style="background:#f6f6f6;">
          <th align="left">名称</th>
          <th align="left">类型</th>
          <th align="left">规模</th>
          <th align="left">创建时间</th>
          <th align="left" width="120">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="ds in store.datasets" :key="ds.id">
          <td>{{ ds.name }}</td>
          <td>{{ ds.type }}</td>
          <td>{{ ds.size }}</td>
          <td>{{ ds.createdAt }}</td>
          <td>
            <button @click="remove(ds.id)" style="padding:4px 8px;">删除</button>
          </td>
        </tr>
        <tr v-if="store.datasets.length === 0">
          <td colspan="5" style="color:#888;">暂无数据集</td>
        </tr>
      </tbody>
    </table>

    <!-- 简单弹窗（先不用组件库） -->
    <div v-if="showCreate"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center;">
      <div style="background:#fff; padding:16px; width:420px; border-radius:10px;">
        <h3 style="margin:0 0 12px;">新增数据集</h3>

        <div style="display:flex; flex-direction:column; gap:10px;">
          <label>
            名称：
            <input v-model="form.name" placeholder="例如：RESIDE-Indoor 子集" style="width:100%; padding:6px;" />
          </label>

          <label>
            类型：
            <select v-model="form.type" style="width:100%; padding:6px;">
              <option>图像</option>
              <option>视频</option>
            </select>
          </label>

          <label>
            规模：
            <input v-model="form.size" placeholder="例如：500 张 / 30 段视频" style="width:100%; padding:6px;" />
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
  name: "",
  type: "图像",
  size: "",
});

function openCreate() {
  form.name = "";
  form.type = "图像";
  form.size = "";
  showCreate.value = true;
}

function closeCreate() {
  showCreate.value = false;
}

function submitCreate() {
  if (!form.name.trim()) {
    alert("请填写数据集名称");
    return;
  }
  store.addDataset({
    id: `ds_${Date.now()}`,
    name: form.name.trim(),
    type: form.type,
    size: form.size.trim() || "-",
  });
  showCreate.value = false;
}

function remove(id) {
  const ok = confirm("确定删除该数据集吗？");
  if (!ok) return;
  store.removeDataset(id);
}

function fakeUpload() {
  alert("上传功能后续接后端：这里先做占位，先把平台流程跑通。");
}
</script>
