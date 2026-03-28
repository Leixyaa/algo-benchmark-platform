<template>
  <div class="page">
    <h2 class="title">数据集管理</h2>
    <div class="subtitle">
      支持手动创建、磁盘快速登记、ZIP 导入与扫描。目录建议包含 gt/ 与输入目录（hazy/noisy/blur/lr/dark）。
    </div>

    <div class="toolbar">
      <button @click="openCreate">新建数据集</button>
      <button @click="quickAddFromDisk">按ID登记磁盘目录</button>
      <button @click="chooseZipForNew">为当前选择导入 ZIP</button>
      <button @click="generateDemoOnBackend" :disabled="generating">
        {{ generating ? "生成中..." : "生成 Demo 数据集" }}
      </button>
    </div>

    <div class="selectorRow">
      <div class="label">当前选择：</div>
      <select v-model="selectedDatasetId" class="selectBox">
        <option value="" disabled>请选择数据集</option>
        <option v-for="d in store.datasets" :key="d.id" :value="d.id">
          {{ d.name }}（{{ d.id }}）
        </option>
      </select>
      <label class="checkboxLabel">
        <input type="checkbox" v-model="overwriteOnImport" />
        ZIP 导入时覆盖同名文件
      </label>
      <button @click="scanSelected">扫描当前数据集</button>
    </div>

    <table class="gridTable" border="1" cellpadding="8" cellspacing="0">
      <thead>
        <tr>
          <th align="left">名称</th>
          <th align="left">类型</th>
          <th align="left">规模</th>
          <th align="left">创建时间</th>
          <th align="left" width="180">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="ds in store.datasets" :key="ds.id">
          <td>{{ ds.name }}</td>
          <td>{{ ds.type }}</td>
          <td>{{ ds.size }}</td>
          <td>{{ ds.createdAt }}</td>
          <td>
            <button class="miniBtn" @click="scanOne(ds.id)">扫描</button>
            <button class="miniBtn" @click="chooseZipFor(ds.id)">导入 ZIP</button>
            <button class="miniBtn dangerBtn" @click="remove(ds.id)">删除</button>
          </td>
        </tr>
        <tr v-if="store.datasets.length === 0">
          <td colspan="5" class="emptyText">暂无数据集，请先创建或导入。</td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate" class="mask">
      <div class="dialog">
        <h3 class="dialogTitle">新建数据集</h3>

        <div class="formCol">
          <label>
            数据集 ID
            <input v-model="form.id" placeholder="如 ds_gopro_deblur_test（可选）" class="inputBox" />
          </label>

          <label>
            数据集名称
            <input v-model="form.name" placeholder="如 RESIDE Indoor 测试集" class="inputBox" />
          </label>

          <label>
            数据类型
            <select v-model="form.type" class="inputBox">
              <option>图像</option>
              <option>视频</option>
            </select>
          </label>

          <label>
            规模描述
            <input v-model="form.size" placeholder="如 500 张 / 30 段视频" class="inputBox" />
          </label>
        </div>

        <div class="dialogFooter">
          <button @click="closeCreate">取消</button>
          <button @click="submitCreate">确认创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useAppStore } from "../stores/app";
import { ElMessage, ElMessageBox } from "element-plus";

const store = useAppStore();

const showCreate = ref(false);
const generating = ref(false);
const selectedDatasetId = ref("");
const overwriteOnImport = ref(false);
const importTargetId = ref("");
const fileInputRef = ref(null);
const form = reactive({
  id: "",
  name: "",
  type: "图像",
  size: "",
});

onMounted(async () => {
  try {
    await store.fetchDatasets();
    if (!selectedDatasetId.value && store.datasets?.length) {
      selectedDatasetId.value = store.datasets[0].id;
    }
  } catch {
    // ignore
  }
});

function openCreate() {
  form.id = "";
  form.name = "";
  form.type = "图像";
  form.size = "";
  showCreate.value = true;
}

function closeCreate() {
  showCreate.value = false;
}

async function submitCreate() {
  if (!form.name.trim()) {
    alert("请填写数据集名称");
    return;
  }
  try {
    const created = await store.createDataset({
      id: form.id.trim() || undefined,
      name: form.name.trim(),
      type: form.type,
      size: form.size.trim() || "-",
    });
    const id = created?.id || form.id.trim();
    if (id) {
      try {
        await store.scanDataset(id);
        await store.fetchDatasets();
        selectedDatasetId.value = id;
      } catch {
        // ignore
      }
    }
    showCreate.value = false;
  } catch (e) {
    alert(`创建数据集失败：${e?.message || e}`);
  }
}

