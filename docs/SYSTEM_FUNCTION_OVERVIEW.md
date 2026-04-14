# 项目系统功能总览

## 一句话说明
这是一个面向图像与视频增强/复原任务的算法评测平台，目标是实现“可复现、可解释、可导出”的完整评测闭环。

## 主线闭环
数据集管理 -> 算法管理 -> 创建 Run -> Celery 异步执行 -> 指标计算 -> Compare 对比推荐 -> CSV/XLSX/Markdown 导出

## 已支持任务
- 图像任务：`denoise`、`deblur`、`dehaze`、`sr`、`lowlight`
- 视频任务：`video_denoise`、`video_sr`

## 核心能力
- 数据集扫描、目录配对、strict_validate 校验
- 算法配置、默认参数、参数预设与方案复用
- Run 生命周期管理：排队、执行、取消、失败回写、记录留痕
- 指标计算：PSNR、SSIM、NIQE
- Compare 加权排序推荐
- LinUCB 快速选型与一键创建 Run
- CSV / XLSX / Markdown 导出

## 2026-04 本轮更新（与仓库同步）

- **数据集与任务类型**：`web/src/utils/datasetTask.js` 统一判断支持的任务；扫描/导入后后端同步 `supported_task_types` 与 `task_types`；`NewRun` / `Compare` 按任务过滤数据集；`Datasets` 新建不强制手填任务；社区列表排除 `system` 并二次校验；`Community` 不 keep-alive，避免列表快照过期。
- **存储**：`store.py` Redis 与 SQL 合并取较新、更新时间递增；`sql_store.py` DDL 锁与 MySQL 1683/1684 重试、`payload_json` 列类型按需升级。
- **前端工程**：依赖仅在 `web/package.json`（根目录已移除重复 `package.json` / `node_modules`）；新环境须在 `web/` 下 `npm install`。
- **样例脚本**：`docs/项目资料/test_algorithm_denoise.py` 已迁至 `backend/tools/sample_algorithm_denoise.py`（文档路径已对齐）。
- **运维说明**：停止 `uvicorn` 时 Ctrl+C 出现 `KeyboardInterrupt` / `CancelledError` 为正常关机，非业务错误。

## 2026-04-01 本轮更新
- 修复 `NewRun` 预设指标高亮回显。
- 修复 `Compare.vue` 重复声明导致的编译报错。
- 后端执行链路改为真正按所选指标计算。
- Compare 批量/快速选型创建 Run 改为按参数指纹判重。
- 导出请求统一纳入 `authFetch` 处理。
- 核心入口与主展示页完成模板层和主要脚本提示文案清洗，`Runs / Compare` 的状态、导出、图表与评分提示已统一为正常中文。
- 全任务类型基线算法目录扩充为多组可运行变体，`Compare` 与 `Algorithms` 页面可直接展示并批量创建更丰富的正式对比实验。

## 建议优先阅读
- `docs/graduation/系统架构_流程_ER_实现说明.md`
- `docs/graduation/导师演示_全流程操作手册.md`
- `docs/graduation/系统总测试表_验收版.md`
- `docs/graduation/PROCESS_LOG.md`
