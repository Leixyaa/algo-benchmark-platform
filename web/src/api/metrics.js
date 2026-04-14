import { request } from "./http";

export const metricsApi = {
  listMetrics(query = {}) {
    return request("/metrics", { method: "GET", query });
  },
  listSubmissionHistory() {
    return request("/history/metric-submissions", { method: "GET" });
  },
  clearSubmissionHistory() {
    return request("/history/metric-submissions", { method: "DELETE" });
  },
  deleteSubmissionHistoryItem(historyId) {
    return request(`/history/metric-submissions/${historyId}`, { method: "DELETE" });
  },
  deleteSubmissionHistoryBatch(historyIds = []) {
    return request("/history/metric-submissions/delete-batch", {
      method: "POST",
      body: { history_ids: historyIds },
    });
  },
  createMetric(body) {
    return request("/metrics", { method: "POST", body });
  },
  patchMetric(metricId, body) {
    return request(`/metrics/${metricId}`, { method: "PATCH", body });
  },
  deleteMetric(metricId) {
    return request(`/metrics/${metricId}`, { method: "DELETE" });
  },
  publishMetricToCommunity(metricId, body = {}) {
    return request(`/metrics/${metricId}/publish-community`, { method: "POST", body });
  },
  unpublishMetricFromCommunity(metricId) {
    return request(`/metrics/${metricId}/unpublish-community`, { method: "POST" });
  },
  downloadCommunityMetric(metricId) {
    return request(`/community/metrics/${metricId}/download`, { method: "POST" });
  },
  listAdminMetrics(query = {}) {
    return request("/admin/metrics", { method: "GET", query });
  },
  reviewMetric(metricId, body) {
    return request(`/admin/metrics/${metricId}/review`, { method: "POST", body });
  },
};
