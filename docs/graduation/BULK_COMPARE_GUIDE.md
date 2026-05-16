# 批量评测与对比使用说明

本文用于说明如何在 Compare 页面发起批量评测，并在同一批次内完成对比、推荐与导出。

## 1. 前置条件
- 后端 API、Worker、Redis 均已启动。
- 数据集已完成扫描，且对应任务存在有效配对（输入目录与 `gt/` 同名文件）。
- 算法库中已存在可用于该任务的候选算法。

## 2. 在 Compare 页面执行批量评测
建议顺序：
1. 选择任务类型与数据集。
2. 选择参数策略（默认 / 速度优先 / 质量优先）。
3. 点击“批量创建基线 Run”。
   - 如开启 `strict_validate`，系统会先校验配对关系，不通过则拒绝创建。
   - 系统会自动跳过已存在的同任务-同数据集-同算法组合。
   - 每次批量创建会生成批次信息，便于后续筛选与复盘。

批次信息会写入每个 Run 的 `params` / `record`，可通过 `batch_id` 在导出文件中追踪。

## 3. 对比与推荐
- 等待本批次 Run 进入终态（建议以 `done` 为主）后进入 Compare。
- Compare 会按指标权重生成综合排序，并输出推荐结论与理由。

## 4. 导出内容
Compare 支持导出：
- 对比结果 CSV / Excel（全字段）
- 推荐结果 CSV / Excel（包含综合评分与原因）
- 结论 Markdown（推荐算法、原因、Top10 明细）

Runs 页面 `/runs/export` 导出的核心字段包括：
- `task_label`, `dataset_name`, `algorithm_name`, `algorithm_task`
- `batch_id`, `batch_name`, `param_scheme`
- `strict_validate`, `data_mode`, `input_dir`, `pair_total`, `pair_used`
- `params_json`, `samples_json`, `record_json`
