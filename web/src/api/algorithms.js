import { request } from "./http";
import { downloadBinaryFile } from "./download";

export const algorithmsApi = {
  async listAlgorithms({ limit = 500, scope = "manage" } = {}) {
    return request("/algorithms", { method: "GET", query: { limit, scope } });
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
  async resetUserAlgorithms() {
    return request("/algorithms/reset_user", { method: "POST" });
  },
  async downloadCommunityAlgorithm(algorithmId) {
    return request(`/community/algorithms/${algorithmId}/download`, { method: "POST" });
  },
  async exportAlgorithm(algorithmId, filename = "", options = {}) {
    return downloadBinaryFile(`/algorithms/${algorithmId}/export`, filename || `${algorithmId}.json`, options);
  },
};
