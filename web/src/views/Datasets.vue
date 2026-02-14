<template>
  <div style="padding: 16px;">
    <h2 style="margin: 0 0 8px;">数据集管理</h2>
    <div style="color:#666; margin-bottom: 12px;">
      用于管理数据集的创建/删除/查看元信息，支持导入 ZIP（需要 gt/ 与退化图像目录：hazy/noisy/blur/lr/dark）。
    </div>

    <div style="display:flex; gap:8px; margin-bottom: 12px;">
      <button @click="openCreate" style="padding:6px 10px;">新建数据集</button>
      <button @click="chooseZipForNew" style="padding:6px 10px;">导入 ZIP 到选中数据集</button>
      <button
        @click="generateDemoOnBackend"
        :disabled="generating"
        style="padding:6px 10px;"
      >
        {{ generating ? "生成中..." : "生成后端 Demo 数据" }}
      </button>
    </div>

    <div style="display:flex; gap:10px; align-items:center; margin-bottom: 12px;">
      <div style="color:#666;">当前目标：</div>
      <select v-model="selectedDatasetId" style="padding:6px; min-width:220px;">
        <option value="" disabled>请选择数据集</option>
        <option v-for="d in store.datasets" :key="d.id" :value="d.id">
          {{ d.name }}（{{ d.id }}）
        </option>
      </select>
      <label style="display:flex; gap:6px; align-items:center; color:#666;">
        <input type="checkbox" v-model="overwriteOnImport" />
        覆盖导入（覆盖原目录，推荐）
      </label>
      <button @click="scanSelected" style="padding:6px 10px;">扫描并刷新规模</button>
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
            <button @click="scanOne(ds.id)" style="padding:4px 8px; margin-right:6px;">扫描</button>
            <button @click="chooseZipFor(ds.id)" style="padding:4px 8px; margin-right:6px;">导入 ZIP</button>
            <button @click="remove(ds.id)" style="padding:4px 8px;">删除</button>
          </td>
        </tr>
        <tr v-if="store.datasets.length === 0">
          <td colspan="5" style="color:#888;">暂无数据集</td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center;">
      <div style="background:#fff; padding:16px; width:420px; border-radius:10px;">
        <h3 style="margin:0 0 12px;">新建数据集</h3>

        <div style="display:flex; flex-direction:column; gap:10px;">
          <label>
            ID（可选）：
            <input v-model="form.id" placeholder="例如：ds_gopro_deblur_test" style="width:100%; padding:6px;" />
          </label>

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
          <button @click="submitCreate" style="padding:6px 10px;">确认创建</button>
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
    await store.createDataset({
      id: form.id.trim() || undefined,
      name: form.name.trim(),
      type: form.type,
      size: form.size.trim() || "-",
    });
    showCreate.value = false;
  } catch (e) {
    alert(`创建失败：${e?.message || e}`);
  }
}

async function remove(id) {
  const ok = confirm("确认删除该数据集？");
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
      `确认将 ZIP 导入到数据集 ${dsId}？${overwriteOnImport.value ? "（覆盖导入：覆盖原目录）" : "（不覆盖：与原目录合并，规模可能不准）"}`
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
      ElMessage({ type: "success", message: "导入成功，请刷新规模" });
    } catch (e) {
      ElMessage({ type: "error", message: `导入失败：${e?.message || e}` });
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
  if (!selectedDatasetId.value) return alert("请先选择目标数据集");
  chooseZipFor(selectedDatasetId.value);
}

async function scanOne(id) {
  try {
    await store.scanDataset(id);
    ElMessage({ type: "success", message: "已刷新规模" });
  } catch (e) {
    ElMessage({ type: "error", message: `扫描失败：${e?.message || e}` });
  }
}

async function scanSelected() {
  if (!selectedDatasetId.value) return alert("请先选择数据集");
  await scanOne(selectedDatasetId.value);
}

async function generateDemoOnBackend() {
  const targetId = selectedDatasetId.value || "ds_demo";
  try {
    await ElMessageBox.confirm(
      `将为 ${targetId} 在后端生成 5 组演示数据（gt + 退化图像子目录）。`,
      "生成演示数据",
      { type: "warning", confirmButtonText: "生成", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }

  if (generating.value) return;
  generating.value = true;
  ElMessage({ type: "info", message: "开始生成，请稍后" });

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
