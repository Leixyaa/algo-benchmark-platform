import { request } from "./http";

export const feedbackApi = {
  submit(payload) {
    return request("/feedback", { method: "POST", body: payload || {} });
  },
};
