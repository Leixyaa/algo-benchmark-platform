# 实验记录字段说明（Run）

本文用于统一 Run 记录字段口径，保证“可复现、可解释、可导出”。

## 1. Run 主字段
- `run_id`：运行唯一 ID
- `task_type`：任务类型（denoise / deblur / dehaze / sr / lowlight / video_denoise / video_sr）
- `dataset_id`：数据集 ID
- `algorithm_id`：算法 ID
- `status`：状态（queued/running/done/failed/canceling/canceled）
- `created_at/started_at/finished_at/elapsed`：时间与耗时字段
- `metrics`：指标对象（PSNR/SSIM/NIQE）
- `params`：运行参数（含业务参数与可选控制参数）
- `samples`：样本明细（可选）
- `error/error_code/error_detail`：失败信息

## 2. strict_validate 规则
- 当 `strict_validate=true`：
  - 若输入目录与 `gt/` 无有效同名配对，创建 Run 直接返回 409。
  - 不会进入执行阶段，避免产生无效实验结果。

## 3. record 字段建议
`record` 用于保留运行上下文，建议至少包含：
- `task_type`
- `seed`
- `strict_validate`
- `worker`
  - `host`
  - `pid`
  - `python`
- `dataset`
  - `dataset_id/name/type/size`
  - `meta`（支持任务、配对计数等）
- `algorithm`
  - `algorithm_id/task/name/impl/version`
- `data_mode`
  - `paired_images`
  - `synthetic_no_dataset`
- `input_dir`（hazy/noisy/blur/lr/dark）
- `pair_total`
- `pair_used`

## 4. 导出字段对应
`/runs/export`（csv/xlsx）中建议保留：
- `task_label`
- `dataset_name` / `algorithm_name` / `algorithm_task`
- `strict_validate` / `data_mode` / `input_dir` / `pair_total` / `pair_used`
- `params_json` / `samples_json` / `record_json`
