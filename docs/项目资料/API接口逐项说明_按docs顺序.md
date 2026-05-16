# API 接口逐项说明

本文按当前 `backend/app/main.py` 的真实路由整理，作为 FastAPI `/docs` 的中文辅助说明。

## 基础与鉴权

- `GET /health`：健康检查。
- `GET /meta/error-codes`：返回结构化错误码清单。
- `GET /`：浏览器访问根路径时跳转到 `/docs`。
- `POST /register`：注册普通用户。
- `POST /token` / `POST /login`：用户登录并返回 token。
- `POST /admin/login`：管理员登录。
- `GET /me`：获取当前用户信息。
- `PATCH /me/profile`：更新个人资料。
- `POST /me/password`：修改密码。

## AI、反馈与通知

- `POST /ai/chat`：AI 辅助问答，面向平台流程解释与使用帮助。
- `POST /feedback`：提交用户反馈。
- `GET /me/notices`：查看个人通知。
- `POST /me/notices/{notice_id}/read`：标记单条通知已读。
- `POST /me/notices/read-all`：全部标记已读。
- `POST /me/notices/clear-read`：清理已读通知。

## 数据集

- `GET /datasets`：查询数据集列表。
- `POST /datasets`：创建数据集元信息。
- `PATCH /datasets/{dataset_id}`：更新数据集信息。
- `POST /datasets/{dataset_id}/change_id`：修改数据集 ID。
- `DELETE /datasets/{dataset_id}`：删除数据集。
- `GET /datasets/{dataset_id}/export`：导出数据集资源。
- `POST /datasets/{dataset_id}/scan`：扫描磁盘目录并回填任务类型、规模和配对信息。
- `POST /datasets/{dataset_id}/import_zip`：Base64 ZIP 导入。
- `POST /datasets/{dataset_id}/import_zip_file`：文件表单 ZIP 导入。

## 算法与算法接入

- `GET /algorithms`：查询算法库。
- `POST /algorithms`：创建算法条目。
- `PATCH /algorithms/{algorithm_id}`：更新算法配置。
- `DELETE /algorithms/{algorithm_id}`：删除算法。
- `GET /algorithms/{algorithm_id}/export`：导出算法包。
- `GET /algorithm-submissions`：查看当前用户算法接入申请。
- `POST /algorithm-submissions`：提交算法接入申请。
- `GET /algorithm-submissions/{submission_id}/download`：下载算法接入包。
- `DELETE /algorithm-submissions/{submission_id}`：删除接入申请。
- `POST /algorithm-submissions/{submission_id}/publish-community`：发布算法到社区。
- `POST /algorithm-submissions/{submission_id}/unpublish-community`：取消社区发布。
- `GET /history/algorithm-submissions`：查看算法接入历史。
- `GET /history/algorithm-submissions/{history_id}/download`：下载历史算法包。
- `DELETE /history/algorithm-submissions`、`DELETE /history/algorithm-submissions/{history_id}`、`POST /history/algorithm-submissions/delete-batch`：清理历史记录。

## 指标

- `GET /metrics`：查询指标库。
- `POST /metrics`：创建自定义指标。
- `PATCH /metrics/{metric_id}`：更新指标。
- `DELETE /metrics/{metric_id}`：删除指标。
- `POST /metrics/{metric_id}/publish-community` / `unpublish-community`：发布或取消发布社区指标。
- `POST /community/metrics/{metric_id}/download`：下载社区指标。
- `GET /history/metric-submissions` 及相关删除接口：查看和清理指标历史。

## 社区与管理后台

- `POST /community/datasets/{dataset_id}/download`：下载社区数据集。
- `GET/POST/DELETE /community/*/comments`：资源评论管理。
- `POST /community/reports`：提交举报。
- `GET /admin/users`、`DELETE /admin/users/{username}`：用户管理。
- `GET /admin/algorithm-submissions`、`POST /admin/algorithm-submissions/{submission_id}/review`：算法接入审核。
- `POST /admin/algorithm-submissions/{submission_id}/promote-platform`：收录为平台算法。
- `GET /admin/metrics`、`POST /admin/metrics/{metric_id}/review`：指标审核。
- `GET /admin/community/*`、`POST /admin/community/*/takedown`、`promote`：社区资源审核与下架/恢复。
- `GET /admin/feedback`、`POST /admin/feedback/{feedback_id}/resolve`：反馈处理。
- `GET /admin/reports`、`POST /admin/reports/{report_id}/resolve`、`POST /admin/reports/clear`：举报处理。

## 预设与评测任务

- `GET /presets`、`GET /presets/{preset_id}`：查询运行预设。
- `POST /presets`、`PATCH /presets/{preset_id}`、`DELETE /presets/{preset_id}`：创建、更新、删除预设。
- `POST /runs`：创建评测任务并投递异步执行队列。
- `GET /runs`：查询任务列表。
- `GET /runs/export`：导出任务记录。
- `POST /runs/clear`、`POST /runs/batch-clear`：清理任务记录。
- `GET /runs/{run_id}`：查看单个任务详情。
- `POST /runs/{run_id}/cancel`：取消任务。

## 已下线接口

- `POST /recommend/fast-select` 已移除。
- 当前项目不包含 LinUCB 或多臂赌博机快速选型流程。
