import { request } from "./http";

export const algorithmsApi = {
  async listAlgorithms({ limit = 500 } = {}) {
    return request("/algorithms", { method: "GET", query: { limit } });
  },
  async createAlgorithm(payload) {
    return request("/algorithms", { method: "POST", body: payload });
  },
  async patchAlgorithm(algorithmId, patch) {
    return request(`/algorithms/${algorithmId}`, { method: "PATCH", body: patch });
  },
  async deleteAlgorithm(algorithmId) {
    return request(`/algorithms/${algorithmId}`, { method: "DELETE" });
  },
};

