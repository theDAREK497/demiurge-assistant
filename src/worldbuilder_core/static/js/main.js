import {
  buildContext,
  createEntity,
  createManualProposal,
  saveMapPin,
  createRelationship,
  createRule,
  createWorld,
  exportWorld,
  importWorld,
  loadHealth,
  loadLlmConfig,
  loadWorldData,
  loadWorlds,
  openDetectiveConnectionEditor,
  openDetectiveNodeEditor,
  openMapPinEditor,
  rerenderLocalizedState,
  resetDetectiveConnectionForm,
  resetDetectiveNodeForm,
  resetEntityForm,
  resetMapPinForm,
  resetRandomTableForm,
  resetRandomTableRowForm,
  saveDetectiveConnection,
  saveDetectiveNode,
  saveRandomTable,
  saveRandomTableRow,
  saveLlmConfig,
  sendChat,
  startCreateEntity,
  startCreateEntityWithType,
  testLlmConnection,
  uploadEntityImage,
} from "./actions.js";
import { $, toast, wrap } from "./dom.js";
import { language, setLanguage, t } from "./i18n.js";
import {
  activateModuleView,
  activateTab,
  closeEntityReader,
  openSelectedEntityForEdit,
  renderChat,
  renderEntityFormMode,
  renderInviteLinks,
  renderModuleVisibility,
} from "./render.js";
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
  $("mapPinForm").addEventListener("submit", wrap(saveMapPin));
  $("randomTableForm").addEventListener("submit", wrap(saveRandomTable));
  $("randomTableRowForm").addEventListener("submit", wrap(saveRandomTableRow));
  $("detectiveNodeForm").addEventListener("submit", wrap(saveDetectiveNode));
  $("detectiveConnectionForm").addEventListener("submit", wrap(saveDetectiveConnection));
  $("chatForm").addEventListener("submit", sendChat);
  $("manualProposalForm").addEventListener("submit", wrap(createManualProposal));
  $("llmSettingsForm").addEventListener("submit", wrap(saveLlmConfig));
  $("importForm").addEventListener("submit", wrap(importWorld));
  $("cancelEntityEdit").addEventListener("click", resetEntityForm);
  $("openEntityDrawer").addEventListener("click", startCreateEntity);
  $("closeEntityDrawer").addEventListener("click", resetEntityForm);
  $("closeEntityReader").addEventListener("click", closeEntityReader);
  $("readerEditEntity").addEventListener("click", openSelectedEntityForEdit);
  $("cancelMapPinEdit").addEventListener("click", resetMapPinForm);
  $("cancelRandomTableEdit").addEventListener("click", resetRandomTableForm);
  $("cancelRandomTableRowEdit").addEventListener("click", resetRandomTableRowForm);
  $("cancelDetectiveNodeEdit").addEventListener("click", resetDetectiveNodeForm);
  $("cancelDetectiveConnectionEdit").addEventListener("click", resetDetectiveConnectionForm);
  $("openMapPinEditor").addEventListener("click", openMapPinEditor);
  $("openMapLocationCreator").addEventListener("click", () => startCreateEntityWithType("location"));
  $("openDetectiveNodeEditor").addEventListener("click", openDetectiveNodeEditor);
  $("openDetectiveConnectionEditor").addEventListener("click", openDetectiveConnectionEditor);
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
  document.querySelectorAll("[data-module-nav]").forEach((button) => {
    button.addEventListener("click", () => activateModuleView(button.dataset.moduleNav));
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
    if ($("languageSelect")?.options?.[0]) {
      $("languageSelect").options[0].textContent = "Русский";
    }
    setTheme(theme());
    bindTabs();
    bindEvents();
    bootViewerRole();
    bootModuleSettings();
    renderInviteLinks();
    $("contextPreview").textContent = t("context.empty");
    renderEntityFormMode();
    resetMapPinForm();
    resetRandomTableForm();
    resetRandomTableRowForm();
    resetDetectiveNodeForm();
    resetDetectiveConnectionForm();
    renderModuleVisibility();
    renderChat();
    await loadHealth();
    await loadLlmConfig();
    await loadWorlds();
  } catch (error) {
    toast(`${t("boot.failed")}: ${error.message}`, "error");
  }
}
