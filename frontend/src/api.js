const apiBase = "/api";
const masterTokenStorageKey = "worldbuilder.masterToken";

captureMasterTokenFromFragment();

export async function api(path, options = {}) {
  const { headers: optionHeaders = {}, ...fetchOptions } = options;
  const token = masterAccessToken();
  const response = await fetch(`${apiBase}${path}`, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Worldbuilder-Master-Token": token } : {}),
      ...optionHeaders,
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

function masterAccessToken() {
  try {
    return sessionStorage.getItem(masterTokenStorageKey) || "";
  } catch {
    return "";
  }
}

function captureMasterTokenFromFragment() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const token = params.get("master_token");
  if (!token) return;
  try {
    sessionStorage.setItem(masterTokenStorageKey, token);
  } catch {
    return;
  }
  params.delete("master_token");
  const nextHash = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}${nextHash ? `#${nextHash}` : ""}`);
}
