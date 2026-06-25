const fallbackTheme = "light";
const supportedThemes = new Set(["light", "dark"]);

let currentTheme = localStorage.getItem("worldbuilder.theme") || fallbackTheme;

export function theme() {
  return currentTheme;
}

export function setTheme(nextTheme) {
  currentTheme = supportedThemes.has(nextTheme) ? nextTheme : fallbackTheme;
  localStorage.setItem("worldbuilder.theme", currentTheme);
  document.documentElement.dataset.theme = currentTheme;
  const selector = document.getElementById("themeSelect");
  if (selector) {
    selector.value = currentTheme;
  }
}
