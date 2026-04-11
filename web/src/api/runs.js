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
};

