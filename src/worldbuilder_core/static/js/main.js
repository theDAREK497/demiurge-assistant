import {
  buildContext,
  branchChatThread,
  createEntity,
  createManualProposal,
  saveMapPin,
  createRelationship,
  createRule,
  createWorld,
  deleteDetectiveBoard,
  deleteEntity,
  deleteDetectiveNode,
  deleteMapPin,
  exportWorld,
  generateDetectiveBoard,
  importWorld,
  insertChatTemplate,
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
  resetRelationshipForm,
  resetRandomTableForm,
  resetRandomTableRowForm,
  saveDetectiveConnection,
  saveDetectiveNode,
  saveRandomTable,
  saveRandomTableRow,
  saveLlmConfig,
  sendChat,
  startNewChatThread,
  startCreateEntity,
  startCreateEntityWithType,
  testLlmConnection,
  uploadEntityImage,
} from "./actions.js?v=20260715.1";
import { masterAccessToken, setMasterAccessToken } from "./api.js?v=20260715.1";
import { $, toast, wrap } from "./dom.js?v=20260715.1";
import { language, setLanguage, t } from "./i18n.js?v=20260715.1";
import {
  activateModuleView,
  activateTab,
  arrangeGraph,
  closeEntityReader,
  openSelectedEntityForEdit,
  renderChat,
  renderChatTemplates,
  renderChatThreads,
  renderEntities,
  renderEntityFormMode,
  renderInviteLinks,
  renderModuleVisibility,
} from "./render.js?v=20260715.1";
import { defaultModuleSettings, state } from "./state.js?v=20260715.1";
import { setTheme, theme } from "./theme.js?v=20260715.1";

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tab);
    });
  });
}

function bindEvents() {
  window.addEventListener("unhandledrejection", (event) => {
    event.preventDefault();
    toast(event.reason?.message || t("common.unexpectedError"), "error");
  });
  document.addEventListener(
    "error",
    (event) => {
      if (event.target instanceof HTMLImageElement) {
        event.target.hidden = true;
      }
    },
    true,
  );
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
  $("cancelRelationshipEdit").addEventListener("click", resetRelationshipForm);
  $("openEntityDrawer").addEventListener("click", startCreateEntity);
  $("closeEntityDrawer").addEventListener("click", resetEntityForm);
  $("closeEntityReader").addEventListener("click", closeEntityReader);
  $("readerEditEntity").addEventListener("click", openSelectedEntityForEdit);
  $("readerDeleteEntity").addEventListener("click", () => {
    if (state.selectedReaderType === "detectiveNode" && state.selectedReaderSourceId) {
      deleteDetectiveNode(state.selectedReaderSourceId);
      return;
    }
    if (!state.selectedEntityId) return;
    deleteEntity(state.selectedEntityId);
  });
  $("cancelMapPinEdit").addEventListener("click", resetMapPinForm);
  $("deleteMapPinBtn").addEventListener("click", () => {
    if (state.editingMapPinId) {
      deleteMapPin(state.editingMapPinId);
    }
  });
  $("cancelRandomTableEdit").addEventListener("click", resetRandomTableForm);
  $("cancelRandomTableRowEdit").addEventListener("click", resetRandomTableRowForm);
  $("cancelDetectiveNodeEdit").addEventListener("click", resetDetectiveNodeForm);
  $("cancelDetectiveConnectionEdit").addEventListener("click", resetDetectiveConnectionForm);
  $("openMapPinEditor").addEventListener("click", openMapPinEditor);
  $("openMapLocationCreator").addEventListener("click", () => startCreateEntityWithType("location"));
  $("addTimelineEventBtn").addEventListener("click", () => startCreateEntityWithType("event"));
  $("addJournalEntryBtn").addEventListener("click", () => startCreateEntityWithType("event"));
  $("addQuestBtn").addEventListener("click", () => startCreateEntityWithType("event", ["quest"]));
  $("openDetectiveNodeEditor").addEventListener("click", openDetectiveNodeEditor);
  $("openDetectiveConnectionEditor").addEventListener("click", openDetectiveConnectionEditor);
  $("generateDetectiveBoard").addEventListener("click", wrap(generateDetectiveBoard));
  $("deleteDetectiveBoard").addEventListener("click", wrap(deleteDetectiveBoard));
  $("entityImageFile").addEventListener("change", wrap(uploadEntityImage));

  // Responsive mobile sidebar listeners
  const toggleBtn = $("toggleSidebarMobile");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      document.querySelector(".shell")?.classList.toggle("sidebar-open");
    });
  }

  let backdrop = document.querySelector(".sidebar-backdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "sidebar-backdrop";
    document.querySelector(".shell")?.appendChild(backdrop);
  }
  backdrop.addEventListener("click", () => {
    document.querySelector(".shell")?.classList.remove("sidebar-open");
  });

  $("refreshWorlds").addEventListener("click", wrap(loadWorlds));
  $("refreshEntities").addEventListener("click", wrap(loadWorldData));
  $("refreshRelationships").addEventListener("click", wrap(loadWorldData));
  $("refreshRules").addEventListener("click", wrap(loadWorldData));
  $("refreshProposals").addEventListener("click", wrap(loadWorldData));
  $("refreshGraph").addEventListener("click", wrap(loadWorldData));
  $("arrangeGraph").addEventListener("click", arrangeGraph);
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
    setViewerRole(event.target.value);
    wrap(loadWorldData)();
  });
  $("switchRole").addEventListener("click", () => {
    $("roleGate").classList.remove("hidden");
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
  $("newChatThread").addEventListener("click", startNewChatThread);
  $("branchChatThread").addEventListener("click", branchChatThread);
  document.querySelectorAll("[data-chat-template]").forEach((button) => {
    button.addEventListener("click", () => insertChatTemplate(button.dataset.chatTemplate));
  });
  document.querySelectorAll("[data-role-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.roleChoice === "master") {
        setMasterAccessToken($("masterAccessToken").value);
      }
      setViewerRole(button.dataset.roleChoice);
      $("roleGate").classList.add("hidden");
      wrap(loadWorldData)();
    });
  });

  // Bind category filter buttons
  document.querySelectorAll(".category-filter").forEach((button) => {
    button.addEventListener("click", () => {
      state.entityTypeFilter = button.dataset.filter;
      renderEntities();
    });
  });
}

function setViewerRole(role) {
  const nextRole = role === "player" ? "player" : "master";
  $("viewerRole").value = nextRole;
  localStorage.setItem("worldbuilder.viewerRole", nextRole);
  const url = new URL(window.location.href);
  url.searchParams.set("role", nextRole);
  window.history.replaceState({}, "", url);
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
    initMarkdownToolbar();
    bootViewerRole();
    $("masterAccessToken").value = masterAccessToken();
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
    renderChatTemplates();
    renderChatThreads();
    renderChat();
    await loadHealth();
    if ($("viewerRole").value === "master") {
      await loadLlmConfig();
    }
    await loadWorlds();
  } catch (error) {
    toast(`${t("boot.failed")}: ${error.message}`, "error");
  }
}

function initMarkdownToolbar() {
  document.querySelectorAll(".md-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const textarea = $("entityDescription");
      if (!textarea) return;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = textarea.value;
      const prefix = btn.dataset.mdPrefix || "";
      const suffix = btn.dataset.mdSuffix || "";
      const selectedText = text.substring(start, end);
      const replacement = prefix + selectedText + suffix;
      textarea.value = text.substring(0, start) + replacement + text.substring(end);
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length);
    });
  });
}