async function quickAddFromDisk() {
  const id = prompt("请输入数据集ID（对应 backend/data/<id> 目录）");
  const datasetId = String(id || "").trim();
  if (!datasetId) return;

  const name = prompt("请输入数据集名称", datasetId);
  const datasetName = String(name || "").trim() || datasetId;

  try {
    await store.createDataset({ id: datasetId, name: datasetName, type: "图像", size: "-" });
    await store.scanDataset(datasetId);
    await store.fetchDatasets();
    selectedDatasetId.value = datasetId;
    ElMessage({ type: "success", message: "数据集创建并扫描完成" });
  } catch (e) {
    ElMessage({ type: "error", message: `快速登记失败：${e?.message || e}` });
  }
}

async function remove(id) {
  const ok = confirm("确认删除该数据集吗？");
  if (!ok) return;
  try {
    await store.removeDataset(id);
  } catch (e) {
    alert(`删除失败：${e?.message || e}`);
  }
}

function _ensureFileInput() {
  if (fileInputRef.value) return;
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".zip,application/zip";
  input.style.display = "none";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const dsId = importTargetId.value;
    if (!dsId) return;

    const ok = confirm(
      `将导入 ZIP 到数据集 ${dsId}，${overwriteOnImport.value ? "会覆盖同名文件" : "不会覆盖同名文件"}，是否继续？`
    );
    if (!ok) return;

    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const fr = new FileReader();
        fr.onload = () => resolve(fr.result);
        fr.onerror = () => reject(new Error("read_file_failed"));
        fr.readAsDataURL(file);
      });
      const s = String(dataUrl || "");
      const idx = s.indexOf(",");
      const b64 = idx >= 0 ? s.slice(idx + 1) : "";
      if (!b64) throw new Error("empty_base64");

      await store.importDatasetZip(dsId, {
        filename: file.name,
        dataB64: b64,
        overwrite: overwriteOnImport.value,
      });
      ElMessage({ type: "success", message: "ZIP 导入成功" });
    } catch (e) {
      ElMessage({ type: "error", message: `ZIP 导入失败：${e?.message || e}` });
    }
  });
  document.body.appendChild(input);
  fileInputRef.value = input;
}

function chooseZipFor(id) {
  importTargetId.value = id;
  _ensureFileInput();
  fileInputRef.value.click();
}

function chooseZipForNew() {
  if (!selectedDatasetId.value) return alert("请先选择一个数据集");
  chooseZipFor(selectedDatasetId.value);
}

async function scanOne(id) {
  try {
    await store.scanDataset(id);
    ElMessage({ type: "success", message: "扫描完成" });
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
  }
}

async function scanSelected() {
  if (!selectedDatasetId.value) return alert("请先选择一个数据集");
  await scanOne(selectedDatasetId.value);
}

async function generateDemoOnBackend() {
  const targetId = selectedDatasetId.value || "ds_demo";
  try {
    await ElMessageBox.confirm(
      `将为 ${targetId} 生成 5 组 Demo 样例（含 gt 与输入目录），是否继续？`,
      "生成 Demo",
      { type: "warning", confirmButtonText: "开始生成", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }

  if (generating.value) return;
  generating.value = true;
  ElMessage({ type: "info", message: "正在生成并刷新数据..." });

  try {
    const res = await fetch(`http://127.0.0.1:8000/dev/datasets/${targetId}/generate?task_type=all&count=5`, {
      method: "POST",
    });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const data = ct.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) throw new Error(typeof data === "string" ? data : JSON.stringify(data));
    const created = typeof data === "object" && data ? data.created : null;
    ElMessage({ type: "success", message: `生成成功：${JSON.stringify(created ?? data)}` });
    await store.fetchDatasets();
    if (targetId) {
      await scanOne(targetId);
    }
  } catch (e) {
    ElMessage({ type: "error", message: `生成失败：${e?.message || e}` });
  } finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.page {
  padding: 16px;
}

.title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: #1b2f62;
}

.subtitle {
  margin-bottom: 14px;
  color: #5f7098;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.selectorRow {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.label {
  color: #5f7098;
}

.selectBox,
.inputBox {
  min-width: 220px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid #c8d7fb;
  background: #fff;
}

.checkboxLabel {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #5f7098;
}

.gridTable {
  width: 100%;
  border-collapse: collapse;
  border-color: #d9e4ff;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

.gridTable thead tr {
  background: #f4f7ff;
}

.miniBtn {
  margin-right: 6px;
  padding: 4px 8px;
}

.dangerBtn {
  color: #a53030;
  border-color: #f3c5c5;
  background: linear-gradient(180deg, #fff 0%, #fff2f2 100%);
}

.emptyText {
  color: #8a96b3;
}

.mask {
  position: fixed;
  inset: 0;
  background: rgba(8, 18, 40, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.dialog {
  background: #fff;
  padding: 16px;
  width: 420px;
  border-radius: 14px;
  border: 1px solid #d8e3ff;
  box-shadow: 0 18px 32px rgba(23, 71, 180, 0.2);
}

.dialogTitle {
  margin: 0 0 12px;
  color: #1f3263;
}

.formCol {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dialogFooter {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
