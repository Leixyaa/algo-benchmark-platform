import { request } from "./http";

export const communityApi = {
  async listAlgorithmComments(algorithmId) {
    return request(`/community/algorithms/${algorithmId}/comments`, { method: "GET" });
  },
  async createAlgorithmComment(algorithmId, content) {
    return request(`/community/algorithms/${algorithmId}/comments`, {
      method: "POST",
      body: { content },
    });
  },
  async deleteAlgorithmComment(algorithmId, commentId) {
    return request(`/community/algorithms/${algorithmId}/comments/${commentId}`, {
      method: "DELETE",
    });
  },
  async listDatasetComments(datasetId) {
    return request(`/community/datasets/${datasetId}/comments`, { method: "GET" });
  },
  async createDatasetComment(datasetId, content) {
    return request(`/community/datasets/${datasetId}/comments`, {
      method: "POST",
      body: { content },
    });
  },
  async deleteDatasetComment(datasetId, commentId) {
    return request(`/community/datasets/${datasetId}/comments/${commentId}`, {
      method: "DELETE",
    });
  },
  async createReport(payload) {
    return request("/community/reports", {
      method: "POST",
      body: payload,
    });
  },
};
