<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">&#31639;&#27861;&#24211;</h2>
      <div class="subtitle">
        &#36825;&#37324;&#20027;&#35201;&#29992;&#20110;&#26597;&#30475;&#24179;&#21488;&#31639;&#27861;&#12289;&#24050;&#19979;&#36733;&#31038;&#53306;&#31639;&#27861;&#19982;&#21382;&#21490;&#29992;&#25143;&#31639;&#27861;&#35760;&#24405;&#65307;&#26032;&#30340;&#33258;&#23450;&#20041;&#31639;&#27861;&#35831;&#36208;&#8220;&#31639;&#27861;&#25509;&#20837;&#8221;&#27969;&#31243;&#25552;&#20132;&#20195;&#30721;&#21253;&#12290;
      </div>
    </div>

    <div class="action-bar">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button type="primary" class="centered-btn action-btn" @click="goToAlgorithmAccess" :disabled="!store.user.isLoggedIn">&#25552;&#20132;&#31639;&#27861;&#20195;&#30721;&#21253;</el-button>
          <el-button icon="RefreshLeft" class="centered-btn action-btn" @click="resetToBuiltins" :disabled="!store.user.isLoggedIn">&#28165;&#29702;&#29992;&#25143;&#31639;&#27861;</el-button>
        </div>
      </div>

      <div class="filter-bar">
        <div class="filter-left">
          <el-select v-model="filterTask" placeholder="&#20840;&#37096;&#20219;&#21153;" clearable class="filter-box">
            <el-option v-for="t in taskFilterOptions" :key="t" :label="t" :value="t" />
          </el-select>
          <el-select v-model="filterImpl" placeholder="&#20840;&#37096;&#23454;&#29616;" clearable class="filter-box">
            <el-option v-for="x in implFilterOptions" :key="x" :label="x" :value="x" />
          </el-select>
          <el-input v-model="filterKeyword" placeholder="&#25628;&#32034;&#31639;&#27861;&#21517;&#31216; / &#29256;&#26412; / ID" clearable class="filter-input" prefix-icon="Search" />
        </div>
        <el-button @click="resetFilters" icon="Close" plain class="reset-btn centered-btn action-btn">&#37325;&#32622;&#31579;&#36873;</el-button>
      </div>
    </div>

    <div class="section">
      <el-tabs v-model="activeAlgorithmTab" class="resource-tabs">
        <el-tab-pane label="&#24179;&#21488;&#31639;&#27861;" name="builtin">
          <el-table :data="filteredBuiltinAlgorithms" border stripe class="data-table">
            <el-table-column prop="task" label="&#20219;&#21153;" width="120" />
            <el-table-column prop="name" label="&#31639;&#27861;&#21517;&#31216;" min-width="200" />
            <el-table-column prop="impl" label="&#23454;&#29616;&#26041;&#24335;" width="120" />
            <el-table-column prop="version" label="&#29256;&#26412;" width="100" />
            <el-table-column prop="createdAt" label="&#21019;&#24314;&#26102;&#38388;" width="180" />
            <el-table-column label="&#25805;&#20316;" width="180">
              <template #default="{ row }">
                <el-dropdown v-if="canManagePlatformAlgorithm(row)" trigger="click" @command="(cmd) => handlePlatformAlgorithmAction(row, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="exportingAlgorithms.has(row.id)" :disabled="!store.user.isLoggedIn">
                    {{ TEXT.manage }}<el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="view">&#26597;&#30475;&#21442;&#25968;</el-dropdown-item>
                      <el-dropdown-item command="edit">&#32534;&#36753;</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>&#19979;&#26550;</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <template v-else>
                  <el-button size="small" icon="Setting" @click="viewBuiltinParams(row)">&#26597;&#30475;&#21442;&#25968;</el-button>
                  <el-tag size="small" type="info" class="readonly-tag">&#21482;&#35835;</el-tag>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="&#29992;&#25143;&#31639;&#27861;" name="owned">
          <div class="history-tip">
            &#36825;&#37324;&#23637;&#31034;&#24403;&#21069;&#36134;&#21495;&#30340;&#31169;&#26377;&#31639;&#27861;&#12290;&#21253;&#25324;&#36890;&#36807;&#8220;&#31639;&#27861;&#25509;&#20837;&#8221;&#23457;&#26680;&#21518;&#29983;&#25104;&#30340; UserPackage &#31639;&#27861;&#65292;&#21487;&#29992;&#20110;&#26412;&#20154;&#21457;&#36215;&#27979;&#35797;&#12289;&#19979;&#36733;&#19982;&#21024;&#38500;&#12290;
          </div>
          <el-table :data="pagedOwnedAlgorithms" border stripe class="data-table">
            <el-table-column prop="task" label="&#20219;&#21153;" width="120" />
            <el-table-column prop="name" label="&#31639;&#27861;&#21517;&#31216;" min-width="200" />
            <el-table-column prop="impl" label="&#23454;&#29616;&#26041;&#24335;" width="120" />
            <el-table-column prop="version" label="&#29256;&#26412;" width="100" />
            <el-table-column prop="createdAt" label="&#21019;&#24314;&#26102;&#38388;" width="180" />
            <el-table-column label="&#25805;&#20316;" width="120">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleAlgorithmAction(row, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="exportingAlgorithms.has(row.id)" :disabled="!store.user.isLoggedIn">
                    {{ TEXT.manage }}<el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="use">{{ TEXT.use }}</el-dropdown-item>
                      <el-dropdown-item command="export">&#19979;&#36733;&#21040;&#26412;&#22320;</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>&#21024;&#38500;</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="&#26242;&#26080;&#29992;&#25143;&#31639;&#27861;" />
            </template>
          </el-table>

          <div class="pagination-row">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="filteredOwnedAlgorithms.length"
              @size-change="() => currentPage = 1"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane :label="TEXT.communityAlgorithms" name="community">
          <el-table :data="filteredDownloadedAlgorithms" border stripe class="data-table">
            <el-table-column prop="task" label="&#20219;&#21153;" width="120" />
            <el-table-column prop="name" label="&#31639;&#27861;&#21517;&#31216;" min-width="200" />
            <el-table-column prop="impl" label="&#23454;&#29616;&#26041;&#24335;" width="120" />
            <el-table-column prop="version" label="&#29256;&#26412;" width="100" />
            <el-table-column prop="sourceUploaderId" label="&#19978;&#20256;&#32773;ID" width="140" />
            <el-table-column prop="createdAt" label="&#19979;&#36733;&#26102;&#38388;" width="180" />
            <el-table-column label="&#25805;&#20316;" width="140">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => handleAlgorithmAction(row, cmd)">
                  <el-button size="small" class="table-action-btn" :loading="exportingAlgorithms.has(row.id)" :disabled="!store.user.isLoggedIn">
                    {{ TEXT.manage }}<el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="use">{{ TEXT.use }}</el-dropdown-item>
                      <el-dropdown-item command="export">&#19979;&#36733;&#21040;&#26412;&#22320;</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>&#21024;&#38500;</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="&#26242;&#26080;&#31038;&#53306;&#31639;&#27861;" />
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="showParamDialog" title="&#20869;&#32622;&#31639;&#27861;&#21442;&#25968;&#35814;&#24773;" width="760px">
      <el-descriptions border :column="2" class="param-desc">
        <el-descriptions-item label="&#31639;&#27861;&#21517;&#31216;">{{ paramDialogTitle }}</el-descriptions-item>
        <el-descriptions-item label="&#31639;&#27861; ID">{{ paramDialogId || '-' }}</el-descriptions-item>
        <el-descriptions-item label="&#20219;&#21153;">{{ paramDialogTask || '-' }}</el-descriptions-item>
        <el-descriptions-item label="&#23454;&#29616;&#26041;&#24335;">{{ paramDialogImpl || '-' }}</el-descriptions-item>
        <el-descriptions-item label="&#29256;&#26412;">{{ paramDialogVersion || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="param-section-title">&#40664;&#35748;&#21442;&#25968;&#65288;&#21487;&#35270;&#21270;&#65289;</div>
      <div v-if="paramDialogRows.length === 0" class="no-params">&#35813;&#20869;&#32622;&#31639;&#27861;&#26080;&#40664;&#35748;&#21442;&#25968;&#12290;</div>
      <div v-else class="param-kv-list">
        <div v-for="item in paramDialogRows" :key="`pk-${item.key}`" class="param-kv-item">
          <span class="param-kv-key">{{ item.key }}</span>
          <span class="param-kv-type">{{ item.type }}</span>
          <span class="param-kv-val">{{ item.text }}</span>
        </div>
      </div>

      <div class="param-section-title">&#21442;&#25968;&#35828;&#26126;</div>
      <div v-if="paramDialogExplainList.length === 0" class="no-params">&#35813;&#31639;&#27861;&#26080;&#40664;&#35748;&#21442;&#25968;&#12290;</div>
      <div class="param-explain-list">
        <div v-for="item in paramDialogExplainList" :key="`pd-${item.key}`" class="explain-item">
          <span class="explain-label">{{ item.label }}</span>
          <span class="explain-key">({{ item.key }})</span>
          <span class="explain-usage">{{ item.usage }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showParamDialog = false">&#20851;&#38381;</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editorVisible" :title="isEditing ? '&#32534;&#36753;&#31639;&#27861;' : '&#26032;&#22686;&#31639;&#27861;'" width="1100px" top="5vh">
      <div class="algorithm-form-container">
        <div class="form-left">
          <el-form :model="isEditing ? editForm : form" label-position="top">
            <el-form-item label="&#20219;&#21153;&#31867;&#21035;">
              <el-select v-model="(isEditing ? editForm : form).task" style="width: 100%">
                <el-option v-for="t in ['&#21435;&#22122;', '&#21435;&#27169;&#31946;', '&#21435;&#38654;', '&#36229;&#20998;&#36776;&#29575;', '&#20302;&#29031;&#24230;&#22686;&#24378;', '&#35270;&#39057;&#21435;&#22122;', '&#35270;&#39057;&#36229;&#20998;']" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>

            <el-form-item label="&#39044;&#35774;&#31639;&#27861;">
              <el-select v-model="(isEditing ? editForm : form).presetKey" style="width: 100%">
                <el-option v-for="p in (isEditing ? editPresetOptions : createPresetOptions)" :key="p.key" :label="p.name" :value="p.key" />
              </el-select>
            </el-form-item>

            <el-form-item label="&#33258;&#23450;&#20041;&#26631;&#35782;">
              <el-input v-model="(isEditing ? editForm : form).customTag" placeholder="&#20363;&#22914;&#65306;&#23454;&#39564;A / &#28436;&#31034;&#29256;" />
              <div class="form-hint">&#29992;&#20110;&#21306;&#20998;&#21516;&#19968;&#39044;&#35774;&#31639;&#27861;&#19979;&#30340;&#19981;&#21516;&#23454;&#39564;&#26465;&#30446;</div>
            </el-form-item>

            <el-form-item label="&#23454;&#29616;&#26041;&#24335;">
              <el-input v-model="(isEditing ? editForm : form).impl" disabled />
            </el-form-item>

            <el-form-item label="&#29256;&#26412;">
              <el-input v-model="(isEditing ? editForm : form).version" placeholder="&#20363;&#22914;&#65306;v1" />
            </el-form-item>
          </el-form>
        </div>

        <div class="form-right">
          <div class="param-header">
            <span class="param-title">&#40664;&#35748;&#21442;&#25968;&#65288;JSON&#65289;</span>
            <div class="param-modes">
              <el-radio-group v-model="activeParamMode" size="small">
                <el-radio-button label="visual">&#21487;&#35270;&#21270;</el-radio-button>
                <el-radio-button label="json">JSON</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="param-actions">
            <el-button-group size="small">
              <el-button @click="applyParamStyle(isEditing ? 'edit' : 'create', 'default')">&#24674;&#22797;&#40664;&#35748;&#21442;&#25968;</el-button>
              <el-button @click="applyParamStyle(isEditing ? 'edit' : 'create', 'safe')">&#31283;&#22949;&#27169;&#24335;</el-button>
              <el-button @click="applyParamStyle(isEditing ? 'edit' : 'create', 'strong')">&#22686;&#24378;&#27169;&#24335;</el-button>
            </el-button-group>
          </div>

          <div class="param-editor">
            <div v-if="activeParamMode === 'visual'" class="visual-editor">
              <div v-for="(row, idx) in activeParamRows" :key="idx" class="param-row">
                <el-input v-model="row.key" placeholder="&#21442;&#25968;&#21517;" :disabled="activePresetConstrained" style="flex: 1.5" />
                <el-select v-model="row.type" :disabled="activePresetConstrained" style="width: 100px">
                  <el-option label="&#25968;&#23383;" value="number" />
                  <el-option label="&#25991;&#26412;" value="string" />
                  <el-option label="&#24320;&#20851;" value="boolean" />
                </el-select>
                <el-input v-if="row.type !== 'boolean'" v-model="row.value" placeholder="&#20540;" style="flex: 1" />
                <el-select v-else v-model="row.value" style="flex: 1">
                  <el-option label="&#26159;" value="true" />
                  <el-option label="&#21542;" value="false" />
                </el-select>
                <el-button type="danger" plain icon="Delete" circle size="small" @click="removeActiveParamRow(idx)" />
              </div>
              <el-button v-if="!activePresetConstrained" type="dashed" icon="Plus" style="width: 100%; margin-top: 8px" @click="addActiveParamRow">&#28155;&#21152;&#21442;&#25968;</el-button>
            </div>
            <el-input v-else v-model="activeParamsText" type="textarea" :rows="10" placeholder="&#35831;&#36755;&#20837;&#21512;&#27861;&#30340; JSON &#23545;&#35937;" font-family="monospace" />
          </div>

          <div class="param-doc-panel">
            <div class="doc-title">&#21442;&#25968;&#20013;&#25991;&#35828;&#26126;</div>
            <div class="doc-list">
              <div v-for="item in activeExplainList" :key="item.key" class="doc-item">
                <span class="doc-label">{{ item.label }}</span>
                <span class="doc-usage">{{ item.usage }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="isEditing ? closeEdit() : closeCreate()">&#21462;&#28040;</el-button>
        <el-button type="primary" @click="isEditing ? submitEdit() : submitCreate()">{{ isEditing ? '&#20445;&#23384;&#20462;&#25913;' : '&#30830;&#35748;&#26032;&#22686;' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
import { algorithmsApi } from "../api/algorithms";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const router = useRouter();
const TEXT = {
  communityAlgorithms: "\u793e\u533a\u7b97\u6cd5",
  manage: "\u7ba1\u7406",
  use: "\u4f7f\u7528",
};
const HIDDEN_PLATFORM_ALGORITHM_IDS = new Set([
  "alg_dn_cnn_light",
  "alg_dn_cnn_strong",
  "alg_denoise_bilateral_soft",
  "alg_denoise_bilateral_strong",
  "alg_denoise_gaussian_light",
  "alg_denoise_gaussian_strong",
  "alg_denoise_median_light",
  "alg_denoise_median_strong",
  "alg_dehaze_dcp_fast",
  "alg_dehaze_dcp_strong",
  "alg_dehaze_clahe_mild",
  "alg_dehaze_clahe_strong",
  "alg_dehaze_gamma_mild",
  "alg_dehaze_gamma_strong",
  "alg_deblur_unsharp_light",
  "alg_deblur_unsharp_strong",
  "alg_deblur_laplacian_light",
  "alg_deblur_laplacian_strong",
  "alg_sr_nearest",
  "alg_sr_linear",
  "alg_sr_bicubic_sharp",
  "alg_sr_lanczos_sharp",
  "alg_lowlight_gamma_soft",
  "alg_lowlight_gamma_strong",
  "alg_lowlight_clahe_soft",
  "alg_lowlight_clahe_strong",
  "alg_video_denoise_gaussian_light",
  "alg_video_denoise_gaussian_strong",
  "alg_video_denoise_median_light",
  "alg_video_denoise_median_strong",
  "alg_video_sr_nearest",
  "alg_video_sr_linear",
  "alg_video_sr_bicubic_sharp",
  "alg_video_sr_lanczos_sharp",
]);
function isPlatformAlgorithm(alg) {
  return String(alg?.raw?.owner_id || "") === "system";
}
function getPackageRole(alg) {
  const explicit = String(alg?.packageRole || alg?.raw?.package_role || "").trim().toLowerCase();
  if (explicit) return explicit;
  const impl = String(alg?.impl || alg?.raw?.impl || "").trim().toLowerCase();
  if (impl !== "userpackage") return "";
  if (isPlatformAlgorithm(alg)) return "platform";
  const visibility = String(alg?.visibility || alg?.raw?.visibility || "").trim().toLowerCase();
  if (String(alg?.sourceAlgorithmId || alg?.raw?.source_algorithm_id || "").trim()) return "downloaded_community";
  if (visibility === "public" && String(alg?.sourceSubmissionId || alg?.raw?.source_submission_id || "").trim()) return "community";
  if (String(alg?.sourceSubmissionId || alg?.raw?.source_submission_id || "").trim()) return "owner_runtime";
  return "";
}
function isVisiblePlatformAlgorithm(alg) {
  if (!isPlatformAlgorithm(alg)) return false;
  if (alg?.raw?.is_active === false) return false;
  const hasCommunitySource = String(alg?.sourceUploaderId || "").trim() || String(alg?.sourceAlgorithmId || "").trim();
  if (hasCommunitySource) return true;
  return !HIDDEN_PLATFORM_ALGORITHM_IDS.has(String(alg?.id || ""));
}
function canManagePlatformAlgorithm(alg) {
  if (store.user.role !== "admin") return false;
  if (!isPlatformAlgorithm(alg)) return false;
  return true;
}
const TASK_SORT_ORDER = {
  "去雾": 1,
  "去噪": 2,
  "去模糊": 3,
  "超分辨率": 4,
  "低照度增强": 5,
  "视频去噪": 6,
  "视频超分": 7,
};
const sortedAlgorithms = computed(() => {
  const arr = Array.isArray(store.algorithms) ? [...store.algorithms] : [];
  arr.sort((a, b) => {
    const ta = TASK_SORT_ORDER[String(a?.task || "")] ?? 99;
    const tb = TASK_SORT_ORDER[String(b?.task || "")] ?? 99;
    if (ta !== tb) return ta - tb;
    const na = String(a?.name || "");
    const nb = String(b?.name || "");
    const byName = na.localeCompare(nb, "zh-Hans-CN-u-co-pinyin");
    if (byName !== 0) return byName;
    const ca = Number(a?.raw?.created_at || 0);
    const cb = Number(b?.raw?.created_at || 0);
    if (ca !== cb) return cb - ca;
    return String(a?.id || "").localeCompare(String(b?.id || ""));
  });
  return arr;
});
const filterTask = ref("");
const filterImpl = ref("");
const filterKeyword = ref("");
const activeAlgorithmTab = ref("builtin");
const currentPage = ref(1);
const pageSize = ref(20);
const exportingAlgorithms = ref(new Set());
const taskFilterOptions = computed(() => {
  return [...new Set(sortedAlgorithms.value.map((a) => String(a?.task || "").trim()).filter(Boolean))];
});
const implFilterOptions = computed(() => {
  return [...new Set(sortedAlgorithms.value.map((a) => String(a?.impl || "").trim()).filter(Boolean))];
});
const filteredAlgorithms = computed(() => {
  const kw = String(filterKeyword.value || "").trim().toLowerCase();
  return sortedAlgorithms.value.filter((a) => {
    if (filterTask.value && a.task !== filterTask.value) return false;
    if (filterImpl.value && a.impl !== filterImpl.value) return false;
    if (!kw) return true;
    const text = `${a.name || ""} ${a.version || ""} ${a.id || ""}`.toLowerCase();
    return text.includes(kw);
  });
});
const filteredBuiltinAlgorithms = computed(() => filteredAlgorithms.value.filter((a) => isVisiblePlatformAlgorithm(a)));
const filteredUserAlgorithms = computed(() => filteredAlgorithms.value.filter((a) => !isPlatformAlgorithm(a)));
function isUserRuntimeAlgorithm(row) {
  const role = getPackageRole(row);
  if (role === "owner_runtime") return true;
  if (role === "community" || role === "downloaded_community") return false;
  return !hasAlgorithmCommunitySource(row);
}
function hasAlgorithmCommunitySource(row) {
  const role = getPackageRole(row);
  if (role === "community" || role === "downloaded_community") return true;
  return Boolean(String(row?.sourceUploaderId || "").trim() || String(row?.sourceAlgorithmId || "").trim());
}
const filteredOwnedAlgorithms = computed(() => filteredUserAlgorithms.value.filter((a) => isUserRuntimeAlgorithm(a)));
const filteredDownloadedAlgorithms = computed(() => filteredUserAlgorithms.value.filter((a) => hasAlgorithmCommunitySource(a)));

function isSelfPublishedAlgorithm(row) {
  if (!row) return false;
  if (String(row?.uploaderId || "") !== String(store.user?.username || "")) return false;
  if (hasAlgorithmCommunitySource(row)) return false;
  return String(row?.visibility || "").toLowerCase() === "public";
}
const pageCount = computed(() => {
  const n = Math.ceil(filteredOwnedAlgorithms.value.length / Number(pageSize.value || 20));
  return n > 0 ? n : 1;
});
const pagedOwnedAlgorithms = computed(() => {
  const page = Math.min(Math.max(1, Number(currentPage.value || 1)), pageCount.value);
  const size = Math.max(1, Number(pageSize.value || 20));
  const start = (page - 1) * size;
  return filteredOwnedAlgorithms.value.slice(start, start + size);
});

function resetFilters() {
  filterTask.value = "";
  filterImpl.value = "";
  filterKeyword.value = "";
  currentPage.value = 1;
}

function goToAlgorithmAccess() {
  router.push("/algorithm-access");
}

const PRESET_BY_TASK = {
  去雾: [
    { key: "dehaze_dcp", name: "DCP暗通道先验(基线)", impl: "OpenCV", defaultParams: { dcp_patch: 15, dcp_omega: 0.95, dcp_t0: 0.1 } },
    { key: "dehaze_clahe", name: "CLAHE(基线)", impl: "OpenCV", defaultParams: { clahe_clip_limit: 2.0 } },
    { key: "dehaze_gamma", name: "Gamma(基线)", impl: "OpenCV", defaultParams: { gamma: 0.75 } },
  ],
  去噪: [
    {
      key: "denoise_nlm",
      name: "FastNLMeans(基线)",
      impl: "OpenCV",
      defaultParams: { nlm_h: 10, nlm_hColor: 10, nlm_templateWindowSize: 7, nlm_searchWindowSize: 21 },
    },
    {
      key: "denoise_bilateral",
      name: "Bilateral(基线)",
      impl: "OpenCV",
      defaultParams: { bilateral_d: 7, bilateral_sigmaColor: 35, bilateral_sigmaSpace: 35 },
    },
    { key: "denoise_gaussian", name: "Gaussian(基线)", impl: "OpenCV", defaultParams: { gaussian_sigma: 1.0 } },
    { key: "denoise_median", name: "Median(基线)", impl: "OpenCV", defaultParams: { median_ksize: 3 } },
  ],
  去模糊: [
    {
      key: "deblur_unsharp",
      name: "UnsharpMask(基线)",
      impl: "OpenCV",
      defaultParams: { unsharp_sigma: 1.0, unsharp_amount: 1.6 },
    },
    { key: "deblur_laplacian", name: "LaplacianSharpen(基线)", impl: "OpenCV", defaultParams: { laplacian_strength: 0.7 } },
  ],
  超分辨率: [
    { key: "sr_bicubic", name: "Bicubic(基线)", impl: "OpenCV", defaultParams: {} },
    { key: "sr_lanczos", name: "Lanczos(基线)", impl: "OpenCV", defaultParams: {} },
    { key: "sr_nearest", name: "Nearest(基线)", impl: "OpenCV", defaultParams: {} },
  ],
  低照度增强: [
    { key: "lowlight_gamma", name: "Gamma(基线)", impl: "OpenCV", defaultParams: { lowlight_gamma: 0.6 } },
    { key: "lowlight_clahe", name: "CLAHE(基线)", impl: "OpenCV", defaultParams: { clahe_clip_limit: 2.5 } },
  ],
  视频去噪: [],
  视频超分: [],
};

const PARAM_DOCS = {
  dcp_patch: { label: "暗通道窗口", usage: "窗口越大去雾越强，但细节更容易被抹平。" },
  dcp_omega: { label: "去雾强度", usage: "越大去雾越明显，过高可能偏灰。" },
  dcp_t0: { label: "最小透射率", usage: "用于限制最暗区域，避免过度增强噪声。" },
  clahe_clip_limit: { label: "局部对比度上限", usage: "越大对比度越高，过高会放大噪声。" },
  gamma: { label: "亮度伽马", usage: "小于 1 提亮暗部，大于 1 压暗画面。" },
  lowlight_gamma: { label: "低照增强强度", usage: "用于低照图片提亮，建议从 0.5 到 0.8 尝试。" },
  nlm_h: { label: "去噪强度", usage: "越大去噪越强，细节损失也更明显。" },
  nlm_hColor: { label: "色彩去噪强度", usage: "控制彩色噪声抑制，建议与去噪强度接近。" },
  nlm_templateWindowSize: { label: "模板窗口大小", usage: "匹配局部纹理用，常用奇数 7。" },
  nlm_searchWindowSize: { label: "搜索窗口大小", usage: "搜索范围越大越稳但更慢，常用奇数 21。" },
  bilateral_d: { label: "双边滤波直径", usage: "邻域大小，越大平滑更明显。" },
  bilateral_sigmaColor: { label: "色域平滑系数", usage: "控制颜色差异的平滑程度。" },
  bilateral_sigmaSpace: { label: "空间平滑系数", usage: "控制空间距离的平滑程度。" },
  gaussian_sigma: { label: "高斯标准差", usage: "越大模糊越强，适合轻噪声抑制。" },
  median_ksize: { label: "中值核大小", usage: "应为奇数，越大去噪越强。" },
  unsharp_sigma: { label: "锐化半径", usage: "控制锐化作用范围。" },
  unsharp_amount: { label: "锐化强度", usage: "越大边缘越锐，过高易产生光晕。" },
  laplacian_strength: { label: "拉普拉斯锐化强度", usage: "越大边缘增强越明显。" },
};
const TASK_PARAM_KEYS = {
  去雾: ["dcp_patch", "dcp_omega", "dcp_t0", "clahe_clip_limit", "gamma"],
  去噪: ["nlm_h", "nlm_hColor", "nlm_templateWindowSize", "nlm_searchWindowSize", "bilateral_d", "bilateral_sigmaColor", "bilateral_sigmaSpace", "gaussian_sigma", "median_ksize"],
  去模糊: ["unsharp_sigma", "unsharp_amount", "laplacian_strength"],
  超分辨率: [],
  低照度增强: ["lowlight_gamma", "clahe_clip_limit"],
  视频去噪: ["gaussian_sigma", "median_ksize"],
  视频超分: [],
};
const PARAM_RULES = {
  dcp_patch: { type: "number", integer: true, min: 3, max: 51, odd: true },
  dcp_omega: { type: "number", min: 0, max: 1.5 },
  dcp_t0: { type: "number", min: 0.01, max: 0.5 },
  clahe_clip_limit: { type: "number", min: 0.1, max: 40 },
  gamma: { type: "number", min: 0.05, max: 5 },
  lowlight_gamma: { type: "number", min: 0.05, max: 5 },
  nlm_h: { type: "number", min: 1, max: 50 },
  nlm_hColor: { type: "number", min: 1, max: 50 },
  nlm_templateWindowSize: { type: "number", integer: true, min: 3, max: 21, odd: true },
  nlm_searchWindowSize: { type: "number", integer: true, min: 3, max: 51, odd: true },
  bilateral_d: { type: "number", integer: true, min: 1, max: 25 },
  bilateral_sigmaColor: { type: "number", min: 1, max: 200 },
  bilateral_sigmaSpace: { type: "number", min: 1, max: 200 },
  gaussian_sigma: { type: "number", min: 0.05, max: 20 },
  median_ksize: { type: "number", integer: true, min: 1, max: 31, odd: true },
  unsharp_sigma: { type: "number", min: 0.05, max: 10 },
  unsharp_amount: { type: "number", min: 1, max: 5 },
  laplacian_strength: { type: "number", min: 0, max: 5 },
};

const showCreate = ref(false);
const showEdit = ref(false);
const createParamMode = ref("visual");
const editParamMode = ref("visual");
const createParamRows = ref([]);
const editParamRows = ref([]);
const form = reactive({
  task: "去噪",
  presetKey: "",
  name: "",
  customTag: "",
  impl: "OpenCV",
  version: "v1",
  defaultParamsText: "{}",
});

const editForm = reactive({
  id: "",
  task: "去噪",
  presetKey: "",
  name: "",
  customTag: "",
  impl: "OpenCV",
  version: "v1",
  defaultParamsText: "{}",
});

const createPresetOptions = ref([]);
const editPresetOptions = ref([]);
const suppressCreatePresetSync = ref(false);
const suppressEditPresetSync = ref(false);
const createSelectedPreset = computed(() => {
  return (PRESET_BY_TASK[form.task] || []).find((x) => x.key === form.presetKey) || null;
});
const editSelectedPreset = computed(() => {
  return (PRESET_BY_TASK[editForm.task] || []).find((x) => x.key === editForm.presetKey) || null;
});
const isCreatePresetConstrained = computed(() => Boolean(createSelectedPreset.value));
const isEditPresetConstrained = computed(() => Boolean(editSelectedPreset.value));
const showParamDialog = ref(false);
const paramDialogTitle = ref("");
const paramDialogId = ref("");
const paramDialogTask = ref("");
const paramDialogImpl = ref("");
const paramDialogVersion = ref("");
const paramDialogExplainList = ref([]);
const paramDialogRows = ref([]);

function toParamRows(obj) {
  return Object.entries(obj || {}).map(([key, value]) => {
    if (typeof value === "boolean") return { key, type: "boolean", value: value ? "true" : "false" };
    if (typeof value === "number") return { key, type: "number", value: String(value) };
    return { key, type: "string", value: String(value ?? "") };
  });
}

function rowsToParamObject(rows) {
  const out = {};
  for (const r of rows || []) {
    const key = String(r?.key || "").trim();
    if (!key) continue;
    if (r.type === "boolean") {
      out[key] = String(r.value) === "true";
      continue;
    }
    if (r.type === "number") {
      const n = Number(r.value);
      out[key] = Number.isFinite(n) ? n : 0;
      continue;
    }
    out[key] = String(r.value ?? "");
  }
  return out;
}

function getParamDoc(key) {
  const k = String(key || "").trim();
  if (!k) return null;
  const doc = PARAM_DOCS[k];
  if (doc) return { key: k, ...doc };
  return { key: k, label: "自定义参数", usage: "当前参数暂无内置说明，请结合算法文档或实验对比调整。" };
}

function getParamExplainLine(key) {
  const doc = getParamDoc(key);
  if (!doc) return "请输入参数名后会显示中文说明。";
  return `${doc.label}：${doc.usage}`;
}

function suggestParamKey(task) {
  const preset = (PRESET_BY_TASK[task] || [])[0];
  const first = preset && preset.defaultParams ? Object.keys(preset.defaultParams)[0] : "";
  return first || "dcp_patch";
}

function listFromJsonText(s) {
  try {
    const obj = s ? JSON.parse(s) : {};
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
    return Object.keys(obj).map((k) => getParamDoc(k));
  } catch {
    return [];
  }
}

function getCreateExplainList() {
  const fromVisual = createParamRows.value.map((r) => getParamDoc(r.key)).filter(Boolean);
  const list = createParamMode.value === "visual" ? fromVisual : listFromJsonText(String(form.defaultParamsText || "").trim());
  return list.length ? list : [{ key: "_", label: "提示", usage: "先添加参数或选择预设算法，这里会自动显示中文说明。" }];
}

function getEditExplainList() {
  const fromVisual = editParamRows.value.map((r) => getParamDoc(r.key)).filter(Boolean);
  const list = editParamMode.value === "visual" ? fromVisual : listFromJsonText(String(editForm.defaultParamsText || "").trim());
  return list.length ? list : [{ key: "_", label: "提示", usage: "先添加参数或选择预设算法，这里会自动显示中文说明。" }];
}

function setCreateParamsObject(obj) {
  form.defaultParamsText = JSON.stringify(obj || {}, null, 2);
  createParamRows.value = toParamRows(obj || {});
}

function setEditParamsObject(obj) {
  editForm.defaultParamsText = JSON.stringify(obj || {}, null, 2);
  editParamRows.value = toParamRows(obj || {});
}

function _normalizeParamObject(obj) {
  const src = obj && typeof obj === "object" && !Array.isArray(obj) ? obj : {};
  const out = {};
  for (const k of Object.keys(src).sort()) {
    out[k] = src[k];
  }
  return out;
}

function _isSameParamObject(a, b) {
  return JSON.stringify(_normalizeParamObject(a)) === JSON.stringify(_normalizeParamObject(b));
}

function _toSingleParamRow(key, value) {
  if (typeof value === "boolean") return { key, type: "boolean", value: value ? "true" : "false" };
  if (typeof value === "number") return { key, type: "number", value: String(value) };
  return { key, type: "string", value: String(value ?? "") };
}

function addCreateParamRow() {
  if (isCreatePresetConstrained.value) return;
  createParamRows.value.push({ key: "", type: "number", value: "0" });
}

function removeCreateParamRow(idx) {
  if (isCreatePresetConstrained.value) {
    const row = createParamRows.value[idx];
    const key = String(row?.key || "").trim();
    const preset = createSelectedPreset.value;
    if (!preset || !key) return;
    const dv = Object.prototype.hasOwnProperty.call(preset.defaultParams || {}, key)
      ? preset.defaultParams[key]
      : undefined;
    if (dv === undefined) return;
    createParamRows.value[idx] = _toSingleParamRow(key, dv);
    form.defaultParamsText = JSON.stringify(rowsToParamObject(createParamRows.value), null, 2);
    return;
  }
  createParamRows.value.splice(idx, 1);
}

function addEditParamRow() {
  if (isEditPresetConstrained.value) return;
  editParamRows.value.push({ key: "", type: "number", value: "0" });
}

function removeEditParamRow(idx) {
  if (isEditPresetConstrained.value) {
    const row = editParamRows.value[idx];
    const key = String(row?.key || "").trim();
    const preset = editSelectedPreset.value;
    if (!preset || !key) return;
    const dv = Object.prototype.hasOwnProperty.call(preset.defaultParams || {}, key)
      ? preset.defaultParams[key]
      : undefined;
    if (dv === undefined) return;
    editParamRows.value[idx] = _toSingleParamRow(key, dv);
    editForm.defaultParamsText = JSON.stringify(rowsToParamObject(editParamRows.value), null, 2);
    return;
  }
  editParamRows.value.splice(idx, 1);
}

function switchCreateParamMode(mode) {
  if (mode === createParamMode.value) return;
  if (mode === "visual") {
    try {
      const s = String(form.defaultParamsText || "").trim();
      const obj = s ? JSON.parse(s) : {};
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) throw new Error("参数需为对象");
      createParamRows.value = toParamRows(obj);
    } catch (e) {
      ElMessage({ type: "error", message: "JSON 解析失败：" + String((e && e.message) || e) });
      return;
    }
  } else {
    form.defaultParamsText = JSON.stringify(rowsToParamObject(createParamRows.value), null, 2);
  }
  createParamMode.value = mode;
}

function switchEditParamMode(mode) {
  if (mode === editParamMode.value) return;
  if (mode === "visual") {
    try {
      const s = String(editForm.defaultParamsText || "").trim();
      const obj = s ? JSON.parse(s) : {};
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) throw new Error("参数需为对象");
      editParamRows.value = toParamRows(obj);
    } catch (e) {
      ElMessage({ type: "error", message: "JSON 解析失败：" + String((e && e.message) || e) });
      return;
    }
  } else {
    editForm.defaultParamsText = JSON.stringify(rowsToParamObject(editParamRows.value), null, 2);
  }
  editParamMode.value = mode;
}

function applyStyleToObject(obj, style) {
  if (style === "default") return { ...(obj || {}) };
  const out = {};
  const factor = style === "safe" ? 0.7 : 1.35;
  for (const [k, v] of Object.entries(obj || {})) {
    if (typeof v !== "number") {
      out[k] = v;
      continue;
    }
    let nv = v * factor;
    if (Number.isInteger(v)) {
      const delta = style === "safe" ? -2 : 2;
      nv = Math.max(1, Math.round(nv) + delta);
      const rule = PARAM_RULES[k];
      if (rule?.odd && nv % 2 === 0) nv += 1;
      if (rule?.min != null) nv = Math.max(rule.min, nv);
      if (rule?.max != null) nv = Math.min(rule.max, nv);
      if (rule?.odd && nv % 2 === 0) {
        if (rule?.max != null && nv >= rule.max) nv -= 1;
        else nv += 1;
      }
    } else {
      nv = Number(nv.toFixed(3));
      const rule = PARAM_RULES[k];
      if (rule?.min != null) nv = Math.max(rule.min, nv);
      if (rule?.max != null) nv = Math.min(rule.max, nv);
    }
    out[k] = nv;
  }
  return out;
}

function getAllowedParamKeysByTask(task) {
  const keys = new Set(TASK_PARAM_KEYS[task] || []);
  for (const p of PRESET_BY_TASK[task] || []) {
    for (const k of Object.keys(p?.defaultParams || {})) keys.add(k);
  }
  return [...keys];
}

function validateDefaultParamsByTask(task, presetKey, defaultParams) {
  if (!task) return "请先选择任务类别";
  const allowed = new Set(getAllowedParamKeysByTask(task));
  const entries = Object.entries(defaultParams || {});
  if (allowed.size === 0 && entries.length > 0) {
    return `任务“${task}”当前不接受参数，请清空默认参数(JSON)。`;
  }
  for (const [k] of entries) {
    if (!allowed.has(k)) {
      return `参数“${k}”不属于任务“${task}”可用参数，请检查参数名。`;
    }
  }
  const presets = PRESET_BY_TASK[task] || [];
  if (presets.length > 0) {
    const preset = presets.find((x) => x.key === presetKey);
    if (!preset) return "请选择有效的预设算法。";
    const presetKeys = new Set(Object.keys(preset.defaultParams || {}));
    for (const [k] of entries) {
      if (!presetKeys.has(k)) return `预设算法不支持参数“${k}”，请使用该预设的参数键。`;
    }
  }
  for (const [k, v] of entries) {
    const rule = PARAM_RULES[k];
    if (!rule) continue;
    if (rule.type === "number") {
      if (typeof v !== "number" || !Number.isFinite(v)) return `参数“${k}”必须是数字。`;
      if (rule.integer && !Number.isInteger(v)) return `参数“${k}”必须是整数。`;
      if (rule.odd && Number.isInteger(v) && v % 2 === 0) return `参数“${k}”必须是奇数。`;
      if (rule.min != null && v < rule.min) return `参数“${k}”不能小于 ${rule.min}。`;
      if (rule.max != null && v > rule.max) return `参数“${k}”不能大于 ${rule.max}。`;
    }
  }
  return "";
}

function applyParamStyle(scope, style) {
  const hint =
    style === "default"
      ? "已恢复为预设默认参数"
      : style === "safe"
        ? "已应用稳妥模式参数"
         : "已应用增强模式参数";
  if (scope === "create") {
    const p = (PRESET_BY_TASK[form.task] || []).find((x) => x.key === form.presetKey);
    const base = p?.defaultParams || rowsToParamObject(createParamRows.value);
    const next = applyStyleToObject(base, style);
    setCreateParamsObject(next);
    ElMessage({ type: "success", message: hint });
    return;
  }
  const p = (PRESET_BY_TASK[editForm.task] || []).find((x) => x.key === editForm.presetKey);
  const base = p?.defaultParams || rowsToParamObject(editParamRows.value);
  const next = applyStyleToObject(base, style);
  setEditParamsObject(next);
  ElMessage({ type: "success", message: hint });
}

function buildAlgorithmName(task, presetKey, customTag, fallbackName = "") {
  const preset = (PRESET_BY_TASK[task] || []).find((x) => x.key === presetKey);
  const base = String(preset?.name || fallbackName || "").trim();
  const tag = String(customTag || "").trim();
  if (!tag) return base || "未命名算法";
  return `${base || "未命名算法"}（${tag}）`;
}

function normalizeAlgorithmName(name) {
  return String(name || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function parseAlgorithmName(task, name) {
  const n = String(name || "").trim();
  const presets = PRESET_BY_TASK[task] || [];
  const sorted = [...presets].sort((a, b) => String(b?.name || "").length - String(a?.name || "").length);
  for (const p of sorted) {
    const pn = String(p?.name || "");
    if (!pn) continue;
    if (n === pn) return { presetKey: p.key, customTag: "" };
    const prefix = `${pn}（`;
    if (n.startsWith(prefix) && n.endsWith("）")) {
      return { presetKey: p.key, customTag: n.slice(prefix.length, -1) };
    }
  }
  return { presetKey: presets[0]?.key || "", customTag: n };
}

function _updatePresetOptions() {
  const a = PRESET_BY_TASK[form.task] || [];
  createPresetOptions.value = a;
  if (!a.some((x) => x.key === form.presetKey)) {
    form.presetKey = a[0]?.key || "";
  }

  const b = PRESET_BY_TASK[editForm.task] || [];
  editPresetOptions.value = b;
  if (!b.some((x) => x.key === editForm.presetKey)) {
    editForm.presetKey = b[0]?.key || "";
  }
}

onMounted(async () => {
  try {
    await store.fetchAlgorithms();
  } catch {
    // ignore
  }
  _updatePresetOptions();
});

const isEditing = ref(false);
const activeParamMode = computed({
  get: () => (isEditing.value ? editParamMode.value : createParamMode.value),
  set: (val) => (isEditing.value ? switchEditParamMode(val) : switchCreateParamMode(val)),
});
const editorVisible = computed({
  get: () => (isEditing.value ? showEdit.value : showCreate.value),
  set: (val) => {
    if (isEditing.value) showEdit.value = Boolean(val);
    else showCreate.value = Boolean(val);
  },
});
const activeParamRows = computed(() => (isEditing.value ? editParamRows.value : createParamRows.value));
const activeParamsText = computed({
  get: () => (isEditing.value ? editForm.defaultParamsText : form.defaultParamsText),
  set: (val) => (isEditing.value ? (editForm.defaultParamsText = val) : (form.defaultParamsText = val)),
});
const activePresetConstrained = computed(() => (isEditing.value ? isEditPresetConstrained.value : isCreatePresetConstrained.value));
const activeExplainList = computed(() => (isEditing.value ? getEditExplainList() : getCreateExplainList()));

function addActiveParamRow() {
  if (isEditing.value) addEditParamRow();
  else addCreateParamRow();
}
function removeActiveParamRow(idx) {
  if (isEditing.value) removeEditParamRow(idx);
  else removeCreateParamRow(idx);
}

function openCreate() {
  isEditing.value = false;
  createParamMode.value = "visual";
  suppressCreatePresetSync.value = true;
  form.task = "去噪";
  form.presetKey = "";
  form.name = "";
  form.customTag = "";
  form.impl = "OpenCV";
  form.version = "v1";
  setCreateParamsObject({});
  showCreate.value = true;
  _updatePresetOptions();
  const first = createPresetOptions.value?.[0]?.key || "";
  form.presetKey = first;
  suppressCreatePresetSync.value = false;
  const p = (PRESET_BY_TASK[form.task] || []).find((x) => x.key === form.presetKey);
  if (p) {
    form.name = p.name;
    form.impl = "OpenCV";
    setCreateParamsObject(p.defaultParams || {});
  }
}
function closeCreate() {
  showCreate.value = false;
}

function openEdit(a) {
  isEditing.value = true;
  editParamMode.value = "visual";
  suppressEditPresetSync.value = true;
  editForm.id = a?.id || "";
  editForm.task = a?.task || "去噪";
  editForm.name = a?.name || "";
  const parsed = parseAlgorithmName(editForm.task, editForm.name);
  editForm.presetKey = parsed.presetKey;
  editForm.customTag = parsed.customTag;
  editForm.impl = "OpenCV";
  editForm.version = a?.version || "v1";
  const obj =
    a?.defaultParams && typeof a.defaultParams === "object" && !Array.isArray(a.defaultParams)
      ? a.defaultParams
      : {};
  setEditParamsObject(obj);
  const presets = PRESET_BY_TASK[editForm.task] || [];
  const matched = presets.find((p) => p.key === editForm.presetKey) || null;
  if (!matched || !_isSameParamObject(obj, matched.defaultParams || {})) {
    editForm.customTag = String(editForm.customTag || "");
  }
  showEdit.value = true;
  _updatePresetOptions();
  suppressEditPresetSync.value = false;
}

function closeEdit() {
  showEdit.value = false;
}

async function askAlgorithmPublishSettings() {
  try {
    await ElMessageBox.confirm(
      "是否将这个新建算法发布到社区？发布后其他用户可以浏览和下载。",
      "发布设置",
      {
        type: "info",
        confirmButtonText: "发布",
        cancelButtonText: "仅自己可见",
        distinguishCancelAndClose: true,
      }
    );
  } catch (action) {
    if (action === "cancel" || action === "close") {
      return { visibility: "private", allowUse: false, allowDownload: false };
    }
    throw action;
  }
  return { visibility: "public", allowUse: true, allowDownload: true };
}

watch(
  () => form.task,
  () => {
    _updatePresetOptions();
    const presets = PRESET_BY_TASK[form.task] || [];
    if (!presets.some((x) => x.key === form.presetKey)) {
      form.presetKey = presets[0]?.key || "";
    }
    if (!form.presetKey && presets.length > 0) {
      form.presetKey = presets[0].key;
    }
  }
);
watch([filterTask, filterImpl, filterKeyword, pageSize], () => {
  currentPage.value = 1;
});
watch([filteredOwnedAlgorithms, pageCount], () => {
  if (currentPage.value > pageCount.value) currentPage.value = pageCount.value;
});

watch(
  () => form.presetKey,
  () => {
    if (suppressCreatePresetSync.value) return;
    const p = (PRESET_BY_TASK[form.task] || []).find((x) => x.key === form.presetKey);
    if (!p) return;
    form.name = p.name;
    form.impl = "OpenCV";
    setCreateParamsObject(p.defaultParams || {});
  }
);

watch(
  () => editForm.task,
  () => {
    _updatePresetOptions();
    const presets = PRESET_BY_TASK[editForm.task] || [];
    if (!presets.some((x) => x.key === editForm.presetKey)) {
      editForm.presetKey = presets[0]?.key || "";
    }
    if (!editForm.presetKey && presets.length > 0) {
      editForm.presetKey = presets[0].key;
    }
  }
);

watch(
  () => editForm.presetKey,
  () => {
    if (suppressEditPresetSync.value) return;
    const p = (PRESET_BY_TASK[editForm.task] || []).find((x) => x.key === editForm.presetKey);
    if (!p) return;
    editForm.name = p.name;
    editForm.impl = "OpenCV";
    setEditParamsObject(p.defaultParams || {});
  }
);

async function submitEdit() {
  if (!editForm.id) {
    ElMessage({ type: "warning", message: "缺少算法 ID" });
    return;
  }
  if (!editForm.name.trim()) {
    ElMessage({ type: "warning", message: "请填写算法名称" });
    return;
  }
  if (editParamMode.value === "visual") {
    editForm.defaultParamsText = JSON.stringify(rowsToParamObject(editParamRows.value), null, 2);
  }
  let defaultParams = {};
  try {
    const s = String(editForm.defaultParamsText || "").trim();
    defaultParams = s ? JSON.parse(s) : {};
  } catch (e) {
    ElMessage({ type: "error", message: "默认参数不是合法 JSON：" + String((e && e.message) || e) });
    return;
  }
  if (!defaultParams || typeof defaultParams !== "object" || Array.isArray(defaultParams)) {
    ElMessage({ type: "error", message: "默认参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }" });
    return;
  }
  const validateMsg = validateDefaultParamsByTask(editForm.task, editForm.presetKey, defaultParams);
  if (validateMsg) {
    ElMessage({ type: "error", message: validateMsg });
    return;
  }

  try {
    const finalName = buildAlgorithmName(editForm.task, editForm.presetKey, editForm.customTag, editForm.name);
    const dup = store.algorithms.find(
      (a) => String(a?.id || "") !== String(editForm.id || "") && normalizeAlgorithmName(a?.name || "") === normalizeAlgorithmName(finalName)
    );
    if (dup) {
      ElMessage({ type: "warning", message: "算法名称重复：已存在“" + String(dup.name || "") + "”" });
      return;
    }
    await store.updateAlgorithm(editForm.id, {
      task: editForm.task,
      name: finalName,
      impl: "OpenCV",
      version: editForm.version.trim() || "v1",
      defaultParams,
    });
    editorVisible.value = false;
    ElMessage({ type: "success", message: "算法已保存" });
  } catch (e) {
    ElMessage({ type: "error", message: "保存失败：" + String((e && e.message) || e) });
  }
}

async function submitCreate() {
  if (!String(form.customTag || "").trim()) {
    ElMessage({ type: "warning", message: "请填写自定义标识（创建必填）" });
    return;
  }
  if (createParamMode.value === "visual") {
    form.defaultParamsText = JSON.stringify(rowsToParamObject(createParamRows.value), null, 2);
  }
  let defaultParams = {};
  try {
    const s = String(form.defaultParamsText || "").trim();
    defaultParams = s ? JSON.parse(s) : {};
  } catch (e) {
    ElMessage({ type: "error", message: "默认参数不是合法 JSON：" + String((e && e.message) || e) });
    return;
  }
  if (!defaultParams || typeof defaultParams !== "object" || Array.isArray(defaultParams)) {
    ElMessage({ type: "error", message: "默认参数必须是 JSON 对象，例如：{ \"dcp_patch\": 15 }" });
    return;
  }
  const validateMsg = validateDefaultParamsByTask(form.task, form.presetKey, defaultParams);
  if (validateMsg) {
    ElMessage({ type: "error", message: validateMsg });
    return;
  }
  try {
    const finalName = buildAlgorithmName(form.task, form.presetKey, form.customTag, form.name);
    const dup = store.algorithms.find((a) => normalizeAlgorithmName(a?.name || "") === normalizeAlgorithmName(finalName));
    if (dup) {
      ElMessage({ type: "warning", message: "算法名称重复：已存在“" + String(dup.name || "") + "”" });
      return;
    }
    const created = await store.createAlgorithm({
      task: form.task,
      name: finalName,
      impl: "OpenCV",
      version: form.version.trim() || "v1",
      defaultParams,
      visibility: "private",
      allowUse: false,
      allowDownload: false,
    });
    const publishSettings = await askAlgorithmPublishSettings();
    await store.updateAlgorithm(created.id, publishSettings);
    await store.fetchAlgorithms();
    showCreate.value = false;
    ElMessage({ type: "success", message: publishSettings.visibility === "public" ? "算法已创建并发布到社区" : "算法已创建" });
  } catch (e) {
    ElMessage({ type: "error", message: "新增失败：" + String((e && e.message) || e) });
  }
}

function viewBuiltinParams(a) {
  const name = String(a?.name || "");
  const params = a?.defaultParams && typeof a.defaultParams === "object" ? a.defaultParams : {};
  paramDialogTitle.value = name;
  paramDialogId.value = String(a?.id || "");
  paramDialogTask.value = String(a?.task || "");
  paramDialogImpl.value = String(a?.impl || "");
  paramDialogVersion.value = String(a?.version || "");
  paramDialogExplainList.value = Object.keys(params).map((k) => getParamDoc(k)).filter(Boolean);
  paramDialogRows.value = Object.entries(params).map(([key, value]) => ({
    key,
    type: typeof value,
    text: typeof value === "object" ? JSON.stringify(value) : String(value),
  }));
  showParamDialog.value = true;
}

async function remove(id) {
  try {
    await ElMessageBox.confirm("确认删除该算法吗？", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    await store.removeAlgorithm(id);
    ElMessage({ type: "success", message: "算法已删除" });
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: "删除失败：" + String((e && e.message) || e) });
  }
}

async function handleAlgorithmAction(row, command) {
  if (command === "community") {
    await uploadAlgorithmToCommunity(row);
    return;
  }
  if (command === "export") {
    await exportAlgorithmToLocal(row);
    return;
  }
  if (command === "use") {
    router.push("/new-run");
    ElMessage({ type: "success", message: "已进入发起评测页面，请在任务中选择该算法使用" });
    return;
  }
  if (command === "edit") {
    openEdit(row);
    return;
  }
  if (command === "delete") {
    await remove(row?.id);
  }
}

async function handlePlatformAlgorithmAction(row, command) {
  if (command === "view") {
    viewBuiltinParams(row);
    return;
  }
  if (command === "edit") {
    openEdit(row);
    return;
  }
  if (command === "delete") {
    await remove(row?.id);
  }
}

async function exportAlgorithmToLocal(row) {
  const algorithmId = String(row?.id || "");
  if (!algorithmId) return;
  if (exportingAlgorithms.value.has(algorithmId)) return;
  try {
    const nextExporting = new Set(exportingAlgorithms.value);
    nextExporting.add(algorithmId);
    exportingAlgorithms.value = nextExporting;
    ElMessage({ type: "info", message: "正在准备下载算法，请稍候..." });
    const fallbackFilename = row?.archiveFilename || row?.raw?.archive_filename || `${algorithmId}.json`;
    const result = await algorithmsApi.exportAlgorithm(algorithmId, fallbackFilename);
    ElMessage({
      type: "success",
      message: result?.savedWithPicker ? "算法已保存到你选择的位置" : "算法已开始下载到本地",
    });
  } catch (e) {
    ElMessage({ type: "error", message: "下载到本地失败：" + String((e && e.message) || e) });
  } finally {
    const nextExporting = new Set(exportingAlgorithms.value);
    nextExporting.delete(algorithmId);
    exportingAlgorithms.value = nextExporting;
  }
}

async function uploadAlgorithmToCommunity(row) {
  if (!row?.id) return;
  const alreadyPublished = isSelfPublishedAlgorithm(row);
  try {
    const { value } = await ElMessageBox.prompt(
      "请输入算法在社区中心展示的描述。",
      alreadyPublished ? "更新社区信息" : "上传到社区",
      {
        inputType: "textarea",
        inputValue: String(row.description || ""),
        inputPlaceholder: "例如：适用于图像去噪任务，基于 OpenCV FastNLMeans 的实验版本。",
        confirmButtonText: alreadyPublished ? "保存" : "上传",
        cancelButtonText: "取消",
      }
    );
    await store.updateAlgorithm(row.id, {
      description: String(value || "").trim(),
      visibility: "public",
      allowUse: true,
      allowDownload: true,
    });
    ElMessage({ type: "success", message: alreadyPublished ? "社区信息已更新" : "算法已上传到社区" });
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: "上传社区失败：" + String((e && e.message) || e) });
  }
}

async function resetToBuiltins() {
  try {
    await ElMessageBox.confirm(
      "将删除所有用户新建算法，仅保留平台内置算法并重置默认参数，是否继续？",
      "重置确认",
      { type: "warning", confirmButtonText: "继续", cancelButtonText: "取消" }
    );
    await store.resetUserAlgorithms();
    currentPage.value = 1;
    ElMessage({ type: "success", message: "已清理用户算法并恢复内置算法默认参数。" });
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage({ type: "error", message: "清理失败：" + String((e && e.message) || e) });
  }
}
</script>

<style scoped>
.page {
  padding: 24px;
}

.header-section {
  margin-bottom: 24px;
}

.title {
  margin: 0 0 12px;
  font-size: 24px;
  font-weight: 700;
  color: #1f2f57;
}

.subtitle {
  color: #6a7ca9;
  font-size: 14px;
  line-height: 1.6;
  max-width: 800px;
}

.centered-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.action-btn {
  min-width: 132px;
  height: 42px;
  padding: 0 18px;
  border-radius: 12px;
}

.action-bar {
  background: #f8faff;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid #e6eeff;
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.history-tip {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #dbe7ff;
  background: #f7faff;
  color: #5d6c8c;
  line-height: 1.7;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex: 1;
  flex-wrap: wrap;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 20px;
  border-top: 1px dashed #dce7ff;
}

.filter-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1;
}

.reset-btn {
  margin-left: auto;
}

.filter-box {
  width: 160px;
}

.filter-input {
  width: 300px;
}

.section {
  margin-bottom: 40px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  color: #1f2f57;
  margin-bottom: 16px;
  font-weight: 700;
}

.data-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.data-table :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

.readonly-tag {
  margin-left: 8px;
}

.table-action-btn {
  min-width: 84px;
  justify-content: center;
}

.pagination-row {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 鍙傛暟璇︽儏寮圭獥 */
.param-desc {
  margin-bottom: 20px;
}

.param-section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2f57;
  margin: 20px 0 10px;
  padding-left: 10px;
  border-left: 4px solid #409eff;
}

.param-explain-list {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}

.param-kv-list {
  background: #f8faff;
  border: 1px solid #dce7ff;
  border-radius: 8px;
  padding: 12px;
}

.param-kv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  border-bottom: 1px dashed #e6eeff;
}

.param-kv-item:last-child {
  border-bottom: none;
}

.param-kv-key {
  min-width: 220px;
  font-weight: 700;
  color: #1f2f57;
}

.param-kv-type {
  min-width: 56px;
  font-size: 12px;
  color: #409eff;
  background: #ecf5ff;
  border-radius: 999px;
  text-align: center;
  padding: 2px 8px;
}

.param-kv-val {
  color: #303133;
  word-break: break-all;
}

.explain-item {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.explain-label {
  font-weight: 700;
  color: #1f2f57;
  margin-right: 4px;
}

.explain-key {
  color: #6a7ca9;
  font-family: monospace;
  margin-right: 8px;
}

.explain-usage {
  color: #606266;
}

/* 鏂板/缂栬緫寮圭獥甯冨眬 */
.algorithm-form-container {
  display: flex;
  gap: 30px;
}

.form-left {
  flex: 1;
  max-width: 400px;
}

.form-right {
  flex: 1.5;
  display: flex;
  flex-direction: column;
  background: #f8faff;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e6eeff;
}

.param-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.param-title {
  font-weight: 700;
  color: #1f2f57;
}

.param-actions {
  margin-bottom: 15px;
}

.param-editor {
  margin-bottom: 20px;
}

.param-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.param-doc-panel {
  background: white;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #dce7ff;
}

.doc-title {
  font-weight: 700;
  color: #1f2f57;
  margin-bottom: 10px;
  font-size: 13px;
}

.doc-list {
  max-height: 150px;
  overflow-y: auto;
}

.doc-item {
  margin-bottom: 6px;
  font-size: 12px;
}

.doc-label {
  font-weight: 700;
  color: #409eff;
  margin-right: 8px;
}

.doc-usage {
  color: #606266;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>






