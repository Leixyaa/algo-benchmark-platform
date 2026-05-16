# 运行创建相关错误码说明

以下内容用于说明 `POST /runs` 常见错误，便于前端提示与答辩说明。

## 1. 错误返回结构

FastAPI 返回统一结构：

```json
{
  "detail": {
    "error_code": "E_XXX",
    "error_message": "可读错误信息",
    "error_detail": {
      "task_type": "...",
      "dataset_id": "..."
    }
  }
}
```

前端应优先读取 `detail.error_code` 与 `detail.error_message`，并在需要时展示 `error_detail`。

## 2. POST /runs 常见错误

### E_BAD_TASK_TYPE（400）
- `task_type` 不在支持列表中。
- 返回可选任务类型用于前端修正。

### E_DATASET_ID_REQUIRED（400）
- 请求体缺少 `dataset_id`。

### E_ALGORITHM_ID_REQUIRED（400）
- 请求体缺少 `algorithm_id`。

### E_DATASET_NOT_FOUND（404）
- 指定的数据集不存在。

### E_ALGORITHM_NOT_FOUND（404）
- 指定的算法不存在。

### E_ALGORITHM_TASK_MISMATCH（409）
- 算法所属任务与 `task_type` 不一致。
- `error_detail` 会给出期望任务与实际任务，便于定位。

### E_DATASET_NO_PAIR（409）
- 在 `strict_validate=true` 下，当前数据集在该任务下无有效配对。
- `error_detail` 会包含 `expected_dirs` 与 `pair_count`。

## 3. 排查建议
- 若报 `E_DATASET_NO_PAIR`：先检查输入目录与 `gt/` 同名文件，再执行 `scan`。
- 若报 `E_ALGORITHM_TASK_MISMATCH`：确认算法 task 标签与运行任务一致。
- 若报 4xx 参数错误：先校验请求体，再重试创建 Run。
