// web/src/api/runs.js

import { request } from "./http";

export const runsApi = {
  /**
   * 创建 Run
   * @param {{task_type:string,dataset_id:string,algorithm_id:string,params?:object}} payload
   */
  createRun(payload) {
    return request("/runs", { method: "POST", body: payload });
  },

  /**
   * 获取 Run 详情
   * @param {string} runId
   */
  getRun(runId) {
    return request(`/runs/${runId}`);
  },

  /**
   * 列表查询 Runs
   * @param {{limit?:number}} query
   */
  listRuns(query = {}) {
    return request("/runs", { query });
  },

  cancelRun(runId) {
    return request(`/runs/${runId}/cancel`, { method: "POST" });
  },

  /**
   * 核心算法快速选型 Top-K
   * @param {{task_type:string,dataset_id:string,candidate_algorithm_ids?:string[],top_k?:number,alpha?:number}} payload
   */
  fastSelect(payload) {
    return request("/recommend/fast-select", { method: "POST", body: payload });
  },
};
