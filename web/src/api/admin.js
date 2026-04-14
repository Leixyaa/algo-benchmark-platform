import { request } from "./http";

export const adminApi = {
  listRegisteredUsers() {
    return request("/admin/users", { method: "GET" });
  },
  promoteCommunityAlgorithm(algorithmId) {
    return request(`/admin/community/algorithms/${algorithmId}/promote`, { method: "POST" });
  },
  listCommunityAlgorithms() {
    return request("/admin/community/algorithms", { method: "GET" });
  },
  getCommunityAlgorithmDetail(algorithmId) {
    return request(`/admin/community/algorithms/${algorithmId}`, { method: "GET" });
  },
  listCommunityDatasets() {
    return request("/admin/community/datasets", { method: "GET" });
  },
  getCommunityDatasetDetail(datasetId) {
    return request(`/admin/community/datasets/${datasetId}`, { method: "GET" });
  },
  listComments() {
    return request("/admin/comments", { method: "GET" });
  },
  takedownAlgorithm(algorithmId) {
    return request(`/admin/community/algorithms/${algorithmId}/takedown`, { method: "POST" });
  },
  takedownDataset(datasetId) {
    return request(`/admin/community/datasets/${datasetId}/takedown`, { method: "POST" });
  },
  deleteComment(resourceType, resourceId, commentId) {
    return request(`/admin/comments/${resourceType}/${resourceId}/${commentId}`, { method: "DELETE" });
  },
  listReports() {
    return request("/admin/reports", { method: "GET" });
  },
  resolveReport(reportId, payload) {
    return request(`/admin/reports/${reportId}/resolve`, {
      method: "POST",
      body: payload,
    });
  },
  clearReports(status = "handled") {
    return request(`/admin/reports/clear?status=${encodeURIComponent(status)}`, {
      method: "POST",
    });
  },
  listMetrics(status) {
    return request("/admin/metrics", { method: "GET", query: status ? { status } : {} });
  },
  reviewMetric(metricId, payload) {
    return request(`/admin/metrics/${metricId}/review`, {
      method: "POST",
      body: payload,
    });
  },
  listAlgorithmSubmissions(status) {
    return request("/admin/algorithm-submissions", { method: "GET", query: status ? { status } : {} });
  },
  reviewAlgorithmSubmission(submissionId, payload) {
    return request(`/admin/algorithm-submissions/${submissionId}/review`, {
      method: "POST",
      body: payload,
    });
  },
  promoteAlgorithmSubmission(submissionId) {
    return request(`/admin/algorithm-submissions/${submissionId}/promote-platform`, { method: "POST" });
  },
};
