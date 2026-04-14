import { request } from "./http";
import { downloadBinaryFile } from "./download";

export const algorithmSubmissionsApi = {
  listMine() {
    return request("/algorithm-submissions", { method: "GET" });
  },
  listHistory() {
    return request("/history/algorithm-submissions", { method: "GET" });
  },
  clearHistory() {
    return request("/history/algorithm-submissions", { method: "DELETE" });
  },
  deleteHistoryItem(historyId) {
    return request(`/history/algorithm-submissions/${historyId}`, { method: "DELETE" });
  },
  deleteHistoryBatch(historyIds = []) {
    return request("/history/algorithm-submissions/delete-batch", {
      method: "POST",
      body: { history_ids: historyIds },
    });
  },
  createSubmission(body) {
    return request("/algorithm-submissions", { method: "POST", body });
  },
  publishToCommunity(submissionId, body = {}) {
    return request(`/algorithm-submissions/${submissionId}/publish-community`, { method: "POST", body });
  },
  unpublishFromCommunity(submissionId) {
    return request(`/algorithm-submissions/${submissionId}/unpublish-community`, { method: "POST" });
  },
  downloadArchive(submissionId, filename = "algorithm_package.zip") {
    return downloadBinaryFile(`/algorithm-submissions/${submissionId}/download`, filename);
  },
  downloadHistoryArchive(historyId, filename = "algorithm_package.zip") {
    return downloadBinaryFile(`/history/algorithm-submissions/${historyId}/download`, filename);
  },
  deleteSubmission(submissionId) {
    return request(`/algorithm-submissions/${submissionId}`, { method: "DELETE" });
  },
  listAdmin(query = {}) {
    return request("/admin/algorithm-submissions", { method: "GET", query });
  },
  reviewSubmission(submissionId, body) {
    return request(`/admin/algorithm-submissions/${submissionId}/review`, { method: "POST", body });
  },
};
