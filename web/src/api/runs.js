// web/src/api/runs.js

import { request } from "./http";

export const runsApi = {
  /**
   * ???? Run
   * @param {{task_type:string,dataset_id:string,algorithm_id:string,params?:object}} payload
   */
  createRun(payload) {
    return request("/runs", { method: "POST", body: payload });
  },

  /**
   * ??? Run
   * @param {string} runId
   */
  getRun(runId) {
    return request(`/runs/${runId}`);
  },

  /**
   * ?§Ô? Runs
   * @param {{limit?:number}} query
   */
  listRuns(query = {}) {
    return request("/runs", { query });
  },

  cancelRun(runId) {
    return request(`/runs/${runId}/cancel`, { method: "POST" });
  },
};
