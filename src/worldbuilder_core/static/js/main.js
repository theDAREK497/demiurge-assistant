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
  loadWorldData,
  loadWorlds,
  rerenderLocalizedState,
  sendChat,
} from "./actions.js";
import { $, toast, wrap } from "./dom.js";
import { language, setLanguage, t } from "./i18n.js";
import { renderChat } from "./render.js";
import { state } from "./state.js";
import { setTheme, theme } from "./theme.js";

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      $(`tab-${button.dataset.tab}`).classList.add("active");
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
  $("importForm").addEventListener("submit", wrap(importWorld));

  $("refreshWorlds").addEventListener("click", wrap(loadWorlds));
  $("refreshEntities").addEventListener("click", wrap(loadWorldData));
  $("refreshRelationships").addEventListener("click", wrap(loadWorldData));
  $("refreshRules").addEventListener("click", wrap(loadWorldData));
  $("refreshProposals").addEventListener("click", wrap(loadWorldData));
  $("refreshContext").addEventListener("click", wrap(buildContext));
  $("exportWorld").addEventListener("click", wrap(exportWorld));

  $("entitySearch").addEventListener("search", wrap(loadWorldData));
  $("entitySearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      wrap(loadWorldData)();
    }
  });
  $("viewerRole").addEventListener("change", wrap(loadWorldData));
  $("languageSelect").addEventListener("change", async (event) => {
    await setLanguage(event.target.value);
    rerenderLocalizedState();
  });
  $("themeSelect").addEventListener("change", (event) => {
    setTheme(event.target.value);
  });
  $("clearChat").addEventListener("click", () => {
    state.chatMessages = [];
    renderChat();
  });
}

export async function boot() {
  try {
    await setLanguage(language());
    setTheme(theme());
    bindTabs();
    bindEvents();
    $("contextPreview").textContent = t("context.empty");
    renderChat();
    await loadHealth();
    await loadWorlds();
  } catch (error) {
    toast(`${t("boot.failed")}: ${error.message}`, "error");
  }
}
