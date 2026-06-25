export const $ = (id) => document.getElementById(id);

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  $("toastRoot").appendChild(node);
  window.setTimeout(() => node.remove(), 4200);
}

export function wrap(fn) {
  return async (event) => {
    try {
      await fn(event);
    } catch (error) {
      toast(error.message || "Unexpected error", "error");
    }
  };
}
