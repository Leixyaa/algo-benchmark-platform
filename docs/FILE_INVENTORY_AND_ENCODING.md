# 项目文件清单与编码规范

更新时间：2026-05-16

## 编码约定

- 文本文件统一使用 UTF-8 编码。
- 文本换行默认使用 LF，Windows 启动脚本按 `.gitattributes` 约定处理。
- 二进制文件保持原始格式，不做文本化处理。
- VSCode 工作区固定 `files.encoding = utf8`，避免中文资料被误判编码。

## 核心目录

| 路径 | 用途 |
| :-- | :-- |
| `backend/` | FastAPI、Celery、Redis/SQL 存储与评测执行后端 |
| `web/` | Vue3 + Vite 前端界面 |
| `desktop/` | Electron 桌面端壳 |
| `scripts/` | Windows 启动、构建与演示辅助脚本 |
| `docs/` | 工程说明、AI 问答知识库、答辩验收轻量文档 |
| `release/` | 交付包与桌面运行包 |

## 重点文件

| 文件 | 用途 |
| :-- | :-- |
| `backend/app/main.py` | 后端 API 主入口 |
| `backend/app/tasks.py` | Worker 执行、指标计算、失败回写 |
| `backend/app/algorithm_runtime.py` | 用户算法包运行时 |
| `backend/app/metric_runtime.py` | 指标运行时 |
| `backend/app/selector.py` | 已置空，旧快速选型流程已移除 |
| `web/src/views/Datasets.vue` | 数据集管理 |
| `web/src/views/Algorithms.vue` | 算法库与算法接入 |
| `web/src/views/NewRun.vue` | 评测任务创建 |
| `web/src/views/Runs.vue` | 任务状态、详情、取消与导出 |
| `web/src/views/Compare.vue` | 多任务对比、权重排序推荐与导出 |
| `web/src/views/Admin.vue` | 管理后台 |
| `docs/AI_PLATFORM_KNOWLEDGE_BASE.md` | AI 辅助问答知识库 |
| `docs/graduation/README.md` | 答辩与验收文档入口 |
| `scripts/manual_up.ps1` | 本地一键启动脚本 |

## 当前口径

- 项目不包含 LinUCB、多臂赌博机或 `POST /recommend/fast-select` 快速选型接口。
- Compare 页面保留的是多任务对比、权重排序推荐、批量基线与导出能力。
- 前端依赖以 `web/package.json` 为准，新环境请在 `web/` 目录执行 `npm install`。
