// web/src/api/runs.js
// /runs 相关 API 封装：让 store/视图层不直接拼 URL。

import { request } from "./http";

export const runsApi = {
  /**
   * 创建一次评测 Run
   * @param {{task_type:string,dataset_id:string,algorithm_id:string,params?:object}} payload
   */
  createRun(payload) {
    return request("/runs", { method: "POST", body: payload });
  },

  /**
   * 获取单条 Run
   * @param {string} runId
   */
  getRun(runId) {
    return request(`/runs/${runId}`);
  },

  /**
   * 获取 Run 列表（后端按 created_at 倒序返回）
   * @param {{limit?:number}} query
   */
  listRuns(query = {}) {
    return request("/runs", { query });
  },

  cancelRun(runId) {
    return request(`/runs/${runId}/cancel`, { method: "POST" });
  },
};
