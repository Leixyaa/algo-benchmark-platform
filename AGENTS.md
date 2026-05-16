# AGENTS.md

> 本文件描述本仓库当前的真实状态，用于所有智能助手会话的上下文。
> 如有字段与代码/论文实际不符，请以代码与论文正文为准，并及时更新本文。

## 核心说明（Core Instructions）
本仓库是 `algo-benchmark-platform` 的工程主仓，交付“面向图像/视频增强复原任务的开放式算法性能测试平台”。
项目主线以系统工程能力为中心：统一评测流程、稳定执行链路、标准化导出与答辩可演示性。
**本项目不包含任何机器学习选型算法**（如 LinUCB、多臂赌博机等已全部移除）。

## 1. 项目架构（Project Architecture）

### 1.1 后端（Backend）
- 目录：`backend/`
- 技术栈：Python 3.x、FastAPI、Celery、Redis、OpenPyXL、SQLAlchemy
- 算法/指标：OpenCV、scikit-image、NumPy、SciPy、scikit-video
- 关键文件：
  - `backend/app/main.py`：FastAPI 主入口，聚合所有 HTTP 接口
  - `backend/app/celery_app.py` / `backend/app/tasks.py`：Celery 异步任务执行
  - `backend/app/algorithm_runtime.py`：算法运行时（UserPackage 执行、沙箱）
  - `backend/app/metric_runtime.py`：指标运行时（PSNR/SSIM/NIQE 等）
  - `backend/app/vision/`：数据集访问、目录扫描与经典算法实现（DCP 去雾、NIQE）
  - `backend/app/schemas.py`：Pydantic 请求/响应模型
  - `backend/app/store.py` / `backend/app/sql_store.py`：Redis 与关系型存储封装
  - `backend/app/errors.py`：结构化错误码（E_xxx）
  - `backend/app/auth.py`：Token 鉴权
  - `backend/app/selector.py`：**已置空**（原 LinUCB 快速选型已移除）

### 1.2 前端（Frontend）
- 目录：`web/`
- 技术栈：Vue3 + Vite、Pinia、Element Plus、XLSX
- 关键页面（`web/src/views/`）：
  - `Datasets.vue`：数据集管理、ZIP 导入、目录扫描、社区下载
  - `Algorithms.vue`：算法库、算法接入表单（新手可视化 / 专业 JSON 双模式 + 预设参数一键应用）
  - `Metrics.vue`：指标库与自定义指标接入
  - `NewRun.vue` / `Runs.vue`：评测任务创建与任务状态跟踪
  - `Compare.vue`：多任务指标对比、权重排序推荐、CSV/XLSX/Markdown 导出
  - `Community.vue`：社区资源（数据集/算法/指标）共享与评论
  - `Notices.vue` / `Profile.vue`：通知、个人中心
  - `Admin.vue`：管理后台（用户管理、社区审核、举报处理、反馈处理、日志）
  - 登录/注册/布局相关：`LoginBrand.vue`、`RegisterBrand.vue`、`AdminLoginBrand.vue`、`LayoutBrand2.vue`

### 1.3 桌面端（Desktop）
- 目录：`desktop/`（Electron 壳）
- **构建约定**：凡是修改 `web/` 前端，完成后需同时产出标准 Web 与桌面模式包。
  - `cd web && npm run build` — 标准站点（默认输出到 `web/dist/`）
  - `cd web && npm run build:desktop` — `--mode desktop`，供 `desktop/` 壳加载
- 桌面壳侧：`desktop/package.json` 的 `build:web` 会调用 `../web` 的 `build:desktop`；打包前请至少跑过上述两条或等价的 `npm run build:web`。

## 2. 毕设文档与论文（Graduation Docs & Thesis）
- `docs/` 中仍需保留项目运行、AI 问答知识库、桌面打包和导出检查会引用到的轻量工程文档。
- 论文最终稿、PPT、参考文献库、论文配图、写作过程稿、备份稿等大体量毕业材料可单独归档到工作区外部，不作为工程运行依赖。
- 推荐放回仓库的最小文档集：
  - `docs/AI_PLATFORM_KNOWLEDGE_BASE.md`
  - `docs/desktop-quickstart.md`
  - `docs/graduation/*.md`
  - `docs/导出文件/`
  - `docs/项目资料/`
- 论文写作说明：
  - 论文中提到的功能/模块必须与代码实际一致
  - 若论文中未涉及某段历史特性（例如已删除的 LinUCB 选型），禁止在答辩材料/创新点中重新引入

