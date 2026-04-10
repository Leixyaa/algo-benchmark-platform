import { request } from "./http";
import { downloadBinaryFile } from "./download";

export const algorithmSubmissionsApi = {
  listMine() {
    return request("/algorithm-submissions", { method: "GET" });
  },
  createSubmission(body) {
    return request("/algorithm-submissions", { method: "POST", body });
  },
  publishToCommunity(submissionId, body = {}) {
    return request(`/algorithm-submissions/${submissionId}/publish-community`, { method: "POST", body });
  },
  downloadArchive(submissionId, filename = "algorithm_package.zip") {
    return downloadBinaryFile(`/algorithm-submissions/${submissionId}/download`, filename);
  },
  listAdmin(query = {}) {
    return request("/admin/algorithm-submissions", { method: "GET", query });
  },
  reviewSubmission(submissionId, body) {
    return request(`/admin/algorithm-submissions/${submissionId}/review`, { method: "POST", body });
  },
};
