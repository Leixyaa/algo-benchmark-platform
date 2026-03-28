# 项目文件清单与编码规范

> 生成时间：2026-03-23\
> 说明：本清单覆盖当前仓库代码、脚本、配置与文档文件；用于毕设交付审查与编码规范核对。\
> 编码约定：文本文件统一 `UTF-8`（无 BOM，LF 换行），二进制文件保持原始二进制格式。

| 文件                                                        | 作用                                       | 编码                 |
| :-------------------------------------------------------- | :--------------------------------------- | :----------------- |
| `.editorconfig`                                           | 编辑器统一格式规则                                | UTF-8              |
| `.gitignore`                                              | Git 忽略规则                                 | UTF-8              |
| `AGENTS.md`                                               | 项目长期约束、开发日志、待办跟踪                         | UTF-8              |
| `package.json`                                            | 根目录 Node 依赖与脚本入口                         | UTF-8              |
| `package-lock.json`                                       | 根目录依赖锁文件                                 | UTF-8              |
| `scripts/check_utf8.py`                                   | 全仓 UTF-8 合规检测脚本                          | UTF-8              |
| `scripts/dev.cmd`                                         | Windows 一键开发启动脚本（cmd）                    | UTF-8              |
| `scripts/dev.ps1`                                         | Windows 一键开发启动脚本（PowerShell）             | UTF-8              |
| `backend/requirements.txt`                                | 后端 Python 依赖清单                           | UTF-8              |
| `backend/app/__init__.py`                                 | 后端包初始化                                   | UTF-8              |
| `backend/app/celery_app.py`                               | Celery 应用配置与任务注册                         | UTF-8              |
| `backend/app/errors.py`                                   | 统一错误码定义与 API 错误映射                        | UTF-8              |
| `backend/app/main.py`                                     | FastAPI 主入口与全部业务路由                       | UTF-8              |
| `backend/app/schemas.py`                                  | Pydantic 请求/响应模型定义                       | UTF-8              |
| `backend/app/selector.py`                                 | 核心算法模块（LinUCB 快速选型）                      | UTF-8              |
| `backend/app/store.py`                                    | Redis 存取封装（run/dataset/algorithm/preset） | UTF-8              |
| `backend/app/tasks.py`                                    | Worker 执行逻辑、指标计算、重试与取消                   | UTF-8              |
| `backend/app/vision/dataset_io.py`                        | 数据集扫描、图像/视频配对与计数                         | UTF-8              |
| `backend/app/vision/dehaze_dcp.py`                        | 去雾基线算法实现（DCP）                            | UTF-8              |
| `backend/app/vision/niqe_simple.py`                       | NIQE 指标简化实现                              | UTF-8              |
| `backend/tools/check_exports.py`                          | 导出结果一致性校验脚本                              | UTF-8              |
| `backend/tools/e2e_smoke.py`                              | 后端端到端冒烟脚本                                | UTF-8              |
| `backend/tools/eval_fast_select.py`                       | 快速选型算法对比实验脚本                             | UTF-8              |
| `backend/tools/import_kodak24_denoise.py`                 | Kodak24 去噪数据导入脚本                         | UTF-8              |
| `backend/tools/make_sample_dataset_zip.py`                | 样例数据集压缩包生成脚本                             | UTF-8              |
| `backend/tools/smoke_kodak24_denoise.py`                  | Kodak24 去噪冒烟脚本                           | UTF-8              |
| `backend/tools/smoke_cancel_race.py`                      | 取消竞争态冒烟脚本                                | UTF-8              |
| `backend/data/ds_demo/gt/1400.png`                        | Demo 数据 GT 图像                            | Binary (PNG)       |
| `backend/data/ds_demo/gt/1401.png`                        | Demo 数据 GT 图像                            | Binary (PNG)       |
| `backend/data/ds_demo/gt/1402.png`                        | Demo 数据 GT 图像                            | Binary (PNG)       |
| `backend/data/ds_demo/gt/1403.png`                        | Demo 数据 GT 图像                            | Binary (PNG)       |
| `backend/data/ds_demo/gt/1404.png`                        | Demo 数据 GT 图像                            | Binary (PNG)       |
| `backend/data/ds_demo/hazy/1400.png`                      | Demo 数据输入图像（hazy）                        | Binary (PNG)       |
| `backend/data/ds_demo/hazy/1401.png`                      | Demo 数据输入图像（hazy）                        | Binary (PNG)       |
| `backend/data/ds_demo/hazy/1402.png`                      | Demo 数据输入图像（hazy）                        | Binary (PNG)       |
| `backend/data/ds_demo/hazy/1403.png`                      | Demo 数据输入图像（hazy）                        | Binary (PNG)       |
| `backend/data/ds_demo/hazy/1404.png`                      | Demo 数据输入图像（hazy）                        | Binary (PNG)       |
| `docs/UPLOAD_GUIDE.md`                                    | 毕设资料提交与组织说明                              | UTF-8              |
| `docs/FILE_INVENTORY_AND_ENCODING.md`                     | 文件作用与编码总表（本文件）                           | UTF-8              |
| `docs/README.md`                                          | 文档目录总索引（快速入口）                             | UTF-8              |
| `docs/SYSTEM_FUNCTION_OVERVIEW.md`                        | 项目系统功能总览（快速了解）                            | UTF-8              |
| `docs/graduation/.gitignore`                              | 毕设文档目录白名单规则                              | UTF-8              |
| `docs/graduation/README.md`                               | 毕设资料目录说明                                 | UTF-8              |
| `docs/graduation/REQUIREMENTS_EXTRACTED_TEMPLATE.md`      | 学校要求摘录模板                                 | UTF-8              |
| `docs/graduation/BULK_COMPARE_GUIDE.md`                   | 批量评测与对比导出使用说明                            | UTF-8              |
| `docs/graduation/ERROR_CODES.md`                          | 运行创建常见错误码与排查说明                           | UTF-8              |
| `docs/graduation/EXPERIMENT_RECORD_FIELDS.md`             | Run 记录字段与导出口径说明                            | UTF-8              |
| `docs/graduation/PROCESS_LOG.md`                          | 过程开发摘要记录                                 | UTF-8              |
| `docs/graduation/系统架构_流程_ER_实现说明.md`                      | 系统设计总说明（架构/流程/ER/实现）                     | UTF-8              |
| `docs/graduation/答辩交付_演示脚本_验收清单_论文章节映射.md`                | 答辩交付总文档                                  | UTF-8              |
| `docs/graduation/核心算法_快速选型模块说明.md`                        | 核心算法模块设计说明                               | UTF-8              |
| `docs/graduation/核心算法_快速选型_实验小节（可直接入论文）.md`               | 快速选型实验小节草稿                               | UTF-8              |
| `docs/导出文件/去噪/compare_conclusion_2026-02-14-04-01-27.md`  | 对比结论导出样例（去噪）                             | UTF-8              |
| `docs/导出文件/去模糊/compare_conclusion_2026-02-14-04-00-38.md` | 对比结论导出样例（去模糊）                            | UTF-8              |
| `docs/导出文件/去雾/compare_conclusion_2026-02-14-03-59-12.md`  | 对比结论导出样例（去雾）                             | UTF-8              |
| `web/.gitignore`                                          | 前端忽略规则                                   | UTF-8              |
| `web/README.md`                                           | 前端项目说明                                   | UTF-8              |
| `web/index.html`                                          | Vite 页面入口模板                              | UTF-8              |
| `web/package.json`                                        | 前端依赖与脚本                                  | UTF-8              |
| `web/package-lock.json`                                   | 前端依赖锁文件                                  | UTF-8              |
| `web/vite.config.js`                                      | 前端构建配置                                   | UTF-8              |
| `web/public/vite.svg`                                     | 前端公共静态资源                                 | Binary (SVG/UTF-8) |
| `web/src/main.js`                                         | 前端启动入口                                   | UTF-8              |
| `web/src/App.vue`                                         | 根组件                                      | UTF-8              |
| `web/src/style.css`                                       | 全局样式                                     | UTF-8              |
| `web/src/router/index.js`                                 | 路由定义                                     | UTF-8              |
| `web/src/api/http.js`                                     | 通用 HTTP 请求封装                             | UTF-8              |
| `web/src/api/algorithms.js`                               | 算法 API 封装                                | UTF-8              |
| `web/src/api/datasets.js`                                 | 数据集 API 封装                               | UTF-8              |
| `web/src/api/presets.js`                                  | 预设 API 封装                                | UTF-8              |
| `web/src/api/runs.js`                                     | Run 与快速选型 API 封装                         | UTF-8              |
| `web/src/stores/app.js`                                   | Pinia 主状态与业务动作                           | UTF-8              |
| `web/src/views/Layout.vue`                                | 页面布局框架                                   | UTF-8              |
| `web/src/views/Datasets.vue`                              | 数据集管理页面                                  | UTF-8              |
| `web/src/views/Algorithms.vue`                            | 算法管理页面                                   | UTF-8              |
| `web/src/views/NewRun.vue`                                | 新建运行页面                                   | UTF-8              |
| `web/src/views/Runs.vue`                                  | 运行列表与详情页面                                | UTF-8              |
| `web/src/views/Compare.vue`                               | 对比推荐页面（含快速选型接入）                          | UTF-8              |
| `web/src/assets/vue.svg`                                  | 前端示例图标                                   | Binary (SVG/UTF-8) |

## 已处理的过期/异常项

- 已删除过期规划文件：`docs/PROJECT_MASTER_PLAN.md`（由当前交付文档链替代）。
- 已更新 AGENTS 中对过期规划文件的引用，避免无效链接。
- 已将以下非 UTF-8 文件统一转为 UTF-8：
  - `docs/graduation/系统架构_流程_ER_实现说明.md`
  - `docs/graduation/答辩交付_演示脚本_验收清单_论文章节映射.md`
  - `docs/graduation/核心算法_快速选型模块说明.md`
  - `docs/graduation/核心算法_快速选型_实验小节（可直接入论文）.md`
  - `web/src/views/Compare.vue`
  - `web/src/views/Runs.vue`
- 已将实验文档标记为草稿，避免在系统未完全收口前误用最终数字。
- 已删除无必要兼容文件：`web/src/views/Tasks.vue`。
- 已删除默认示例文件：`web/src/components/HelloWorld.vue`。

## 编码检查命令

```bash
python scripts/check_utf8.py
```
