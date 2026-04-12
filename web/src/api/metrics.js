import { request } from "./http";

export const metricsApi = {
  listMetrics(query = {}) {
    return request("/metrics", { method: "GET", query });
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
