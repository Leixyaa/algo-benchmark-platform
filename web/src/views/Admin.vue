<template>
  <div class="page">
    <div class="header-section">
      <h2 class="title">管理后台</h2>
      <div class="subtitle">管理员可以在这里下架社区资源、处理举报，并在资源详情中删除违规评论。</div>
    </div>

    <el-alert
      v-if="store.user.role !== 'admin'"
      type="warning"
      :closable="false"
      title="当前账号不是管理员，无法使用后台治理能力。"
      class="warn-box"
    />

    <el-tabs v-model="tab" class="resource-tabs">

      <el-tab-pane label="注册用户" name="users">
        <div class="toolbar">
          <el-input v-model="userKeyword" placeholder="搜索用户名 / 显示名 / 角色" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="filteredRegisteredUsers"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="username" label="用户名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="displayName" label="显示名" min-width="180" show-overflow-tooltip />
          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              {{ row.role === "admin" ? "管理员" : "普通用户" }}
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="注册时间" width="180" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="社区算法" name="algorithms">
        <div class="toolbar">
          <el-input v-model="algorithmKeyword" placeholder="搜索算法名称或上传者" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="filteredAlgorithms"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="name" label="算法名称" min-width="220" />
          <el-table-column prop="task" label="任务" width="120" />
          <el-table-column prop="uploaderId" label="上传者" width="140" :formatter="userLabelCell" />
          <el-table-column prop="downloadCount" label="下载量" width="100" />
          <el-table-column prop="createdAt" label="发布时间" width="180" />
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button size="small" plain @click="openResourceDetail('algorithm', row)">详情</el-button>
              <el-button
                size="small"
                type="primary"
                plain
                @click="promoteCommunityAlgorithm(row)"
                :loading="promotingAlgorithmIds.has(row.id)"
              >
                收录为平台算法
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="takedownAlgorithm(row)"
                :loading="loadingAlgorithmIds.has(row.id)"
              >
                下架
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="社区数据集" name="datasets">
        <div class="toolbar">
          <el-input v-model="datasetKeyword" placeholder="搜索数据集名称或上传者" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="filteredDatasets"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="name" label="数据集名称" min-width="220" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="size" label="规模" width="140" />
          <el-table-column prop="uploaderId" label="上传者" width="140" :formatter="userLabelCell" />
          <el-table-column prop="downloadCount" label="下载量" width="100" />
          <el-table-column prop="createdAt" label="发布时间" width="180" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" plain @click="openResourceDetail('dataset', row)">详情</el-button>
              <el-button
                size="small"
                type="danger"
                @click="takedownDataset(row)"
                :loading="loadingDatasetIds.has(row.id)"
              >
                下架
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="指标审核" name="metrics">
        <div class="toolbar">
          <el-input v-model="metricKeyword" placeholder="搜索指标名称 / 标识 / 提交人" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="filteredMetrics"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="displayName" label="指标名称" min-width="160" />
          <el-table-column prop="metricKey" label="指标标识" width="150" />
          <el-table-column label="适用任务" min-width="180">
            <template #default="{ row }">
              {{ formatTaskTypes(row.taskTypes) }}
            </template>
          </el-table-column>
          <el-table-column label="方向" width="110">
            <template #default="{ row }">
              {{ row.direction === "lower_better" ? "越小越好" : "越大越好" }}
            </template>
          </el-table-column>
          <el-table-column prop="uploaderId" label="提交人" width="140" :formatter="userLabelCell" />
          <el-table-column label="代码文件" width="180">
            <template #default="{ row }">
              {{ row.codeFilename || "-" }}
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="提交时间" width="180" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="openMetricReview(row)" :loading="reviewingMetricIds.has(row.id)">
                审核
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="算法接入审核" name="algorithm-submissions">
        <div class="toolbar">
          <el-input
            v-model="algorithmSubmissionKeyword"
            placeholder="搜索算法名称 / 任务 / 提交人 / 文件名"
            clearable
            class="search-input"
          />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="filteredAlgorithmSubmissions"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="name" label="算法名称" min-width="180" />
          <el-table-column prop="taskLabel" label="任务" width="110" />
          <el-table-column prop="uploaderId" label="提交人" width="140" :formatter="userLabelCell" />
          <el-table-column prop="archiveFilename" label="代码包" min-width="180" show-overflow-tooltip />
          <el-table-column prop="version" label="版本" width="100" />
          <el-table-column label="运行链路" width="110">
            <template #default="{ row }">
              <el-tag :type="row.runtimeReady ? 'success' : 'info'">{{ row.runtimeReady ? "已接入" : "未接入" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="提交时间" width="180" />
          <el-table-column label="操作" width="190">
            <template #default="{ row }">
              <el-button size="small" plain @click="downloadAlgorithmSubmission(row)">下载代码包</el-button>
              <el-button
                size="small"
                type="primary"
                @click="openAlgorithmSubmissionReview(row)"
                :loading="reviewingSubmissionIds.has(row.id)"
              >
                审核
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="举报处理" name="reports">
        <div class="toolbar">
          <el-input v-model="pendingReportKeyword" placeholder="搜索待处理举报对象 / 举报人 / 原因" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="pendingReports"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="targetTypeLabel" label="举报类型" width="120" />
          <el-table-column prop="targetId" label="举报对象ID" min-width="180" />
          <el-table-column prop="reporterId" label="举报人" width="140" :formatter="userLabelCell" />
          <el-table-column prop="reason" label="举报原因" min-width="260" show-overflow-tooltip />
          <el-table-column prop="createdAt" label="举报时间" width="180" />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                @click="openReportProcess(row)"
                :loading="resolvingReportIds.has(row.reportId)"
              >
                处理
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="指标处理日志" name="metric-logs">
        <div class="toolbar">
          <el-input v-model="metricLogKeyword" placeholder="搜索指标名称 / 标识 / 提交人 / 处理人" clearable class="search-input" />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="handledMetricLogs"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="name" label="指标名称" min-width="180" />
          <el-table-column prop="targetId" label="指标标识" min-width="180" />
          <el-table-column prop="submitterId" label="提交人" width="140" :formatter="userLabelCell" />
          <el-table-column prop="statusLabel" label="状态" width="100" />
          <el-table-column prop="resolution" label="处理说明" min-width="260" show-overflow-tooltip />
          <el-table-column prop="resolvedBy" label="处理人" width="120" :formatter="userLabelCell" />
          <el-table-column prop="resolvedAt" label="处理时间" width="180" />
          <el-table-column prop="createdAt" label="提交时间" width="180" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="算法接入日志" name="algorithm-submission-logs">
        <div class="toolbar">
          <el-input
            v-model="algorithmSubmissionLogKeyword"
            placeholder="搜索算法名称 / 提交人 / 审核人 / 收录结果"
            clearable
            class="search-input"
          />
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="handledAlgorithmSubmissionLogs"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="name" label="算法名称" min-width="180" />
          <el-table-column prop="taskLabel" label="任务" width="110" />
          <el-table-column prop="submitterId" label="提交人" width="140" :formatter="userLabelCell" />
          <el-table-column prop="archiveFilename" label="代码包" min-width="170" show-overflow-tooltip />
          <el-table-column prop="statusLabel" label="状态" width="100" />
          <el-table-column prop="resolution" label="审核说明" min-width="220" show-overflow-tooltip />
          <el-table-column label="运行接入" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.runtimeReady" type="success">已接入</el-tag>
              <el-tag v-else type="info">未接入</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="platformAlgorithmId" label="平台算法" min-width="170" />
          <el-table-column prop="resolvedBy" label="审核人" width="120" :formatter="userLabelCell" />
          <el-table-column prop="resolvedAt" label="审核时间" width="180" />
          <el-table-column prop="createdAt" label="提交时间" width="180" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="处理日志" name="report-logs">
        <div class="toolbar">
          <el-input v-model="reportLogKeyword" placeholder="搜索处理记录 / 处理人 / 理由" clearable class="search-input" />
          <el-button
            plain
            class="clear-btn"
            @click="clearHandledReports"
            :disabled="!handledReports.length"
            :loading="clearingReports"
          >
            清除举报记录
          </el-button>
        </div>
        <el-table
          v-loading="adminDataLoading"
          element-loading-text="加载中..."
          :data="handledReports"
          border
          stripe
          class="data-table"
        >
          <el-table-column prop="targetTypeLabel" label="举报类型" width="120" />
          <el-table-column prop="targetId" label="举报对象ID" min-width="180" />
          <el-table-column prop="reporterId" label="举报人" width="140" :formatter="userLabelCell" />
          <el-table-column prop="reason" label="举报原因" min-width="220" show-overflow-tooltip />
          <el-table-column prop="statusLabel" label="状态" width="100" />
          <el-table-column prop="resolution" label="处理理由" min-width="260" show-overflow-tooltip />
          <el-table-column prop="resolvedBy" label="处理人" width="120" :formatter="userLabelCell" />
          <el-table-column prop="resolvedAt" label="处理时间" width="180" />
          <el-table-column prop="createdAt" label="举报时间" width="180" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" :title="detailTitle" width="820px">
      <div v-if="detailItem" class="detail-panel">
        <div class="detail-summary">
          <div class="detail-name">{{ detailItem.name }}</div>
          <div class="detail-meta">
            <span>上传者：{{ userLabelById(detailItem.uploaderId || "") }}</span>
            <span>下载量：{{ detailItem.downloadCount ?? 0 }}</span>
            <span>发布时间：{{ detailItem.createdAt || "-" }}</span>
          </div>
          <div class="detail-meta">
            <span v-if="detailType === 'algorithm'">任务：{{ detailItem.task || "-" }}</span>
            <span v-if="detailType === 'dataset'">类型：{{ detailItem.type || "-" }}</span>
            <span v-if="detailType === 'dataset'">规模：{{ detailItem.size || "-" }}</span>
          </div>
        </div>

        <div class="detail-block">
          <div class="block-title">详细描述</div>
          <div class="description-box">{{ detailItem.description || "暂无描述" }}</div>
        </div>

        <div class="detail-block">
          <div class="block-title">评论列表</div>
          <div v-if="!detailComments.length" class="empty-text">当前资源暂无评论。</div>
          <div v-for="comment in detailComments" :key="comment.commentId" class="comment-item">
            <div class="comment-head">
              <div class="comment-head-left">
                <span class="comment-author">{{ comment.authorId }}</span>
                <span class="comment-time">{{ comment.createdAt }}</span>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                @click="deleteComment(comment)"
                :loading="deletingCommentIds.has(comment.commentId)"
              >
                删除评论
              </el-button>
            </div>
            <div class="comment-content">{{ comment.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="reportProcessVisible" title="处理举报" width="640px">
      <div v-if="activeReport" class="process-panel">
        <div class="process-meta">
          <div>举报类型：{{ activeReport.targetTypeLabel }}</div>
          <div>举报对象ID：{{ activeReport.targetId }}</div>
          <div>举报人：{{ userLabelById(activeReport.reporterId) }}</div>
        </div>

        <div v-if="reportTargetDetail" class="process-detail-card">
          <div class="process-detail-head">
            <div class="process-detail-title">资源详情</div>
            <template v-if="activeReport.targetType === 'dataset' && reportTargetDetail.storagePath">
              <el-button size="small" plain @click="copyDatasetPath(reportTargetDetail.storagePath)">复制路径</el-button>
              <el-button size="small" type="primary" plain @click="openDatasetFolder(reportTargetDetail.storagePath)">
                打开文件夹
              </el-button>
            </template>
          </div>

          <div class="process-detail-grid">
            <div>名称：{{ reportTargetDetail.name || "-" }}</div>
            <div>上传者：{{ userLabelById(reportTargetDetail.uploaderId || "") }}</div>
            <div v-if="activeReport.targetType !== 'comment'">下载量：{{ reportTargetDetail.downloadCount ?? 0 }}</div>
            <div v-if="reportTargetDetail.createdAt">发布时间：{{ reportTargetDetail.createdAt }}</div>
            <div v-if="reportTargetDetail.task">任务：{{ reportTargetDetail.task }}</div>
            <div v-if="reportTargetDetail.type">类型：{{ reportTargetDetail.type }}</div>
            <div v-if="reportTargetDetail.size">规模：{{ reportTargetDetail.size }}</div>
          </div>

          <div class="process-detail-desc">{{ reportTargetDetail.description || "暂无描述" }}</div>
          <div
            v-if="activeReport.targetType === 'dataset' && reportTargetDetail.storagePath"
            class="process-path"
          >
            平台路径：{{ reportTargetDetail.storagePath }}
          </div>
          <div v-if="activeReport.targetType === 'comment' && reportTargetComment" class="process-comment-box">
            被举报评论：{{ reportTargetComment.content || "-" }}
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item label="处理动作">
            <el-select v-model="reportProcessAction" class="full-width">
              <el-option label="驳回举报" value="reject" />
              <el-option label="仅标记已处理" value="resolve" />
              <el-option v-if="activeReport.targetType === 'algorithm'" label="下架该算法" value="takedown_algorithm" />
              <el-option v-if="activeReport.targetType === 'dataset'" label="下架该数据集" value="takedown_dataset" />
              <el-option v-if="activeReport.targetType === 'comment'" label="删除该评论" value="delete_comment" />
            </el-select>
          </el-form-item>
          <el-form-item label="处理说明">
            <el-input
              v-model="reportProcessNote"
              type="textarea"
              :rows="4"
              placeholder="填写处理结果，便于后续留痕和通知举报人。"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeReportProcess">取消</el-button>
        <el-button type="primary" @click="submitReportProcess" :loading="reportProcessSubmitting">确认处理</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="metricReviewVisible" title="审核指标" width="640px">
      <div v-if="activeMetric" class="process-panel">
        <div class="process-meta">
          <div>指标名称：{{ activeMetric.displayName }}</div>
          <div>指标标识：{{ activeMetric.metricKey }}</div>
          <div>提交人：{{ userLabelById(activeMetric.uploaderId) }}</div>
        </div>
        <div class="detail-block">
          <div class="block-title">指标说明</div>
          <div class="description-box">{{ activeMetric.description || "暂无说明" }}</div>
          <div class="detail-grid">
            <div>适用任务：{{ formatTaskTypes(activeMetric.taskTypes) }}</div>
            <div>指标方向：{{ activeMetric.direction === "lower_better" ? "越小越好" : "越大越好" }}</div>
            <div>是否需要 GT：{{ activeMetric.requiresReference ? "需要" : "不需要" }}</div>
            <div>实现方式：{{ activeMetric.implementationType === "formula" ? "公式/说明" : activeMetric.implementationType === "builtin" ? "内置" : "Python 代码" }}</div>
          </div>
        </div>
        <div v-if="activeMetric.formulaText" class="detail-block">
          <div class="block-title">公式说明</div>
          <div class="description-box code-box">{{ activeMetric.formulaText }}</div>
        </div>
        <div v-if="activeMetric.codeText" class="detail-block">
          <div class="block-title">代码内容</div>
          <div class="description-box code-box">{{ activeMetric.codeText }}</div>
        </div>
        <div v-if="activeMetric.codeText || activeMetric.codeFilename" class="detail-block">
          <div class="block-title">{{ activeMetric.codeFilename ? "原始上传文件" : "代码内容导出" }}</div>
          <div class="file-preview-row">
            <div class="description-box">
              {{ activeMetric.codeFilename || "当前未上传独立文件，可导出本次提交的代码内容" }}
            </div>
            <el-button size="small" plain @click="downloadMetricCode(activeMetric)">
              {{ activeMetric.codeFilename ? "下载原始文件" : "下载代码内容" }}
            </el-button>
          </div>
        </div>
        <div class="detail-block">
          <div class="block-title">自定义指标代码协议</div>
          <div class="description-box protocol-box">
            <div>1. 仅 `Python 代码` 指标可接入运行链路，`公式/说明型` 仅用于存档与审核。</div>
            <div>2. 代码中需定义 `compute_metric(...)` 函数，并返回单个数值结果。</div>
            <div>3. 推荐签名：`def compute_metric(gt_bgr_u8, pred_bgr_u8, sample_name="", task_type=""):`</div>
            <div>4. `gt_bgr_u8` 在“需要 GT”时提供；无 GT 指标应只使用 `pred_bgr_u8`。</div>
            <div>5. 运行环境已注入 `np`、`cv2`、`math` 等常用对象，返回值必须是有限数值。</div>
          </div>
        </div>
        <el-form label-position="top">
          <el-form-item label="审核结论">
            <el-select v-model="metricReviewStatus" class="full-width">
              <el-option label="通过" value="approved" />
              <el-option label="驳回" value="rejected" />
            </el-select>
          </el-form-item>
          <el-form-item label="接入运行链路">
            <el-switch v-model="metricReviewRuntimeReady" :disabled="activeMetric.implementationType === 'formula'" />
          </el-form-item>
          <el-form-item label="审核说明">
            <el-input v-model="metricReviewNote" type="textarea" :rows="4" placeholder="填写审核意见与接入说明。" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeMetricReview">取消</el-button>
        <el-button type="primary" @click="submitMetricReview" :loading="metricReviewSubmitting">提交审核</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="submissionReviewVisible" title="审核算法接入申请" width="680px">
      <div v-if="activeSubmission" class="process-panel">
        <div class="process-meta">
          <div>算法名称：{{ activeSubmission.name }}</div>
          <div>任务：{{ activeSubmission.taskLabel }}</div>
          <div>提交人：{{ userLabelById(activeSubmission.uploaderId) }}</div>
        </div>

        <div class="detail-block">
          <div class="block-title">提交说明</div>
          <div class="detail-grid">
            <div>版本：{{ activeSubmission.version || "-" }}</div>
            <div>代码包：{{ activeSubmission.archiveFilename || "-" }}</div>
            <div>提交时间：{{ activeSubmission.createdAt || "-" }}</div>
            <div>SHA256：{{ activeSubmission.archiveSha256 || "-" }}</div>
          </div>
        </div>

        <div class="detail-block">
          <div class="block-title">算法描述</div>
          <div class="description-box">{{ activeSubmission.description || "暂无说明" }}</div>
        </div>

        <div class="detail-block">
          <div class="block-title">依赖说明</div>
          <div class="description-box">{{ activeSubmission.dependencyText || "暂无依赖说明" }}</div>
        </div>

        <div class="detail-block">
          <div class="block-title">入口说明</div>
          <div class="description-box">{{ activeSubmission.entryText || "暂无入口说明" }}</div>
        </div>

        <div class="file-preview-row">
          <div class="description-box">{{ activeSubmission.archiveFilename || "当前未上传文件" }}</div>
          <el-button size="small" plain @click="downloadAlgorithmSubmission(activeSubmission)">下载代码包</el-button>
        </div>

        <el-form label-position="top">
          <el-form-item label="审核结论">
            <el-select v-model="submissionReviewStatus" class="full-width">
              <el-option label="通过" value="approved" />
              <el-option label="驳回" value="rejected" />
            </el-select>
          </el-form-item>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="审核通过只保存申请留档与运行接入状态；进入平台算法库需在接入日志中单独收录。"
          />
          <el-form-item label="接入运行链路">
            <el-switch
              v-model="submissionReviewRuntimeReady"
              :disabled="submissionReviewStatus !== 'approved'"
            />
          </el-form-item>
          <el-form-item label="审核说明">
            <el-input v-model="submissionReviewNote" type="textarea" :rows="4" placeholder="填写审核结论、接入建议或驳回原因。" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeAlgorithmSubmissionReview">取消</el-button>
        <el-button type="primary" @click="submitAlgorithmSubmissionReview" :loading="submissionReviewSubmitting">提交审核</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
export default { name: "Admin" };
</script>
<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "../api/admin";
import { algorithmSubmissionsApi } from "../api/algorithmSubmissions";
import { TASK_LABEL_BY_TYPE, toTaskType, useAppStore } from "../stores/app";

const store = useAppStore();

const tab = ref("algorithms");
const registeredUsers = ref([]);
const algorithms = ref([]);
const datasets = ref([]);
const metrics = ref([]);
const algorithmSubmissions = ref([]);
const comments = ref([]);
const reports = ref([]);
/** 首屏与各 tab 表格共用数据源，请求未完成前避免误显示空表 / No Data */
const adminDataLoading = ref(true);

const userKeyword = ref("");
const algorithmKeyword = ref("");
const datasetKeyword = ref("");
const metricKeyword = ref("");
const algorithmSubmissionKeyword = ref("");
const algorithmSubmissionLogKeyword = ref("");
const metricLogKeyword = ref("");
const pendingReportKeyword = ref("");
const reportLogKeyword = ref("");

const loadingAlgorithmIds = ref(new Set());
const loadingDatasetIds = ref(new Set());
const deletingCommentIds = ref(new Set());
const resolvingReportIds = ref(new Set());
const promotingAlgorithmIds = ref(new Set());
const promotingSubmissionIds = ref(new Set());
const clearingReports = ref(false);
const reviewingMetricIds = ref(new Set());
const reviewingSubmissionIds = ref(new Set());

const detailVisible = ref(false);
const detailType = ref("algorithm");
const detailItem = ref(null);

const reportProcessVisible = ref(false);
const activeReport = ref(null);
const reportProcessAction = ref("resolve");
const reportProcessNote = ref("");
const reportProcessSubmitting = ref(false);
const reportTargetDetail = ref(null);
const reportTargetComment = ref(null);
const metricReviewVisible = ref(false);
const activeMetric = ref(null);
const metricReviewStatus = ref("approved");
const metricReviewRuntimeReady = ref(false);
const metricReviewNote = ref("");
const metricReviewSubmitting = ref(false);
const submissionReviewVisible = ref(false);
const activeSubmission = ref(null);
const submissionReviewStatus = ref("approved");
const submissionReviewRuntimeReady = ref(false);
const submissionReviewNote = ref("");
const submissionReviewSubmitting = ref(false);

function formatTs(unixSeconds) {
  if (!unixSeconds) return "-";
  const d = new Date(Number(unixSeconds) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function setLoading(setRef, id, loading) {
  const next = new Set(setRef.value);
  if (loading) next.add(String(id));
  else next.delete(String(id));
  setRef.value = next;
}

function includesKeyword(parts, keyword) {
  const kw = String(keyword || "").trim().toLowerCase();
  if (!kw) return true;
  return parts.join(" ").toLowerCase().includes(kw);
}

const userDisplayNameMap = computed(() => {
  const map = new Map();
  for (const row of registeredUsers.value || []) {
    const username = String(row?.username || "").trim();
    if (!username) continue;
    const displayName = String(row?.displayName || "").trim();
    map.set(username, displayName || username);
  }
  return map;
});

function userLabelById(userId) {
  const id = String(userId || "").trim();
  if (!id) return "-";
  if (id === "system") return "系统";
  return userDisplayNameMap.value.get(id) || id;
}

function userLabelCell(_row, _column, cellValue) {
  return userLabelById(cellValue);
}

const filteredRegisteredUsers = computed(() => {
  const kw = String(userKeyword.value || "").trim().toLowerCase();
  const rows = registeredUsers.value || [];
  if (!kw) return rows;
  return rows.filter((row) =>
    includesKeyword(
      [row.username, row.displayName, row.role === "admin" ? "管理员" : "普通用户", row.role || ""],
      kw
    )
  );
});

function mapAlgorithm(x) {
  return {
    id: x.algorithm_id,
    name: x.name,
    task: x.task,
    description: x.description || "",
    uploaderId: String(x.owner_id || ""),
    sourceSubmissionId: String(x.source_submission_id || ""),
    sourceUploaderId: String(x.source_owner_id || ""),
    sourceAlgorithmId: String(x.source_algorithm_id || ""),
    packageRole: String(x.package_role || ""),
    downloadCount: Number(x.download_count || 0),
    createdAt: formatTs(x.created_at),
    storagePath: "",
  };
}

function mapDataset(x) {
  return {
    id: x.dataset_id,
    name: x.name,
    type: x.type,
    size: x.size,
    description: x.description || "",
    uploaderId: String(x.owner_id || ""),
    downloadCount: Number(x.download_count || 0),
    createdAt: formatTs(x.created_at),
    storagePath: x.storage_path || "",
  };
}

function mapMetric(x) {
  return {
    id: x.metric_id,
    metricKey: String(x.metric_key || ""),
    name: String(x.name || ""),
    displayName: String(x.display_name || x.name || x.metric_key || ""),
    description: String(x.description || ""),
    taskTypes: Array.isArray(x.task_types) ? x.task_types : [],
    direction: String(x.direction || "higher_better"),
    requiresReference: Boolean(x.requires_reference),
    implementationType: String(x.implementation_type || "python"),
    formulaText: String(x.formula_text || ""),
    codeText: String(x.code_text || ""),
    codeFilename: String(x.code_filename || ""),
    uploaderId: String(x.owner_id || ""),
    status: String(x.status || "pending"),
    runtimeReady: Boolean(x.runtime_ready),
    reviewNote: String(x.review_note || ""),
    reviewedBy: String(x.reviewed_by || ""),
    reviewedAt: x.reviewed_at ? formatTs(x.reviewed_at) : "",
    createdAt: formatTs(x.created_at),
  };
}

function mapAlgorithmSubmission(x) {
  return {
    id: String(x.submission_id || ""),
    taskType: String(x.task_type || ""),
    taskLabel: String(x.task_label || TASK_LABEL_BY_TYPE[x.task_type] || x.task_type || ""),
    name: String(x.name || ""),
    version: String(x.version || ""),
    description: String(x.description || ""),
    dependencyText: String(x.dependency_text || ""),
    entryText: String(x.entry_text || ""),
    archiveFilename: String(x.archive_filename || ""),
    archiveSize: Number(x.archive_size || 0),
    archiveSha256: String(x.archive_sha256 || ""),
    uploaderId: String(x.owner_id || ""),
    status: String(x.status || "pending"),
    reviewNote: String(x.review_note || ""),
    reviewedBy: String(x.reviewed_by || ""),
    reviewedAt: x.reviewed_at ? formatTs(x.reviewed_at) : "",
    createdAt: formatTs(x.created_at),
    runtimeReady: Boolean(x.runtime_ready),
    ownerAlgorithmId: String(x.owner_algorithm_id || ""),
    platformAlgorithmId: String(x.platform_algorithm_id || ""),
  };
}

function mapComment(x) {
  const resourceType = String(x.resource_type || "");
  return {
    commentId: x.comment_id,
    resourceType,
    resourceTypeLabel: resourceType === "algorithm" ? "算法" : "数据集",
    resourceId: x.resource_id,
    authorId: x.author_id,
    content: x.content,
    createdAt: formatTs(x.created_at),
  };
}

function mapReport(x) {
  const targetType = String(x.target_type || "");
  const targetTypeLabel =
    targetType === "algorithm" ? "算法" :
    targetType === "dataset" ? "数据集" :
    "评论";
  const status = String(x.status || "pending");
  return {
    reportId: x.report_id,
    targetType,
    targetTypeLabel,
    targetId: x.target_id,
    resourceType: x.resource_type || "",
    resourceId: x.resource_id || "",
    reporterId: x.reporter_id,
    reason: x.reason,
    status,
    statusLabel: status === "resolved" ? "已处理" : status === "rejected" ? "已驳回" : "待处理",
    resolution: String(x.resolution || ""),
    resolvedBy: String(x.resolved_by || ""),
    resolvedAt: x.resolved_at ? formatTs(x.resolved_at) : "",
    createdAt: formatTs(x.created_at),
  };
}

function getReportProcessTemplate(action) {
  const key = String(action || "resolve");
  if (key === "reject") return "经核实，当前举报内容不成立，已驳回。";
  if (key === "takedown_algorithm") return "经核实，该算法存在违规问题，已下架处理。";
  if (key === "takedown_dataset") return "经核实，该数据集存在违规问题，已下架处理。";
  if (key === "delete_comment") return "经核实，该评论存在违规内容，已删除处理。";
  return "管理员已核实并处理该举报。";
}

const filteredAlgorithms = computed(() =>
  (algorithms.value || []).filter((item) =>
    includesKeyword([item.name, item.task, item.uploaderId, userLabelById(item.uploaderId)], algorithmKeyword.value)
  )
);

const filteredDatasets = computed(() =>
  (datasets.value || []).filter((item) =>
    includesKeyword([item.name, item.type, item.uploaderId, userLabelById(item.uploaderId)], datasetKeyword.value)
  )
);

const filteredMetrics = computed(() =>
  (metrics.value || []).filter((item) =>
    String(item.status || "") === "pending" &&
    includesKeyword([item.displayName, item.metricKey, item.uploaderId, userLabelById(item.uploaderId), item.description], metricKeyword.value)
  )
);

const filteredAlgorithmSubmissions = computed(() =>
  (algorithmSubmissions.value || []).filter((item) =>
    String(item.status || "") === "pending" &&
    includesKeyword(
      [item.name, item.taskLabel, item.uploaderId, userLabelById(item.uploaderId), item.archiveFilename, item.description, item.dependencyText, item.entryText],
      algorithmSubmissionKeyword.value
    )
  )
);

const pendingReports = computed(() =>
  (reports.value || []).filter(
    (item) =>
      String(item.status || "") === "pending" &&
      includesKeyword([item.targetTypeLabel, item.targetId, item.reporterId, userLabelById(item.reporterId), item.reason], pendingReportKeyword.value)
  )
);

const handledReports = computed(() =>
  (reports.value || []).filter(
    (item) =>
      String(item.status || "") !== "pending" &&
      includesKeyword(
        [item.targetTypeLabel, item.targetId, item.reporterId, userLabelById(item.reporterId), item.reason, item.resolution, item.resolvedBy, userLabelById(item.resolvedBy)],
        reportLogKeyword.value
      )
  )
);

const handledMetricLogs = computed(() =>
  (metrics.value || []).filter(
    (item) =>
      String(item.status || "") !== "pending" &&
      includesKeyword(
        [item.displayName, item.metricKey, item.uploaderId, userLabelById(item.uploaderId), item.reviewNote, item.reviewedBy, userLabelById(item.reviewedBy)],
        metricLogKeyword.value
      )
  ).map((item) => ({
    name: item.displayName,
    targetId: item.metricKey,
    submitterId: item.uploaderId,
    statusLabel: metricStatusLabel(item.status),
    resolution: item.reviewNote || "-",
    resolvedBy: item.reviewedBy || "-",
    resolvedAt: item.reviewedAt || "-",
    createdAt: item.createdAt,
  }))
);

const handledAlgorithmSubmissionLogs = computed(() =>
  (algorithmSubmissions.value || []).filter(
    (item) =>
      String(item.status || "") !== "pending" &&
      includesKeyword(
        [
          item.name,
          item.taskLabel,
          item.uploaderId,
          userLabelById(item.uploaderId),
          item.archiveFilename,
          item.reviewNote,
          item.reviewedBy,
          userLabelById(item.reviewedBy),
          item.platformAlgorithmId,
          item.runtimeReady ? "已接入" : "未接入",
        ],
        algorithmSubmissionLogKeyword.value
      )
  ).map((item) => ({
    id: item.id,
    status: item.status,
    name: item.name,
    taskLabel: item.taskLabel,
    submitterId: item.uploaderId,
    archiveFilename: item.archiveFilename || "-",
    statusLabel: metricStatusLabel(item.status),
    resolution: item.reviewNote || "-",
    runtimeReady: item.runtimeReady,
    platformAlgorithmRawId: item.platformAlgorithmId,
    platformAlgorithmId: item.platformAlgorithmId || "-",
    canPromoteToPlatform: item.status === "approved" && item.runtimeReady && !item.platformAlgorithmId,
    resolvedBy: item.reviewedBy || "-",
    resolvedAt: item.reviewedAt || "-",
    createdAt: item.createdAt,
  }))
);

const detailTitle = computed(() => (detailType.value === "algorithm" ? "算法详情" : "数据集详情"));





const detailComments = computed(() =>
  (comments.value || []).filter(
    (item) =>
      String(item.resourceType || "") === String(detailType.value || "") &&
      String(item.resourceId || "") === String(detailItem.value?.id || "")
  )
);

async function loadAll() {
  if (store.user.role !== "admin") {
    adminDataLoading.value = false;
    return;
  }
  adminDataLoading.value = true;
  try {
    const [userRes, algRes, dsRes, metricRes, submissionRes, commentRes, reportRes] = await Promise.all([
      adminApi.listRegisteredUsers(),
      adminApi.listCommunityAlgorithms(),
      adminApi.listCommunityDatasets(),
      adminApi.listMetrics(),
      adminApi.listAlgorithmSubmissions(),
      adminApi.listComments(),
      adminApi.listReports(),
    ]);
    registeredUsers.value = (userRes || []).map((x) => ({
      username: String(x.username || ""),
      displayName: String(x.display_name || ""),
      role: String(x.role || "user"),
      createdAt: formatTs(x.created_at),
    }));
    algorithms.value = (algRes || []).map(mapAlgorithm);
    datasets.value = (dsRes || []).map(mapDataset);
    metrics.value = (metricRes || []).map(mapMetric).filter((item) => item.uploaderId !== "system");
    algorithmSubmissions.value = (submissionRes || []).map(mapAlgorithmSubmission);
    comments.value = (commentRes || []).map(mapComment);
    reports.value = (reportRes || []).map(mapReport);
  } catch (e) {
    ElMessage({ type: "error", message: `加载管理数据失败：${e?.message || e}` });
  } finally {
    adminDataLoading.value = false;
  }
}



function openResourceDetail(type, row) {
  detailType.value = type;
  detailItem.value = row;
  detailVisible.value = true;
}

async function takedownAlgorithm(row) {
  try {
    setLoading(loadingAlgorithmIds, row.id, true);
    await adminApi.takedownAlgorithm(row.id);
    algorithms.value = algorithms.value.filter((item) => item.id !== row.id);
    ElMessage.success("算法已下架");
  } catch (e) {
    ElMessage.error(e?.message || "算法下架失败");
  } finally {
    setLoading(loadingAlgorithmIds, row.id, false);
  }
}


async function promoteCommunityAlgorithm(row) {
  try {
    setLoading(promotingAlgorithmIds, row.id, true);
    await adminApi.promoteCommunityAlgorithm(row.id);
    await Promise.all([
      loadAll(),
      store.fetchAlgorithms(500, { force: true }),
    ]);
    ElMessage.success("已收录为平台算法");
  } catch (e) {
    ElMessage.error(e?.message || "收录失败");
  } finally {
    setLoading(promotingAlgorithmIds, row.id, false);
  }
}



async function promoteAlgorithmSubmission(row) {
  try {
    setLoading(promotingSubmissionIds, row.id, true);
    const out = await adminApi.promoteAlgorithmSubmission(row.id);
    algorithmSubmissions.value = (algorithmSubmissions.value || []).map((item) =>
      item.id === row.id ? mapAlgorithmSubmission(out) : item
    );
    await store.fetchAlgorithms(500, { force: true });
    ElMessage.success("已收录为平台算法");
  } catch (e) {
    ElMessage.error(e?.message || "收录失败");
  } finally {
    setLoading(promotingSubmissionIds, row.id, false);
  }
}

async function downloadAlgorithmSubmission(row) {
  try {
    await algorithmSubmissionsApi.downloadArchive(row.id, row.archiveFilename || "algorithm_package.zip");
  } catch (e) {
    ElMessage.error(e?.message || "下载代码包失败");
  }
}

function formatTaskTypes(taskTypes) {
  if (!Array.isArray(taskTypes) || !taskTypes.length) return "未限定";
  return taskTypes.map((item) => TASK_LABEL_BY_TYPE[item] || item).join(" / ");
}

function metricStatusLabel(status) {
  if (status === "approved") return "已通过";
  if (status === "rejected") return "已驳回";
  return "待审核";
}

function metricStatusTagType(status) {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  return "warning";
}

function openAlgorithmSubmissionReview(row) {
  activeSubmission.value = row;
  submissionReviewStatus.value = row.status === "rejected" ? "rejected" : "approved";
  submissionReviewRuntimeReady.value = Boolean(row.runtimeReady);
  submissionReviewNote.value = String(row.reviewNote || "");
  submissionReviewVisible.value = true;
}

function closeAlgorithmSubmissionReview() {
  submissionReviewVisible.value = false;
  activeSubmission.value = null;
  submissionReviewStatus.value = "approved";
  submissionReviewRuntimeReady.value = false;
  submissionReviewNote.value = "";
}

async function submitAlgorithmSubmissionReview() {
  const row = activeSubmission.value;
  if (!row?.id) return;
  try {
    submissionReviewSubmitting.value = true;
    setLoading(reviewingSubmissionIds, row.id, true);
    const out = await adminApi.reviewAlgorithmSubmission(row.id, {
      status: submissionReviewStatus.value,
      review_note: submissionReviewNote.value,
      collect_to_platform: false,
      runtime_ready: submissionReviewStatus.value === "approved" ? submissionReviewRuntimeReady.value : false,
    });
    algorithmSubmissions.value = (algorithmSubmissions.value || []).map((item) =>
      item.id === row.id ? mapAlgorithmSubmission(out) : item
    );
    ElMessage.success("算法接入审核结果已保存");
    closeAlgorithmSubmissionReview();
  } catch (e) {
    ElMessage.error(e?.message || "算法接入审核失败");
  } finally {
    submissionReviewSubmitting.value = false;
    setLoading(reviewingSubmissionIds, row.id, false);
  }
}

function openMetricReview(row) {
  activeMetric.value = row;
  metricReviewStatus.value = row.status === "rejected" ? "rejected" : "approved";
  metricReviewRuntimeReady.value = Boolean(row.runtimeReady);
  metricReviewNote.value = String(row.reviewNote || "");
  metricReviewVisible.value = true;
}

function closeMetricReview() {
  metricReviewVisible.value = false;
  activeMetric.value = null;
  metricReviewStatus.value = "approved";
  metricReviewRuntimeReady.value = false;
  metricReviewNote.value = "";
}

async function submitMetricReview() {
  const row = activeMetric.value;
  if (!row?.id) return;
  try {
    metricReviewSubmitting.value = true;
    setLoading(reviewingMetricIds, row.id, true);
    const out = await adminApi.reviewMetric(row.id, {
      status: metricReviewStatus.value,
      review_note: metricReviewNote.value,
      runtime_ready: metricReviewRuntimeReady.value,
    });
    metrics.value = (metrics.value || []).map((item) =>
      item.id === row.id ? mapMetric(out) : item
    );
    await store.fetchMetrics();
    ElMessage.success("指标审核结果已保存");
    closeMetricReview();
  } catch (e) {
    ElMessage.error(e?.message || "指标审核失败");
  } finally {
    metricReviewSubmitting.value = false;
    setLoading(reviewingMetricIds, row.id, false);
  }
}

function downloadMetricCode(row) {
  const codeText = String(row?.codeText || "");
  const fileName = String(row?.codeFilename || row?.metricKey || "metric_code.py").trim() || "metric_code.py";
  if (!codeText) {
    ElMessage.warning("当前没有可下载的代码内容");
    return;
  }
  const blob = new Blob([codeText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function takedownDataset(row) {
  try {
    setLoading(loadingDatasetIds, row.id, true);
    await adminApi.takedownDataset(row.id);
    await loadAll();
    ElMessage.success("数据集已下架");
  } catch (e) {
    ElMessage.error(e?.message || "数据集下架失败");
  } finally {
    setLoading(loadingDatasetIds, row.id, false);
  }
}

async function deleteComment(row) {
  try {
    setLoading(deletingCommentIds, row.commentId, true);
    await adminApi.deleteComment(row.resourceType, row.resourceId, row.commentId);
    comments.value = comments.value.filter((item) => item.commentId !== row.commentId);
    if (reportTargetComment.value?.commentId === row.commentId) {
      reportTargetComment.value = null;
    }
    ElMessage.success("评论已删除");
  } catch (e) {
    ElMessage.error(e?.message || "删除评论失败");
  } finally {
    setLoading(deletingCommentIds, row.commentId, false);
  }
}

function openReportProcess(row) {
  activeReport.value = row;
  reportProcessAction.value =
    row?.targetType === "algorithm"
      ? "takedown_algorithm"
      : row?.targetType === "dataset"
        ? "takedown_dataset"
        : row?.targetType === "comment"
          ? "delete_comment"
          : "resolve";
  reportTargetDetail.value = null;
  reportTargetComment.value = null;
  reportProcessVisible.value = true;
  reportProcessNote.value = getReportProcessTemplate(reportProcessAction.value);
  loadReportTargetDetail(row);
}

function closeReportProcess() {
  reportProcessVisible.value = false;
  activeReport.value = null;
  reportProcessAction.value = "resolve";
  reportProcessNote.value = "";
  reportTargetDetail.value = null;
  reportTargetComment.value = null;
}

watch(reportProcessAction, (next) => {
  reportProcessNote.value = getReportProcessTemplate(next);
});

async function loadReportTargetDetail(row) {
  if (!row) return;
  try {
    if (row.targetType === "algorithm") {
      const x = await adminApi.getCommunityAlgorithmDetail(row.targetId);
      reportTargetDetail.value = mapAlgorithm(x);
      return;
    }
    if (row.targetType === "dataset") {
      const x = await adminApi.getCommunityDatasetDetail(row.targetId);
      reportTargetDetail.value = mapDataset(x);
      return;
    }
    if (row.targetType === "comment") {
      if (row.resourceType === "algorithm") {
        const x = await adminApi.getCommunityAlgorithmDetail(row.resourceId);
        reportTargetDetail.value = mapAlgorithm(x);
      } else if (row.resourceType === "dataset") {
        const x = await adminApi.getCommunityDatasetDetail(row.resourceId);
        reportTargetDetail.value = mapDataset(x);
      }
      reportTargetComment.value =
        (comments.value || []).find((item) => String(item.commentId || "") === String(row.targetId || "")) || null;
    }
  } catch {
    reportTargetDetail.value = null;
    reportTargetComment.value = null;
  }
}

async function copyDatasetPath(path) {
  const text = String(path || "").trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("路径已复制");
  } catch {
    ElMessage.warning("复制失败，请手动复制路径");
  }
}

function openDatasetFolder(path) {
  const text = String(path || "").trim();
  if (!text) return;
  const normalized = text.replace(/\\/g, "/");
  window.open(`file:///${normalized}`, "_blank");
  ElMessage.info("已尝试打开文件夹；如果浏览器拦截，请先复制路径再手动打开。");
}

async function submitReportProcess() {
  const row = activeReport.value;
  if (!row?.reportId) return;
  const action = String(reportProcessAction.value || "resolve");
  const note = String(reportProcessNote.value || "").trim() || getReportProcessTemplate(action);
  try {
    reportProcessSubmitting.value = true;
    setLoading(resolvingReportIds, row.reportId, true);

    if (action === "takedown_algorithm") {
      await adminApi.takedownAlgorithm(row.targetId);
      algorithms.value = algorithms.value.filter((item) => item.id !== row.targetId);
    } else if (action === "takedown_dataset") {
      await adminApi.takedownDataset(row.targetId);
      datasets.value = datasets.value.filter((item) => item.id !== row.targetId);
    } else if (action === "delete_comment") {
      await adminApi.deleteComment(row.resourceType, row.resourceId, row.targetId);
      comments.value = comments.value.filter((item) => item.commentId !== row.targetId);
      if (reportTargetComment.value?.commentId === row.targetId) {
        reportTargetComment.value = null;
      }
    }

    const status = action === "reject" ? "rejected" : "resolved";
    await adminApi.resolveReport(row.reportId, { status, resolution: note });
    reports.value = reports.value.map((item) =>
      item.reportId === row.reportId
        ? {
            ...item,
            status,
            statusLabel: status === "rejected" ? "已驳回" : "已处理",
            resolution: note,
            resolvedBy: String(store.user.username || ""),
            resolvedAt: formatTs(Math.floor(Date.now() / 1000)),
          }
        : item
    );
    ElMessage.success(status === "rejected" ? "举报已驳回" : "举报已处理");
    closeReportProcess();
  } catch (e) {
    ElMessage.error(e?.message || "处理举报失败");
  } finally {
    reportProcessSubmitting.value = false;
    setLoading(resolvingReportIds, row.reportId, false);
  }
}

async function clearHandledReports() {
  try {
    clearingReports.value = true;
    const res = await adminApi.clearReports("handled");
    reports.value = (reports.value || []).filter((item) => String(item.status || "") === "pending");
    ElMessage.success(`已清除 ${Number(res?.deleted || 0)} 条处理记录`);
  } catch (e) {
    ElMessage.error(e?.message || "清除记录失败");
  } finally {
    clearingReports.value = false;
  }
}

onMounted(loadAll);
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
}

.warn-box {
  margin-bottom: 20px;
}

.toolbar {
  margin-bottom: 14px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  max-width: 420px;
}

.clear-btn {
  margin-left: auto;
}

.data-table {
  width: 100%;
}

.detail-panel,
.process-panel {
  display: grid;
  gap: 18px;
}

.detail-summary {
  display: grid;
  gap: 10px;
}

.detail-name {
  font-size: 22px;
  font-weight: 700;
  color: #1f2f57;
}

.detail-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: #5d6c8c;
}

.detail-block {
  display: grid;
  gap: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px 16px;
  color: #334466;
}

.code-box {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, "Courier New", monospace;
}

.full-width {
  width: 100%;
}

.block-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2f57;
}

.description-box,
.process-detail-desc,
.process-path,
.process-comment-box,
.process-meta {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fbff;
  border: 1px solid #dce7ff;
  color: #334466;
  line-height: 1.7;
  white-space: pre-wrap;
}

.process-detail-card {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e6eeff;
}

.process-detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.process-detail-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2f57;
  margin-right: auto;
}

.process-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px 16px;
  color: #334466;
}

.full-width {
  width: 100%;
}

.comment-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e6eeff;
}

.comment-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  color: #5d6c8c;
}

.comment-head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.comment-author {
  font-weight: 700;
  color: #1f2f57;
}

.comment-content {
  color: #334466;
  line-height: 1.7;
  white-space: pre-wrap;
}

.empty-text {
  color: #7b89a8;
}
</style>

