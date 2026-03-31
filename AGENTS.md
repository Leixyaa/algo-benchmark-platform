# AGENTS.md

## 核心说明（Core Instructions）
本仓库是 `algo-benchmark-platform` 的工程主仓，目标是交付“可复现、可解释、可导出”的算法评测系统。  
项目主线以系统工程能力为中心：统一评测流程、稳定执行链路、标准化导出与答辩可演示性。

## 1. 项目架构（Project Architecture）

### 1.1 后端（Backend）
- 目录：`backend/`
- 技术栈：Python 3.x、FastAPI、Celery、Redis、OpenPyXL
- 算法/指标：OpenCV、scikit-image、NumPy、SciPy、scikit-video
- 关键文件：
  - `backend/app/main.py`：API 主入口
  - `backend/app/celery_app.py` / `backend/app/tasks.py`：异步任务执行
  - `backend/app/vision/`：视觉算法与数据配对逻辑
  - `backend/app/schemas.py`：请求/响应模型
  - `backend/app/store.py`：Redis 存取封装
  - `backend/app/selector.py`：核心算法快速选型（LinUCB）

### 1.2 前端（Frontend）
- 目录：`web/`
- 技术栈：Vue3 + Vite、Pinia、Element Plus、XLSX
- 关键页面：
  - `views/Datasets.vue`：数据集管理
  - `views/Algorithms.vue`：算法管理
  - `views/NewRun.vue` / `views/Runs.vue`：运行创建与状态追踪
  - `views/Compare.vue`：指标对比、推荐、导出（含快速选型接入）

## 2. 毕设文档同步（Graduation Docs Sync）
- 主目录：`docs/graduation/`
- 提交总入口：`docs/UPLOAD_GUIDE.md`
- 要求模板：`docs/graduation/REQUIREMENTS_EXTRACTED_TEMPLATE.md`
- 关键文档：
  - `系统架构_流程_ER_实现说明.md`
  - `答辩交付_演示脚本_验收清单_论文章节映射.md`
  - `导师演示_全流程操作手册.md`
  - `核心算法_快速选型模块说明.md`
  - `核心算法_快速选型_实验小节（可直接入论文）.md`
  - `系统总测试表_验收版.md`
  - `论文库盘点_已在库与待补充.md`
  - `BULK_COMPARE_GUIDE.md`
  - `ERROR_CODES.md`
  - `EXPERIMENT_RECORD_FIELDS.md`
  - `PROCESS_LOG.md`

## 3. 毕设目标与验收口径
- 目标：完成图像/视频增强复原评测平台，支持快速选型与可追溯导出。
- 主线闭环：数据集管理 → 运行创建 → 异步执行 → 指标计算 → 对比推荐 → 导出归档。
- 最低验收：
  - 图像 5 类任务 + 视频 2 类任务可运行
  - Run 生命周期与取消一致性完整
  - PSNR/SSIM/NIQE 指标可用
  - CSV/XLSX/Markdown 导出口径一致

## 4. 当前状态（Current Status）
- 图像任务：`denoise/deblur/dehaze/sr/lowlight` 已打通
- 视频任务：`video_denoise/video_sr` 已打通
- 稳定性能力：
  - strict_validate 配对校验
  - 结构化错误码
  - 重试与失败路径治理
  - run.record 上下文留痕
- 推荐能力：
  - Compare 权重排序推荐与 XLSX/Markdown 报告导出
  - 核心算法 `POST /recommend/fast-select`（LinUCB）已接入主流程，支持一键创建 Run
  - `Algorithms.vue` 支持新手可视化/专业 JSON 双模式，集成一键应用预设参数
 - 工程治理：
  - `.gitattributes` 默认文本行尾统一为 LF（脚本文件除外）
  - `scripts/manual_up.ps1` + `scripts/start_docker_redis.ps1` 支持一键拉起 Docker/Redis 与 Backend/Worker/Web
  - 新增 `docs/项目资料/` 目录沉淀接口与项目落地资料

## 4.1 开发启动（Dev Bootstrap）
- Windows 推荐命令：
  - 一键启动（含 Docker + Redis + 三窗口服务）：`.\scripts\manual_up.cmd`
  - PowerShell 直启：`powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1`
  - 仅启动三个业务窗口（跳过 Redis）：`powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1 -SkipRedis`
