import { request } from "./http";
import { downloadBinaryFile } from "./download";

export const datasetsApi = {
  async listDatasets({ limit = 200, scope = "manage" } = {}) {
    return request("/datasets", { method: "GET", query: { limit, scope } });
  },
  async createDataset(payload) {
    return request("/datasets", { method: "POST", body: payload });
  },
  async patchDataset(datasetId, patch) {
    return request(`/datasets/${datasetId}`, { method: "PATCH", body: patch });
  },
  async changeDatasetId(datasetId, newDatasetId) {
    return request(`/datasets/${datasetId}/change_id`, { method: "POST", body: { new_dataset_id: newDatasetId } });
  },
  async deleteDataset(datasetId, options = {}) {
    return request(`/datasets/${datasetId}`, {
      method: "DELETE",
      query: { delete_disk: options?.deleteDisk ? "true" : "false" },
    });
  },
  async scanDataset(datasetId) {
    return request(`/datasets/${datasetId}/scan`, { method: "POST" });
  },
  async importZip(datasetId, payload) {
    return request(`/datasets/${datasetId}/import_zip`, { method: "POST", body: payload });
  },
  async downloadCommunityDataset(datasetId) {
    return request(`/community/datasets/${datasetId}/download`, { method: "POST" });
  },
  async exportDataset(datasetId) {
    return downloadBinaryFile(`/datasets/${datasetId}/export`, `${datasetId}.zip`);
  },
};
