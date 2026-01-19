# AGENTS.md

## 核心说明 (Core Instructions)
本文档用于记录 `algo-benchmark-platform` 项目的架构设计、毕设硬性约束、当前开发进度与后续计划。
**项目性质**：本项目为用户的本科毕业设计（系统开发类），需注重代码规范、文档完整性、评测口径统一与可复现。
**AI 协作约定**：每次启动编程任务前先阅读本文档；每次完成代码修改后同步更新本文档的“开发日志”和“当前状态”。

## 1. 项目架构 (Project Architecture)
本项目是“算法性能测试与快速选型平台”，采用前后端分离架构。

### 1.1 后端 (Backend)
- 路径：`backend/`
- 技术栈：Python 3.x，FastAPI，Celery + Redis
- 依赖能力：OpenCV、scikit-image、scikit-video、NumPy、SciPy
- 关键模块：
  - `app/main.py`：API 入口
  - `app/celery_app.py` / `app/tasks.py`：异步任务执行
  - `app/vision/`：算法与指标实现（如 DCP、NIQE）
  - `app/schemas.py`：数据模型
  - `app/store.py`：数据存储/读写（现阶段以轻量方式为主）

### 1.2 前端 (Frontend)
- 路径：`web/`
- 技术栈：Vue3 + Vite；Pinia；Element Plus；ECharts；Axios；XLSX（Excel 导出）
- 主要页面：
  - `views/Algorithms.vue`：算法库管理
  - `views/Datasets.vue`：数据集管理
  - `views/NewRun.vue` / `views/Runs.vue`：新建评测与运行列表
  - `views/Compare.vue`：结果对比与快速选型（含导出）
  - `views/Tasks.vue`：任务页（后续可调整定位）

## 2. 毕设资料同步 (Graduation Docs Sync)
- 资料目录：`docs/graduation/`
- 上传方式指南：`docs/UPLOAD_GUIDE.md`
- 已同步摘录：`docs/graduation/REQUIREMENTS_EXTRACTED_TEMPLATE.md`

## 3. 毕设需求与约束（已同步）
- 范围：图像（去噪/去模糊/去雾/超分/低照度增强）+ 视频（视频去噪/视频超分）
- 评测闭环：数据集管理 → 算法库管理 → 发起评测（Run）→ 异步执行 → 指标计算（PSNR/SSIM + NIQE）→ 对比与快速推荐 → 导出报告（CSV/Excel）
- 原则：不做算法创新；统一评测协议保证可比性与可复现性；记录配置/耗时/错误信息便于追溯
- 论文约束（系统开发类）：参考文献 ≥15（外文 ≥5、近三年 ≥3）；开题报告 ≥3000 字；需上传《任务书》《开题报告》《论文正文》《AI工具使用责任书》
- 过程管理记录本：至少填写 6 次指导记录并签字，材料需留存并按要求上交
- AI 工具合规：按学校“试行”意见执行（禁止直接生成论文正文/开题报告等；允许用于代码辅助、文献检索/整理、格式检查与辅助制图；需核查并按要求披露）
- 关键时间点（学院安排）：系统验收 2026-04-07~04-18；论文终版截止 2026-05-03 08:00；答辩 2026-05-19~05-21（详见资料摘录）

## 4. 当前状态 (Current Status)
- 日期：2026-01-19
- 状态：已有基础可运行闭环（前后端 + 异步队列 + 指标计算与对比导出）
- 已具备：
  - 异步评测任务：queued/running/done（可扩展 failed）
  - 指标：PSNR、SSIM、NIQE（支持记录耗时、样本级摘要）
  - 图像任务基线实现：去雾（DCP）、去噪（FastNLMeans）、去模糊（Unsharp Mask）、超分（Bicubic）、低照度增强（Gamma）
  - 数据集读取约定：`backend/data/<dataset_id>/{hazy|noisy|blur|lr|dark}/` + `gt/` 同名配对
  - 前端：数据集/算法管理（本地持久化）、结果对比、快速选型（多指标加权）、CSV/Excel 导出
- 待完善（按资料摘录推进）：
  - 数据集/算法的存储与类型管理进一步完善（多任务、多类型、更真实数据验证）
  - 评测执行的鲁棒性：错误信息/重试、运行耗时/资源统计、任务取消等
  - 报告导出更详细：包含执行时间、失败原因、配置快照（当前已支持导出 params_json 与 samples_json）
  - 视频任务（视频去噪/视频超分）的数据格式与评测流程落地

## 5. 开发日志 (Development Log)
| 日期 | 任务 | 详情 | 状态 |
| :--- | :--- | :--- | :--- |
| 2026-01-18 | 初始化协作文档 | 建立 AI 协作流程与项目架构说明 | 完成 |
| 2026-01-18 | 建立资料目录与上传指南 | 新增 `docs/graduation/` 与上传说明、摘录模板 | 完成 |
| 2026-01-18 | 同步毕设资料与硬性约束 | 读取开题/任务书/学校规范并整理为可执行清单 | 完成 |
| 2026-01-18 | 保护毕设资料隐私 | 为 `docs/graduation/` 添加 `.gitignore`，避免误提交包含个人信息的原始材料 | 完成 |
| 2026-01-19 | 扩展多任务基线评测 | 泛化数据集配对读取，补齐多任务基线算法，导出增加 params/samples 字段 | 完成 |

## 6. 待办事项 (Todo)
- [ ] 基于真实数据集补齐端到端测试与稳定性验证
- [ ] 补充任务失败路径、错误信息展示与导出
- [ ] 完善论文所需的系统架构图、流程图、数据模型（ER）与实验设计说明
