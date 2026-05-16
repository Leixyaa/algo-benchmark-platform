# 项目系统功能总览

## 一句话说明

本项目是面向图像与视频增强复原任务的开放式算法性能测试平台，目标是实现数据集、算法、指标、任务执行、结果对比和报告导出的统一评测闭环。

## 主线闭环

数据集管理 -> 算法/指标接入 -> 创建评测任务 -> Celery 异步执行 -> 指标计算 -> Compare 对比分析 -> CSV/XLSX/Markdown 导出。

## 已支持任务

- 图像任务：`denoise`、`deblur`、`dehaze`、`sr`、`lowlight`
- 视频任务：`video_denoise`、`video_sr`

## 核心能力

- 数据集扫描、ZIP 导入、目录配对和 strict_validate 校验
- 算法库与指标库管理，支持用户算法包和自定义指标接入
- Run 生命周期管理：排队、执行、取消、失败回写、记录留痕
- 指标计算：PSNR、SSIM、NIQE 等
- Compare 多任务横向对比、权重排序推荐和报告导出
- 社区资源共享、评论、举报、通知中心与管理后台审核
- Web 与 Electron 桌面端演示交付

## 当前口径

- `backend/app/selector.py` 已置空。
- 项目不包含 LinUCB、多臂赌博机或 `POST /recommend/fast-select` 快速选型接口。
- 答辩与论文不再将旧快速选型作为功能、创新点或实验内容。

## 建议优先阅读

- `docs/graduation/答辩交付_演示脚本_验收清单_论文章节映射.md`
- `docs/graduation/导师演示_全流程操作手册.md`
- `docs/graduation/系统验收准备文档_完整答辩版.md`
- `docs/graduation/系统总测试表_验收版.md`
- `docs/graduation/演示数据固化清单.md`
