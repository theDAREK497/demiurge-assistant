const fallbackLanguage = "ru";
const supportedLanguages = new Set(["ru", "en"]);

let currentLanguage = localStorage.getItem("worldbuilder.language") || fallbackLanguage;
let dictionary = {};

export function language() {
  return currentLanguage;
}

export async function setLanguage(nextLanguage) {
  currentLanguage = supportedLanguages.has(nextLanguage) ? nextLanguage : fallbackLanguage;
  localStorage.setItem("worldbuilder.language", currentLanguage);
  document.documentElement.lang = currentLanguage;
  dictionary = await loadDictionary(currentLanguage);
  applyStaticTranslations();
  const selector = document.getElementById("languageSelect");
  if (selector) {
    selector.value = currentLanguage;
  }
}

export function t(key, params = {}) {
  const template = dictionary[key] || key;
  return Object.entries(params).reduce(
    (value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)),
    template,
  );
}

function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
}

async function loadDictionary(lang) {
  const response = await fetch(`/app/i18n/${lang}.json`);
  if (!response.ok) {
    throw new Error(`Cannot load language file: ${lang}`);
  }
  return response.json();
}
