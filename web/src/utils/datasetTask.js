/**
 * 判断数据集是否支持某评测任务（优先 task_types，其次扫描得到的 pairs_by_task）。
 * @param {object} ds mapDatasetOut 结果或含 raw/meta 的对象
 * @param {string} taskTypeKey denoise / dehaze / sr / video_denoise 等
 */
export function datasetSupportsTaskType(ds, taskTypeKey) {
  if (!taskTypeKey) return true;
  const explicit = Array.isArray(ds?.taskTypes) && ds.taskTypes.length
    ? ds.taskTypes
    : Array.isArray(ds?.raw?.task_types)
      ? ds.raw.task_types
      : [];
  if (explicit.length) return explicit.includes(taskTypeKey);
  const supported =
    (Array.isArray(ds?.meta?.supported_task_types) && ds.meta.supported_task_types) ||
    (Array.isArray(ds?.raw?.meta?.supported_task_types) && ds.raw.meta.supported_task_types) ||
    [];
  if (supported.length) return supported.includes(taskTypeKey);
  const pairs = ds?.meta?.pairs_by_task || ds?.raw?.meta?.pairs_by_task;
  if (pairs && typeof pairs === "object") {
    return Number(pairs[taskTypeKey] ?? 0) > 0;
  }
  return false;
}

/** 是否已有扫描/协议可识别的适用任务（用于发布社区等，不等同于支持某一具体任务） */
export function datasetHasRecognizedTasks(ds) {
  const explicit = Array.isArray(ds?.taskTypes) && ds.taskTypes.length
    ? ds.taskTypes
    : Array.isArray(ds?.raw?.task_types)
      ? ds.raw.task_types
      : [];
  if (explicit.length) return true;
  const supported =
    (Array.isArray(ds?.meta?.supported_task_types) && ds.meta.supported_task_types) ||
    (Array.isArray(ds?.raw?.meta?.supported_task_types) && ds.raw.meta.supported_task_types) ||
    [];
  if (supported.length) return true;
  const pairs = ds?.meta?.pairs_by_task || ds?.raw?.meta?.pairs_by_task;
  if (pairs && typeof pairs === "object") {
    return Object.values(pairs).some((n) => Number(n) > 0);
  }
  return false;
}
