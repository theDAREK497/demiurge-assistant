import {
  buildContext,
  createEntity,
  createManualProposal,
  createRelationship,
  createRule,
  createWorld,
  exportWorld,
  importWorld,
  loadHealth,
  loadLlmConfig,
  loadWorldData,
  loadWorlds,
  rerenderLocalizedState,
  resetEntityForm,
  saveLlmConfig,
  sendChat,
  testLlmConnection,
  uploadEntityImage,
} from "./actions.js";
import { $, toast, wrap } from "./dom.js";
import { language, setLanguage, t } from "./i18n.js";
import { activateTab, renderChat, renderEntityFormMode, renderInviteLinks, renderModuleVisibility } from "./render.js";
import { defaultModuleSettings, state } from "./state.js";
import { setTheme, theme } from "./theme.js";

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tab);
    });
  });
}

function bindEvents() {
  $("worldForm").addEventListener("submit", wrap(createWorld));
  $("entityForm").addEventListener("submit", wrap(createEntity));
  $("relationshipForm").addEventListener("submit", wrap(createRelationship));
  $("ruleForm").addEventListener("submit", wrap(createRule));
  $("chatForm").addEventListener("submit", sendChat);
  $("manualProposalForm").addEventListener("submit", wrap(createManualProposal));
  $("llmSettingsForm").addEventListener("submit", wrap(saveLlmConfig));
  $("importForm").addEventListener("submit", wrap(importWorld));
  $("cancelEntityEdit").addEventListener("click", resetEntityForm);
  $("entityImageFile").addEventListener("change", wrap(uploadEntityImage));

  $("refreshWorlds").addEventListener("click", wrap(loadWorlds));
  $("refreshEntities").addEventListener("click", wrap(loadWorldData));
  $("refreshRelationships").addEventListener("click", wrap(loadWorldData));
  $("refreshRules").addEventListener("click", wrap(loadWorldData));
  $("refreshProposals").addEventListener("click", wrap(loadWorldData));
  $("refreshGraph").addEventListener("click", wrap(loadWorldData));
  $("refreshTimeline").addEventListener("click", wrap(loadWorldData));
  $("refreshContext").addEventListener("click", wrap(buildContext));
  $("refreshLlmConfig").addEventListener("click", wrap(loadLlmConfig));
  $("exportWorld").addEventListener("click", wrap(exportWorld));
  $("testLlm").addEventListener("click", wrap(testLlmConnection));

  $("entitySearch").addEventListener("search", wrap(loadWorldData));
  $("entitySearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      wrap(loadWorldData)();
    }
  });
  $("viewerRole").addEventListener("change", (event) => {
    localStorage.setItem("worldbuilder.viewerRole", event.target.value);
    wrap(loadWorldData)();
  });
  $("languageSelect").addEventListener("change", async (event) => {
    await setLanguage(event.target.value);
    rerenderLocalizedState();
  });
  $("themeSelect").addEventListener("change", (event) => {
    setTheme(event.target.value);
  });
  document.querySelectorAll("[data-module-toggle]").forEach((input) => {
    input.addEventListener("change", () => {
      state.moduleSettings[input.dataset.moduleToggle] = input.checked;
      localStorage.setItem("worldbuilder.modules", JSON.stringify(state.moduleSettings));
      renderModuleVisibility();
    });
  });
  $("clearChat").addEventListener("click", () => {
    state.chatMessages = [];
    renderChat();
  });
  document.querySelectorAll("[data-role-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setViewerRole(button.dataset.roleChoice);
      $("roleGate").classList.add("hidden");
      wrap(loadWorldData)();
    });
  });
}

function setViewerRole(role) {
  const nextRole = role === "player" ? "player" : "master";
  $("viewerRole").value = nextRole;
  localStorage.setItem("worldbuilder.viewerRole", nextRole);
}

function bootViewerRole() {
  const urlRole = new URLSearchParams(window.location.search).get("role");
  if (urlRole === "master" || urlRole === "player") {
    setViewerRole(urlRole);
    return;
  }

  const savedRole = localStorage.getItem("worldbuilder.viewerRole");
  if (savedRole === "master" || savedRole === "player") {
    $("viewerRole").value = savedRole;
    return;
  }
  $("viewerRole").value = "player";
  $("roleGate").classList.remove("hidden");
}

function bootModuleSettings() {
  try {
    const savedSettings = JSON.parse(localStorage.getItem("worldbuilder.modules") || "{}");
    state.moduleSettings = { ...defaultModuleSettings, ...savedSettings };
  } catch {
    state.moduleSettings = { ...defaultModuleSettings };
  }
}

export async function boot() {
  try {
    await setLanguage(language());
    setTheme(theme());
    bindTabs();
    bindEvents();
    bootViewerRole();
    bootModuleSettings();
    renderInviteLinks();
    $("contextPreview").textContent = t("context.empty");
    renderEntityFormMode();
    renderModuleVisibility();
    renderChat();
    await loadHealth();
    await loadLlmConfig();
    await loadWorlds();
  } catch (error) {
    toast(`${t("boot.failed")}: ${error.message}`, "error");
  }
}
