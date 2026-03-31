# API 接口逐项说明（按 /docs 顺序）

说明：以下按 FastAPI 文档页面从上到下整理，每项给出“做什么”。

## default
1. `GET /health`：健康检查，返回服务是否可用与时间戳。
2. `GET /meta/error-codes`：返回系统结构化错误码清单，便于前后端统一报错处理。
3. `GET /datasets`：查询数据集列表。
4. `POST /datasets`：创建数据集元信息（可自定义或自动生成 dataset_id）。
5. `PATCH /datasets/{dataset_id}`：修改数据集信息（名称、类型、规模等）。
6. `DELETE /datasets/{dataset_id}`：删除指定数据集记录。
7. `POST /datasets/{dataset_id}/scan`：扫描磁盘数据集目录并回填类型、规模、配对元信息。
8. `POST /datasets/{dataset_id}/import_zip`：导入 Base64 ZIP 数据集，解压后自动扫描并更新元信息。
9. `GET /algorithms`：查询算法列表（含默认参数与参数预设兜底补全）。
10. `POST /algorithms`：创建算法条目。
11. `PATCH /algorithms/{algorithm_id}`：修改算法配置（任务、名称、实现、版本、参数等）。
12. `DELETE /algorithms/{algorithm_id}`：删除指定算法。
13. `GET /presets`：查询运行预设列表。
14. `GET /presets/{preset_id}`：查询单个预设详情。
15. `POST /presets`：创建运行预设（任务类型、数据集、算法、指标与参数组合）。
16. `PATCH /presets/{preset_id}`：更新预设内容。
17. `DELETE /presets/{preset_id}`：删除预设。
18. `POST /recommend/fast-select`：核心快速选型接口，基于 LinUCB 在线决策返回 Top-K 算法推荐。
19. `POST /runs`：创建评测运行任务并投递异步执行队列。
20. `GET /runs`：查询运行列表，支持按状态、任务、数据集、算法过滤。
21. `GET /runs/export`：导出运行记录（CSV/XLSX）。
22. `POST /runs/clear`：按状态批量清理运行记录（默认清理 done）。
23. `GET /runs/{run_id}`：查询单个运行详情。
24. `POST /runs/{run_id}/cancel`：取消运行任务（排队中可直接取消，运行中进入 canceling）。

## 补充
- `GET /`：会重定向到 `/docs`，用于浏览器直接访问服务根路径时进入 API 文档页。
