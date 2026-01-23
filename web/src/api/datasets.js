import { request } from "./http";

export const datasetsApi = {
  async listDatasets({ limit = 200 } = {}) {
    return request("/datasets", { method: "GET", query: { limit } });
  },
  async createDataset(payload) {
    return request("/datasets", { method: "POST", body: payload });
  },
  async patchDataset(datasetId, patch) {
    return request(`/datasets/${datasetId}`, { method: "PATCH", body: patch });
  },
  async deleteDataset(datasetId) {
    return request(`/datasets/${datasetId}`, { method: "DELETE" });
  },
  async scanDataset(datasetId) {
    return request(`/datasets/${datasetId}/scan`, { method: "POST" });
  },
  async importZip(datasetId, payload) {
    return request(`/datasets/${datasetId}/import_zip`, { method: "POST", body: payload });
  },
};

