# 项目系统功能总览（快速了解版）

## 1. 一句话说明

这是一个面向图像/视频增强与复原任务的算法评测平台，支持从数据集管理、算法管理、Run 执行、指标对比到导出汇报的完整闭环。

## 2. 系统能做什么

- 支持任务：`denoise / deblur / dehaze / sr / lowlight / video_denoise / video_sr`
- 支持对象管理：数据集、算法、参数预设
- 支持执行链路：创建 Run、异步执行、状态跟踪、取消、失败重试
- 支持评测指标：PSNR、SSIM、NIQE（含耗时信息）
- 支持对比推荐：Compare 页面权重推荐 + 核心算法快速选型（增强版 LinUCB）
- 支持结果导出：CSV、XLSX、Markdown

## 3. 系统架构（分层）

- **Web 前端（Vue3 + Vite + Pinia）**
  - 页面：Datasets / Algorithms / NewRun / Runs / Compare
- **API 层（FastAPI）**
  - 负责参数校验、任务编排、查询与导出
- **任务执行层（Celery Worker）**
  - 负责算法执行与指标计算
- **存储层（Redis）**
  - 存储 run/dataset/algorithm/preset 与在线 bandit 模型

## 4. 核心功能模块

### 4.1 数据集管理

- 新建、更新、删除、扫描
- 维护数据集 `meta`（任务支持、目录计数、配对计数）
- strict 校验时用于判断是否允许创建 Run

### 4.2 算法管理

- 新建、更新、删除算法
- 维护算法任务归属与默认参数
- 支持参数预设（用于批量创建与快速对比）

### 4.3 Run 执行与任务中心

- 创建 Run（支持 strict\_validate）
- 状态机：`queued -> running -> done/failed`，并支持 `canceling/canceled`
- Worker 写回 `record`（资源、重试、数据模式、时序等）
- 失败路径输出结构化错误码

### 4.4 对比分析与导出

- Compare 支持多指标归一化加权排序
- 支持批量创建基线 Run 与批次追踪
- 导出推荐结果与结论文档（CSV/XLSX/Markdown）

### 4.5 核心算法模块（快速选型）

- 方法：增强版 Contextual Bandit（LinUCB）
- 机制：时间衰减、冷启动补偿、低样本惩罚、可靠度门控
- 在线学习：Run 完成后增量更新模型，推荐优先读取在线模型
- 输出：`score/expected_reward/uncertainty/reliability` 等可解释字段

## 5. 关键业务流程（端到端）

1. 在 Datasets 导入/扫描数据集，形成可用任务配对信息
2. 在 Algorithms 维护候选算法与参数
3. 在 NewRun 或 Compare 批量创建 Run
4. Worker 异步执行并写回指标与记录
5. 在 Runs/Compare 查看结果、筛选、推荐
6. 导出结论用于汇报与论文材料

## 6. 快速启动（Windows）

- 标准一键联调：`.\scripts\dev.cmd up`
- 外部 Redis 快速模式（手动开 Docker 后，一键启动 Backend/Worker/Web）：`.\scripts\dev.cmd up -ExternalRedis`
- 兼容直启命令（自动拉起 Docker+Redis，并打开三个 PowerShell）：`powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1`
- 停止：`.\scripts\dev.cmd down`
- 重启并安装依赖：`.\scripts\dev.cmd restart -InstallDeps`
- 说明：
  - 一键脚本会优先复用已存在的 `algo-redis` 容器，减少冷启动耗时
  - 若只需手动控制 Docker，使用 `-ExternalRedis` 可避免脚本等待 Docker daemon
- 访问：
  - API 文档：`http://127.0.0.1:8000/docs`
  - Web 页面：`http://localhost:5173/`

## 7. 建议先读的文档

- 系统设计总说明：`docs/graduation/系统架构_流程_ER_实现说明.md`
- 核心算法说明：`docs/graduation/核心算法_快速选型模块说明.md`
- 字段口径说明：`docs/graduation/EXPERIMENT_RECORD_FIELDS.md`
- 错误码说明：`docs/graduation/ERROR_CODES.md`
- 文献补库清单：`docs/graduation/论文库盘点_已在库与待补充.md`
