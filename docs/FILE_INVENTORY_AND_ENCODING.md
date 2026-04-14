# 项目文件清单与编码规范

更新时间：2026-04-14（与当前仓库同步）

## 编码约定
- 文本文件统一使用 `UTF-8` 编码。
- 文本换行统一为 `LF`。
- 二进制文件保持原始格式，不做文本化处理。
- VSCode 工作区固定 `files.encoding = utf8`，并关闭自动猜测编码。
- 建议终端固定 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`，避免脚本写库或写文件时把中文替换成 `?`。
- 交付前建议执行 `python scripts/check_utf8.py`，同时检查非 UTF-8 文件与可疑乱码模式。

## 核心目录
| 路径 | 用途 | 编码 |
| :-- | :-- | :-- |
| `backend/` | FastAPI、Celery、Redis 相关后端实现 | UTF-8 |
| `web/` | Vue3 + Vite 前端界面与交互 | UTF-8 |
| `docs/` | 项目说明、交付材料、过程文档 | UTF-8 |
| `scripts/` | Windows 启动、环境辅助脚本 | UTF-8 |

## 当前重点文件
| 文件 | 作用 |
| :-- | :-- |
| `backend/app/main.py` | 后端 API 主入口 |
| `backend/app/tasks.py` | Worker 执行、指标计算、失败回写 |
| `backend/app/selector.py` | LinUCB 快速选型 |
| `web/src/views/NewRun.vue` | 运行创建与预设应用 |
| `web/src/views/Runs.vue` | 运行列表、详情、导出、取消 |
| `web/src/views/Compare.vue` | 对比推荐、批量运行、快速选型、导出 |
| `web/src/utils/datasetTask.js` | 数据集与任务类型匹配（`pairs_by_task` / `task_types` 等） |
| `web/src/views/LayoutBrand2.vue` | 系统框架布局（社区页不 keep-alive 等） |
| `web/src/views/LoginBrand.vue` | 登录入口 |
| `web/src/views/RegisterBrand.vue` | 注册入口 |
| `web/src/api/http.js` | 统一请求与鉴权处理 |
| `docs/SYSTEM_FUNCTION_OVERVIEW.md` | 系统功能总览 |
| `docs/graduation/README.md` | 毕设相关模板说明 |
| `docs/graduation/系统验收准备文档.md` | 验收演示与版本结论 |
| `backend/app/store.py` | Redis 存储；与 SQL 双写合并取较新 |
| `backend/app/sql_store.py` | SQL 表结构、DDL 重试（含 MySQL 1683/1684） |
| `backend/tools/sample_algorithm_denoise.py` | 算法接入示例脚本（原 `docs/项目资料/test_algorithm_denoise.py` 已迁移） |
| `scripts/demo_preflight_check.ps1` | 演示前端口与 `.env.local` 自检 |

## 仓库根目录说明（当前）

- **根目录不再提供 `package.json` / `node_modules`**；前端依赖以 `web/package.json` 为准，请在 `web/` 目录执行 `npm install`。

## 2026-04-01 清洗结果
- 已修复 `Compare.vue` 的重复函数声明，恢复前端可编译状态。
- 已清理核心入口页面模板层乱码：`Layout / Login / Register / Runs / Compare`。
- 已统一 `Runs / Compare` 的导出、清理、取消、图表空态、评分理由等关键提示文案，减少界面层乱码暴露。
- 已确认 `backend/app/tasks.py` 按所选指标执行，而不是固定计算全部指标。
- 已修复当前演示账号下的数据集与自定义算法名称乱码，并同步回写现有 Run 快照。
- 已增强 `scripts/check_utf8.py`，新增对连续问号、`\ufffd` 及常见乱码片段的复扫能力。

## 仍需继续跟踪
- `Runs.vue` 与 `Compare.vue` 的核心可见文案已完成清洗，后续主要关注低频路径与旧文件再次编辑时的编码漂移风险。
- 其他旧页面与文档建议继续做一次 UTF-8 复扫，避免后续编辑时再次漂移。
