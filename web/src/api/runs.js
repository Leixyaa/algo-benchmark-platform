// web/src/api/runs.js

import { request } from "./http";

export const runsApi = {
  /**
   * 鍒涘缓 Run
   * @param {{task_type:string,dataset_id:string,algorithm_id:string,params?:object}} payload
   */
  createRun(payload) {
    return request("/runs", { method: "POST", body: payload });
  },

  /**
   * 拉取 Run 列表
   * @param {{limit?: number, status?: string, task_type?: string, dataset_id?: string, algorithm_id?: string}} query
   */
  listRuns(query = {}) {
    return request("/runs", { method: "GET", query });
  },

  /**
   * 拉取单个 Run
   * @param {string} runId
   */
  getRun(runId) {
    return request(`/runs/${runId}`, { method: "GET" });
  },

  /**
   * 取消 Run
   * @param {string} runId
   */
  cancelRun(runId) {
    return request(`/runs/${runId}/cancel`, { method: "POST" });
  },
};

