import { request } from "./http";

export const aiApi = {
  chat(payload) {
    return request("/ai/chat", { method: "POST", body: payload || {} });
  },
};