## 3. 毕设目标与验收口径
- **目标**：完成图像/视频增强复原评测平台，支持统一评测、可追溯导出与多端（Web/桌面）可演示。
- **主线闭环**：数据集 → 算法/指标接入 → 任务创建 → 异步执行 → 指标计算 → 对比分析 → 导出归档。
- **最低验收**：
  - 图像 5 类任务（去噪 / 去模糊 / 去雾 / 超分辨率 / 低照度增强）可运行
  - 视频 2 类任务（视频去噪 / 视频超分辨率）可运行
  - Run 生命周期与取消一致性完整
  - PSNR / SSIM / NIQE 指标可用
  - CSV / XLSX / Markdown 导出口径一致
  - 社区资源共享、管理后台审核、AI 辅助问答、反馈处理等外围模块可用

## 4. 当前状态（Current Status）
- **评测主线**：
  - 图像任务：`denoise / deblur / dehaze / sr / lowlight` 已打通
  - 视频任务：`video_denoise / video_sr` 已打通
- **稳定性能力**：
  - strict_validate 严格配对校验
  - 结构化错误码（`E_xxx`）与统一错误响应
  - 任务重试与失败路径治理
  - run.record 上下文留痕（资源快照、错误堆栈、阶段进度）
  - 取消一致性：排队态立即标记已取消；运行中取消后幂等终止
- **对比与导出**：
  - Compare 页面支持同任务/同数据集下的多算法横向对比
  - 权重排序推荐（按 PSNR/SSIM/NIQE/耗时等维度加权综合评分）
  - CSV / XLSX / Markdown 三种格式的结果与推荐报告导出
- **协同模块**：
  - 社区资源共享（数据集/算法/指标）、评论、举报
  - 通知中心（算法审核、举报处理、反馈处理结果回写）
  - AI 辅助问答（流程解释与使用帮助）
  - 管理后台（用户、资源审核、举报、反馈、日志）
- **工程治理**：
  - `.gitattributes` 默认文本行尾统一为 LF（脚本除外）
  - `scripts/manual_up.ps1` + `scripts/start_docker_redis.ps1` 一键拉起 Docker/Redis 与 Backend/Worker/Web
  - 前端 UTF-8 + LF 编码统一、VSCode 工作区编码固定
- **已移除能力**（勿在论文/创新点/答辩中提及）：
  - ~~LinUCB 快速选型算法~~（`backend/app/selector.py` 已置空）
  - ~~`POST /recommend/fast-select` 接口~~

## 4.1 开发启动（Dev Bootstrap）
- Windows 推荐命令：
  - 一键启动（含 Docker + Redis + 三窗口服务）：`.\scripts\manual_up.cmd`
  - PowerShell 直启：`powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1`
  - 仅启动业务窗口（跳过 Redis）：`powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1 -SkipRedis`
- Redis 独立启动：
  - `powershell -ExecutionPolicy Bypass -File .\scripts\start_docker_redis.ps1`
- 常用访问：
  - API 文档：`http://127.0.0.1:8000/docs`
  - Web 页面：`http://localhost:5173/`

## 5. 关键开发日志（Development Log）
| 日期 | 事项 | 状态 |
| :--- | :--- | :--- |
| 2026-01-18 | 项目初始化：仓库、后端/前端骨架、文档目录规范 | 完成 |
| 2026-02-07 | 评测链路增强：strict_validate、record、导出字段 | 完成 |
| 2026-02-14 | Compare 增强：批次筛选、权重排序推荐、Markdown 结论 | 完成 |
| 2026-03-16 | 稳定性治理：重试、取消一致性、run.record 资源信息 | 完成 |
| 2026-03-17 | 视频主线打通：video_denoise / video_sr 端到端联调 | 完成 |
| 2026-03-27 | 一键启动脚本重建：Docker + Redis + Backend/Worker/Web | 完成 |
| 2026-03-29 | 算法参数交互友好化：新手可视化 / 专业 JSON 双模式 + 中文参数说明 | 完成 |
| 2026-03-30 | 验收文档编制：功能/真实性/异常测试表 | 完成 |
| 2026-05-01 | **移除 LinUCB 快速选型模块**：`selector.py` 清空、相关接口下线，论文不再包含该内容 | 完成 |
| 2026-05-02 | 论文终检：图 36 张、表 18 个，编号连续、引用对应、格式合规 | 完成 |

## 6. 当前待办（Todo）
- [ ] 答辩演示彩排与故障预案回归
- [ ] 论文提交查重与盲审前最终校对
