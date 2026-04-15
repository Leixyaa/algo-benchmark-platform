const COMMUNITY_CHANGE_STORAGE_KEY = "abp_community_changed_v1";
const COMMUNITY_CHANGE_EVENT = "abp:community-changed";

function safeParse(jsonText) {
  try {
    return JSON.parse(String(jsonText || ""));
  } catch {
    return null;
  }
}

export function getCommunityChangedAt() {
  const parsed = safeParse(localStorage.getItem(COMMUNITY_CHANGE_STORAGE_KEY));
  const ts = Number(parsed?.ts || 0);
  return Number.isFinite(ts) ? ts : 0;
}

export function markCommunityChanged(source = "") {
  const payload = {
    ts: Date.now(),
    source: String(source || ""),
  };
  try {
    localStorage.setItem(COMMUNITY_CHANGE_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore
  }
  try {
    window.dispatchEvent(new CustomEvent(COMMUNITY_CHANGE_EVENT, { detail: payload }));
  } catch {
    // ignore
  }
}

export { COMMUNITY_CHANGE_EVENT, COMMUNITY_CHANGE_STORAGE_KEY };