- Redis 独立启动：
  - `powershell -ExecutionPolicy Bypass -File .\scripts\start_docker_redis.ps1`
- 常用访问：
  - API 文档：`http://127.0.0.1:8000/docs`
  - Web 页面：`http://localhost:5173/`

## 5. 开发日志（Development Log）
| 日期 | 事项 | 说明 | 状态 |
| :--- | :--- | :--- | :--- |
| 2026-01-18 | 项目初始化 | 建立仓库、后端/前端骨架、文档目录规范 | 完成 |
| 2026-01-23 | 启动脚本统一 | 完善 `scripts/dev.ps1` / `scripts/dev.cmd` 一键联调 | 完成 |
| 2026-02-07 | 评测链路增强 | strict_validate、record、导出字段增强 | 完成 |
| 2026-02-14 | Compare 增强 | 批次筛选、推荐导出、Markdown 结论 | 完成 |
| 2026-03-16 | 稳定性治理 | 重试、取消一致性、run.record 资源信息 | 完成 |
| 2026-03-17 | 视频主线打通 | `video_denoise/video_sr` API+Worker+前端联调 | 完成 |
| 2026-03-23 | 核心算法接入 | LinUCB 快速选型接入 Compare 主流程并可一键创建 Run | 完成 |
| 2026-03-23 | 编码治理 | 全仓 UTF-8 修复、文档库清洗、文件清单更新 | 完成 |
| 2026-03-24 | 前端编码巡检治理 | 收敛行尾策略并转为按需扫描，避免新增临时脚本 | 完成 |
| 2026-03-24 | 前端文本与格式扫描 | 按 views/store/api/router 范围扫描并统一 CRLF→LF，保留疑似乱码清单待逐条修复 | 完成 |
| 2026-03-24 | 前端乱码批量修复 | 完成 views 与 api 相关乱码占位替换并复扫归零，前端构建验证通过 | 完成 |
| 2026-03-24 | 编码防漂移加固 | 前端相关文件重写为 UTF-8+LF，并新增 VSCode 工作区编码固定配置 | 完成 |
| 2026-03-27 | 一键启动脚本重建 | 新增 `scripts/start_docker_redis.ps1` 与 `scripts/manual_up.ps1/.cmd`，实现 Docker+Redis+Backend/Worker/Web 一键拉起 | 完成 |
| 2026-03-28 | 后端文本编码防呆 | 修复数据集默认类型乱码为“图像”，并在数据集/算法/预设创建更新接口加入疑似乱码文本拦截（UTF-8 提示） | 完成 |
| 2026-03-29 | 导师演示手册完善 | 新增 `docs/graduation/导师演示_全流程操作手册.md`，补齐从环境启动、主流程演示到异常兜底与收口交付的逐步操作文档 | 完成 |
| 2026-03-29 | 项目资料目录新增 | 新增 `docs/项目资料/README.md` 与 `API接口逐项说明_按docs顺序.md`，沉淀接口用途与资料索引 | 完成 |
| 2026-03-29 | 算法参数交互友好化 | `Algorithms.vue` 新增“新手可视化/专业JSON”双模式参数编辑，并提供推荐默认、稳妥模式、增强模式一键应用 | 完成 |
| 2026-03-29 | 参数中文解释增强 | `Algorithms.vue` 新增参数中文名与用途说明面板，支持可视化逐项说明与 JSON 键自动解释，降低非算法用户使用门槛 | 完成 |
| 2026-03-30 | 验收文档编制 | 完成 `系统总测试表_验收版.md`，覆盖 F-01~F-25 功能、R-01~R-05 真实性与 E-01~E-05 异常测试 | 完成 |
| 2026-03-31 | 论文库同步与索引更新 | 完成 `论文库盘点_已在库与待补充.md` 梳理，明确 LinUCB 核心算法理论支撑文献补齐路径 | 完成 |

## 6. 当前待办（Todo）
- [ ] 完成最终答辩演示彩排与故障预案回归（按 `系统总测试表_验收版.md` 执行）
- [ ] 完成论文正文第 1~6 章填充与图表定稿
- [ ] 完成核心算法最终实验复跑并更新正式结论（结合 `论文库盘点` 补齐文献支撑）
