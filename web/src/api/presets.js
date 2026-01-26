import { request } from "./http";

export const presetsApi = {
  async listPresets({ limit = 200 } = {}) {
    return request("/presets", { method: "GET", query: { limit } });
  },
  async getPreset(presetId) {
    return request(`/presets/${presetId}`, { method: "GET" });
  },
  async createPreset(payload) {
    return request("/presets", { method: "POST", body: payload });
  },
  async patchPreset(presetId, patch) {
    return request(`/presets/${presetId}`, { method: "PATCH", body: patch });
  },
  async deletePreset(presetId) {
    return request(`/presets/${presetId}`, { method: "DELETE" });
  },
};

