const apiBase = "/api";
const masterTokenStorageKey = "worldbuilder.masterToken";

captureMasterTokenFromFragment();

export function masterAccessToken() {
  try {
    return sessionStorage.getItem(masterTokenStorageKey) || "";
  } catch {
    return "";
  }
}

export function setMasterAccessToken(value) {
  const token = String(value || "").trim();
  try {
    if (token) {
      sessionStorage.setItem(masterTokenStorageKey, token);
    } else {
      sessionStorage.removeItem(masterTokenStorageKey);
    }
  } catch {
    // The local browser session can still use trusted loopback access.
  }
}

export async function api(path, options = {}) {
  const token = masterAccessToken();
  const { headers: optionHeaders = {}, ...fetchOptions } = options;
  const response = await fetch(`${apiBase}${path}`, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Worldbuilder-Master-Token": token } : {}),
      ...optionHeaders,
    },
  });

  if (!response.ok) {
    throw new Error(await responseError(response));
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export async function apiRaw(path, options = {}) {
  const token = masterAccessToken();
  const { headers: optionHeaders = {}, ...fetchOptions } = options;
  const response = await fetch(`${apiBase}${path}`, {
    ...fetchOptions,
    headers: {
      ...(token ? { "X-Worldbuilder-Master-Token": token } : {}),
      ...optionHeaders,
    },
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  return response.status === 204 ? null : response.json();
}

async function responseError(response) {
  const fallback = `${response.status} ${response.statusText}`;
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    return text || fallback;
  }
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => {
      const field = (item.loc || []).filter((part) => part !== "body").join(".");
      return `${field ? `${field}: ` : ""}${item.msg || fallback}`;
    }).join("; ") || fallback;
  }
  return typeof payload?.detail === "string" ? payload.detail : fallback;
}

function captureMasterTokenFromFragment() {
  const rawHash = window.location.hash.replace(/^#/, "");
  if (!rawHash) return;
  const params = new URLSearchParams(rawHash);
  const token = params.get("master_token");
  if (!token) return;
  setMasterAccessToken(token);
  params.delete("master_token");
  const nextHash = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}${nextHash ? `#${nextHash}` : ""}`);
}
