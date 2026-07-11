import { $, escapeHtml } from "./dom.js";
import { selectedWorld, state } from "./state.js";
import { language, t } from "./i18n.js";
import {
  applyProposal,
  applySelectedProposal,
  cancelChatMessageEdit,
  cancelChatThreadRename,
  changeChatThread,
  deleteChatMessage,
  deleteChatThread,
  deleteDetectiveConnection,
  deleteDetectiveNode,
  deleteEntity,
  deleteMapPin,
  deleteRandomTable,
  deleteRandomTableRow,
  deleteRelationship,
  deleteRule,
  deleteProposal,
  deleteWorld,
  editChatMessage,
  editDetectiveConnection,
  editDetectiveNode,
  editEntity,
  editRelationship,
  editMapPin,
  editRandomTable,
  editRandomTableRow,
  openMapPinEditor,
  persistDetectiveNodePosition,
  rejectProposal,
  renameChatThread,
  loadWorldData,
  rollRandomTable,
  saveChatMessageEdit,
  saveChatThreadRename,
  saveAssistantMessageToWiki,
  setDetectiveNodeDraft,
  setMapPinDraft,
  startCreateEntityWithType,
} from "./actions.js";

export function activateTab(tabName) {
  const requestedTab = document.querySelector(`.tab[data-tab="${tabName}"]:not(.hidden)`);
  const fallbackTab = document.querySelector(".tab:not(.hidden)");
  const tab = requestedTab || fallbackTab;
  if (!tab) return;

  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
  tab.classList.add("active");
  $(`tab-${tab.dataset.tab}`)?.classList.add("active");
}

export function activateModuleView(moduleName) {
  const button = document.querySelector(`[data-module-nav="${moduleName}"]:not(.hidden)`);
  if (!button) return;
  state.activeModuleView = moduleName;
  renderModuleVisibility();
}

export function currentRole() {
  return $("viewerRole").value;
}

function isMasterMode() {
  return currentRole() === "master";
}

export function renderAllWorldData() {
  const role = currentRole();
  document.body.classList.toggle("role-master", role === "master");
  document.body.classList.toggle("role-player", role === "player");
  const badge = $("roleIndicatorBadge");
  if (badge) {
    badge.textContent = role === "master" ? t("role.master") : t("role.player");
    badge.className = `role-indicator-badge ${role}`;
  }

  renderEntities();
  renderRelationshipOptions();
  renderRelationshipFormMode();
  renderMapPinOptions();
  renderRandomTableOptions();
  renderDetectiveOptions();
  renderRelationships();
  renderRules();
  renderProposals();
  renderGraph();
  renderTimeline();
  renderModules();
  renderModuleVisibility();
  renderRoleVisibility();
  renderChatThreads();
  renderChatTemplates();
  renderChat();
  renderEntityReader();
}

function renderRoleVisibility() {
  const master = isMasterMode();
  document.querySelectorAll("[data-master-only]").forEach((element) => {
    element.classList.toggle("hidden", !master);
  });

  if (!master) {
    closeEntityDrawer();
  }

  const activeTab = document.querySelector(".tab.active");
  if (activeTab?.dataset.masterOnly === "true" && !master) {
    activateTab("wiki");
  }
}

export function renderModuleVisibility() {
  const settings = state.moduleSettings;
  const modulePanelVisible = ["journal", "quests", "maps", "randomTables", "detectiveBoard"].some(
    (key) => settings[key] !== false,
  );

  document.querySelectorAll("[data-module-toggle]").forEach((input) => {
    input.checked = settings[input.dataset.moduleToggle] !== false;
  });

  document.querySelectorAll("[data-module-tab]").forEach((button) => {
    const tabName = button.dataset.moduleTab;
    const visible = tabName === "modules" ? modulePanelVisible : settings[tabName] !== false;
    button.classList.toggle("hidden", !visible);
    $(`tab-${tabName}`)?.classList.toggle("hidden", !visible);
  });

  document.querySelectorAll("[data-module-panel]").forEach((panel) => {
    const moduleName = panel.dataset.modulePanel;
    panel.classList.toggle("hidden", settings[moduleName] === false || moduleName !== state.activeModuleView);
  });

  document.querySelectorAll("[data-module-nav]").forEach((button) => {
    const moduleName = button.dataset.moduleNav;
    const isVisible = settings[moduleName] !== false;
    button.classList.toggle("hidden", !isVisible);
    button.classList.toggle("active", moduleName === state.activeModuleView);
  });

  const activeModuleAvailable = settings[state.activeModuleView] !== false;
  if (!activeModuleAvailable) {
    const firstVisibleModule = ["journal", "quests", "maps", "randomTables", "detectiveBoard"].find(
      (moduleName) => settings[moduleName] !== false,
    );
    if (firstVisibleModule) {
      state.activeModuleView = firstVisibleModule;
      renderModuleVisibility();
    }
  }

  const activeTab = document.querySelector(".tab.active");
  if (activeTab?.classList.contains("hidden")) {
    activateTab("wiki");
  }
  renderChatTemplates();
}

export function renderInviteLinks() {
  const playerInput = $("playerInviteUrl");
  const masterInput = $("masterInviteUrl");
  if (!playerInput || !masterInput) return;
  const baseUrl = `${window.location.origin}/app/`;
  playerInput.value = `${baseUrl}?role=player`;
  masterInput.value = `${baseUrl}?role=master`;
}

export function renderEntityFormMode() {
  $("entitySubmit").textContent = state.editingEntityId ? t("entity.save") : t("entity.add");
  $("cancelEntityEdit").classList.toggle("hidden", !state.editingEntityId);
  $("entityFormTitle").textContent = state.editingEntityId ? t("entity.editTitle") : t("entity.createTitle");
}

export function renderMapPinFormMode() {
  $("mapPinSubmit").textContent = state.editingMapPinId ? t("map.pinSave") : t("map.pinAdd");
  $("cancelMapPinEdit").classList.toggle("hidden", !state.editingMapPinId);
  const deleteBtn = $("deleteMapPinBtn");
  if (deleteBtn) {
    deleteBtn.classList.toggle("hidden", !state.editingMapPinId);
  }
}

export function renderRelationshipFormMode() {
  const editing = Boolean(state.editingRelationshipId);
  $("relationshipFormTitle").textContent = t(editing ? "relationship.editTitle" : "relationship.createTitle");
  $("relationshipSubmit").textContent = t(editing ? "relationship.save" : "relationship.add");
  $("cancelRelationshipEdit").classList.toggle("hidden", !editing);
}

export function renderRandomTableFormMode() {
  $("randomTableSubmit").textContent = state.editingRandomTableId ? t("randomTable.save") : t("randomTable.add");
  $("cancelRandomTableEdit").classList.toggle("hidden", !state.editingRandomTableId);
}

export function renderRandomTableRowFormMode() {
  $("randomTableRowSubmit").textContent = state.editingRandomTableRowId ? t("randomTable.rowSave") : t("randomTable.rowAdd");
  $("cancelRandomTableRowEdit").classList.toggle("hidden", !state.editingRandomTableRowId);
}

export function renderDetectiveNodeFormMode() {
  $("detectiveNodeSubmit").textContent = state.editingDetectiveNodeId ? t("detective.nodeSave") : t("detective.nodeAdd");
  $("cancelDetectiveNodeEdit").classList.toggle("hidden", !state.editingDetectiveNodeId);
}

export function renderDetectiveConnectionFormMode() {
  $("detectiveConnectionSubmit").textContent = state.editingDetectiveConnectionId
    ? t("detective.connectionSave")
    : t("detective.connectionAdd");
  $("cancelDetectiveConnectionEdit").classList.toggle("hidden", !state.editingDetectiveConnectionId);
}

export function openEntityDrawer() {
  $("entityDrawerBackdrop").classList.remove("hidden");
}

export function closeEntityDrawer() {
  $("entityDrawerBackdrop").classList.add("hidden");
}

export function renderLlmConfig() {
  const config = state.llmConfig;
  if (!config) {
    $("llmConfigStatus").textContent = t("llm.statusUnknown");
    return;
  }

  $("llmBaseUrl").value = config.base_url || "";
  $("llmDefaultModel").value = config.default_model || "";
  $("llmChatModel").value = config.chat_model || "";
  $("llmExtractorModel").value = config.extractor_model || "";
  $("llmSummarizerModel").value = config.summarizer_model || "";
  $("llmCriticModel").value = config.critic_model || "";
  $("llmTimeout").value = config.timeout_seconds;
  $("llmMaxExtract").value = config.max_entities_per_extract;
  $("llmApiKey").value = "";
  $("llmClearApiKey").checked = false;

  const source = config.persisted ? t("llm.statusSaved") : t("llm.statusEnv");
  const keyState = config.has_api_key ? t("llm.apiKeySaved") : t("llm.apiKeyEmpty");
  $("llmConfigStatus").textContent = `${source} - ${keyState}`;
}

export function renderWorlds() {
  const list = $("worldList");
  if (!state.worlds.length) {
    list.className = "list empty";
    list.textContent = t("world.empty");
    return;
  }

  list.className = "list";
  const master = isMasterMode();
  list.innerHTML = state.worlds
    .map(
      (world) => `
        <div class="world-list-item ${world.id === state.selectedWorldId ? "active" : ""}">
          <button class="item" data-world-id="${world.id}" type="button">
            <div class="item-top"><span class="item-title">${escapeHtml(world.name)}</span></div>
            <div class="item-meta">${escapeHtml(world.description || t("common.noDescription"))}</div>
          </button>
          ${master ? `<button class="ghost danger icon-button" data-delete-world="${world.id}" type="button" title="${escapeHtml(t("world.delete"))}" aria-label="${escapeHtml(t("world.delete"))}">&times;</button>` : ""}
        </div>
      `,
    )
    .join("");

  list.querySelectorAll("[data-world-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedWorldId = button.dataset.worldId;
      state.chatMessages = [];
      document.querySelector(".shell")?.classList.remove("sidebar-open");
      renderWorlds();
      renderSelectedWorld();
      renderChat();
      await loadWorldData();
    });
  });
  list.querySelectorAll("[data-delete-world]").forEach((button) => {
    button.addEventListener("click", () => deleteWorld(button.dataset.deleteWorld));
  });
}

export function renderSelectedWorld() {
  const world = selectedWorld();
  $("selectedWorldName").textContent = world?.name || t("common.none");
  $("selectedWorldDescription").textContent = world?.description || t("world.selectPrompt");
}

export function renderEntities() {
  const list = $("entityList");
  const master = isMasterMode();
  if (!state.selectedWorldId) {
    list.className = "grid-list empty";
    list.textContent = t("entity.selectWorld");
    return;
  }

  // Update active state for filter buttons
  document.querySelectorAll(".category-filter").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === (state.entityTypeFilter || "all"));
  });

  let filteredEntities = state.entities;
  if (state.entityTypeFilter && state.entityTypeFilter !== "all") {
    filteredEntities = state.entities.filter((entity) => entity.type === state.entityTypeFilter);
  }

  if (!filteredEntities.length) {
    list.className = "grid-list empty";
    list.textContent = t("entity.empty");
    return;
  }

  list.className = "grid-list";
  list.innerHTML = filteredEntities
    .map(
      (entity) => `
        <article class="item entity-card encyclopedia-card" data-open-entity="${entity.id}" role="button" tabindex="0">
          ${entity.attributes?.image_url ? `<img class="entity-image" src="${escapeHtml(entity.attributes.image_url)}" alt="" loading="lazy" onerror="this.hidden=true" />` : ""}
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(entity.name)}</div>
              <div class="item-meta">${escapeHtml(t(`entityType.${entity.type}`))} - ${escapeHtml(entity.status)} - ${entity.is_secret ? t("common.secretValue") : t("common.public")}</div>
            </div>
            <span class="badge">${escapeHtml(entity.id.slice(0, 8))}</span>
          </div>
          <div class="item-body">${renderMarkdown(entity.summary || entity.description || t("common.noSummary"))}</div>
          ${entity.attributes?.timeline_date ? `<div class="item-meta">${t("entity.timelineDate")}: ${escapeHtml(entity.attributes.timeline_date)}</div>` : ""}
          ${entity.tags?.length ? `<div class="item-meta">${entity.tags.map(escapeHtml).join(", ")}</div>` : ""}
          <div class="item-actions">
            <button class="ghost" data-open-entity-button="${entity.id}" type="button">${t("entity.open")}</button>
            ${
              master
                ? `<button class="ghost" data-edit-entity="${entity.id}" type="button">${t("entity.edit")}</button>
                   <button class="ghost danger" data-delete-entity="${entity.id}" type="button">${t("randomTable.delete")}</button>`
                : ""
            }
          </div>
        </article>
      `,
    )
    .join("");

  list.querySelectorAll("[data-open-entity]").forEach((card) => {
    card.addEventListener("click", () => openEntityReader(card.dataset.openEntity));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openEntityReader(card.dataset.openEntity);
      }
    });
  });
  list.querySelectorAll("[data-open-entity-button]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openEntityReader(button.dataset.openEntityButton);
    });
  });
  list.querySelectorAll("[data-edit-entity]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      editEntity(button.dataset.editEntity);
    });
  });
  list.querySelectorAll("[data-delete-entity]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteEntity(button.dataset.deleteEntity);
    });
  });
}

export function openEntityReader(entityId) {
  openReader("entity", entityId, entityId);
}

export function closeEntityReader() {
  state.selectedEntityId = null;
  state.selectedReaderType = null;
  state.selectedReaderSourceId = null;
  $("entityReader").classList.add("hidden");
}

export function openSelectedEntityForEdit() {
  if (state.selectedReaderType === "detectiveNode" && state.selectedReaderSourceId) {
    editDetectiveNode(state.selectedReaderSourceId);
    return;
  }
  if (!state.selectedEntityId) return;
  editEntity(state.selectedEntityId);
}

function renderEntityReader() {
  const readerType = state.selectedReaderType || "entity";
  const editButton = $("readerEditEntity");

  if (readerType === "detectiveNode") {
    if (editButton) {
      editButton.textContent = t("entity.edit");
    }
    renderDetectiveNodeReader();
    return;
  }

  const entity = state.entities.find((item) => item.id === state.selectedEntityId);
  if (!entity) {
    $("entityReaderContent").innerHTML = "";
    $("entityReader").classList.add("hidden");
    return;
  }

  if (editButton) {
    editButton.textContent = t("entity.edit");
  }

  const extraSections = [];
  if (readerType === "map") {
    extraSections.push(renderMapReaderPinsSection(entity.id));
  }

  $("entityReaderContent").innerHTML = renderEntityReaderLayout(entity, {
    extraSections,
  });
  bindEntityReaderActions();
}

function openReader(type, sourceId, entityId = null) {
  state.selectedReaderType = type;
  state.selectedReaderSourceId = sourceId;
  state.selectedEntityId = entityId;
  renderEntityReader();
  $("entityReader").classList.remove("hidden");
}

function openMapReader(entityId) {
  openReader("map", entityId, entityId);
}

function openDetectiveNodeReader(nodeId) {
  const node = state.detectiveNodes.find((item) => item.id === nodeId);
  openReader("detectiveNode", nodeId, node?.entity_id || null);
}

function renderReaderHeader({ title, eyebrow, summary, badge, imageHtml }) {
  return `
    <header class="reader-hero">
      <div class="reader-hero-media">${imageHtml}</div>
      <div class="reader-hero-copy">
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h2>${escapeHtml(title)}</h2>
        ${summary ? `<p class="reader-summary">${escapeHtml(summary)}</p>` : ""}
        <span class="badge">${escapeHtml(badge)}</span>
      </div>
    </header>
  `;
}

export function renderMarkdown(text) {
  if (!text) return "";
  const lines = escapeHtml(text).replace(/\r\n/g, "\n").split("\n");
  const output = [];
  let listType = null;
  let inCode = false;
  let codeLines = [];

  const closeList = () => {
    if (listType) {
      output.push(`</${listType}>`);
      listType = null;
    }
  };

  const openList = (nextListType) => {
    if (listType === nextListType) return;
    closeList();
    output.push(`<${nextListType}>`);
    listType = nextListType;
  };

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    if (line.trim().startsWith("```")) {
      if (inCode) {
        output.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    const tableHeader = parseMarkdownTableRow(line);
    const tableSeparator = parseMarkdownTableSeparator(lines[lineIndex + 1]);
    if (tableHeader && tableSeparator && tableHeader.length === tableSeparator.length) {
      closeList();
      const rows = [];
      lineIndex += 2;
      while (lineIndex < lines.length) {
        const row = parseMarkdownTableRow(lines[lineIndex]);
        if (!row) break;
        rows.push(row);
        lineIndex += 1;
      }
      lineIndex -= 1;
      output.push(renderMarkdownTable(tableHeader, tableSeparator, rows));
      continue;
    }

    const heading = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      closeList();
      const level = heading[1].length;
      output.push(`<h${level}>${renderInlineMarkdown(heading[2].trim())}</h${level}>`);
      continue;
    }

    if (/^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line)) {
      closeList();
      output.push("<hr>");
      continue;
    }

    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      openList("ul");
      output.push(`<li>${renderInlineMarkdown(bullet[1].trim())}</li>`);
      continue;
    }

    const ordered = /^\s*\d+\.\s+(.+)$/.exec(line);
    if (ordered) {
      openList("ol");
      output.push(`<li>${renderInlineMarkdown(ordered[1].trim())}</li>`);
      continue;
    }

    const quote = /^\s*>\s?(.*)$/.exec(line);
    if (quote) {
      closeList();
      output.push(`<blockquote>${renderInlineMarkdown(quote[1].trim())}</blockquote>`);
      continue;
    }

    closeList();
    if (line.trim()) {
      output.push(`<p>${renderInlineMarkdown(line.trim())}</p>`);
    }
  }

  closeList();
  if (inCode) {
    output.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
  }
  return `<div class="md-content">${output.join("")}</div>`;
}

function parseMarkdownTableRow(line) {
  if (!line || !line.includes("|")) return null;
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells = trimmed.split("|").map((cell) => cell.trim());
  return cells.length > 1 ? cells : null;
}

function parseMarkdownTableSeparator(line) {
  const cells = parseMarkdownTableRow(line);
  if (!cells || !cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")))) return null;
  return cells.map((cell) => {
    const normalized = cell.replace(/\s+/g, "");
    if (normalized.startsWith(":") && normalized.endsWith(":")) return "center";
    if (normalized.endsWith(":")) return "right";
    return "left";
  });
}

function renderMarkdownTable(headers, alignments, rows) {
  const renderCells = (cells, tag) => headers
    .map((_, index) => `<${tag} class="md-align-${alignments[index]}">${renderInlineMarkdown(cells[index] || "")}</${tag}>`)
    .join("");
  return `
    <div class="md-table-wrap">
      <table>
        <thead><tr>${renderCells(headers, "th")}</tr></thead>
        <tbody>${rows.map((row) => `<tr>${renderCells(row, "td")}</tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function renderInlineMarkdown(value) {
  const codeSegments = [];
  const withCodeTokens = value.replace(/`([^`]+)`/g, (_, code) => {
    const token = `%%CODETOKEN${codeSegments.length}%%`;
    codeSegments.push(code);
    return token;
  });
  const rendered = withCodeTokens
    .replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>")
    .replace(/___([^_]+)___/g, "<strong><em>$1</em></strong>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/_([^_]+)_/g, "<em>$1</em>")
    .replace(/~~([^~]+)~~/g, "<del>$1</del>");
  return codeSegments.reduce(
    (result, code, index) => result.replace(`%%CODETOKEN${index}%%`, `<code>${code}</code>`),
    rendered,
  );
}

function renderEntityReaderLayout(entity, { extraSections = [] } = {}) {
  const related = state.relationships.filter(
    (relationship) => relationship.source_entity_id === entity.id || relationship.target_entity_id === entity.id,
  );
  const imageHtml = entity.attributes?.image_url
    ? `<img class="reader-image" src="${escapeHtml(entity.attributes.image_url)}" alt="" onerror="this.hidden=true" />`
    : `<div class="reader-image placeholder">${escapeHtml(t(`entityType.${entity.type}`))}</div>`;

  // Breadcrumbs
  const breadcrumbsHtml = `
    <nav class="reader-breadcrumbs" aria-label="Breadcrumb">
      <span class="breadcrumb-item clickable" data-breadcrumb-action="back-to-wiki">${escapeHtml(t("tabs.wiki"))}</span>
      <span class="breadcrumb-separator">/</span>
      <span class="breadcrumb-item clickable" data-breadcrumb-action="filter-type" data-filter-type="${entity.type}">${escapeHtml(t(`entityType.${entity.type}`))}</span>
      <span class="breadcrumb-separator">/</span>
      <span class="breadcrumb-item active">${escapeHtml(entity.name)}</span>
    </nav>
  `;

  // Table of Contents (TOC)
  const hasSummary = !!entity.summary;
  const hasDesc = !!(entity.description && entity.description !== entity.summary);
  const hasRelationships = related.length > 0;
  const hasExtra = extraSections.length > 0;

  let tocHtml = `
    <nav class="reader-toc">
      <div class="toc-title">${escapeHtml(t("entity.tocTitle") || "Содержание")}</div>
      <ul class="toc-list">
        <li class="toc-item"><a href="#sec-overview" class="toc-link active">${escapeHtml(t("entity.tocOverview") || "Обзор")}</a></li>
  `;
  if (hasDesc) {
    tocHtml += `
        <li class="toc-item"><a href="#sec-details" class="toc-link">${escapeHtml(t("entity.tocDetails") || "Описание")}</a></li>
    `;
  }
  if (hasRelationships) {
    tocHtml += `
        <li class="toc-item"><a href="#sec-relations" class="toc-link">${escapeHtml(t("entity.tocRelations") || "Связи")}</a></li>
    `;
  }
  if (hasExtra) {
    tocHtml += `
        <li class="toc-item"><a href="#sec-extra" class="toc-link">${escapeHtml(t("entity.tocExtra") || "Объекты")}</a></li>
    `;
  }
  tocHtml += `
      </ul>
    </nav>
  `;

  return `
    ${breadcrumbsHtml}
    ${renderReaderHeader({
      title: entity.name,
      eyebrow: t(`entityType.${entity.type}`),
      summary: entity.summary,
      badge: entity.is_secret ? t("common.secretValue") : t("common.public"),
      imageHtml,
    })}
    <div class="reader-reading-layout">
      <!-- Left Column: Table of Contents -->
      <aside class="reader-toc-column">
        ${tocHtml}
      </aside>

      <!-- Unified Article Column: TOC items act as Tabs -->
      <article class="reader-article">
        <section id="sec-overview" class="reader-section-block">
          <div class="reader-body">${renderMarkdown(entity.summary || entity.description || t("common.noSummary"))}</div>
        </section>

        ${hasDesc ? `
          <section id="sec-details" class="reader-section-block">
            <h3 class="section-title">${escapeHtml(t("entity.description") || "Описание")}</h3>
            <div class="reader-body">${renderMarkdown(entity.description)}</div>
          </section>
        ` : ""}

        ${hasExtra ? `
          <section id="sec-extra" class="reader-section-block">
            ${extraSections.join("")}
          </section>
        ` : ""}

        <section id="sec-relations" class="reader-section-block reader-section">
          <h3 class="section-title">${escapeHtml(t("relationship.listTitle"))}</h3>
          ${related.length ? renderReaderRelationshipCards(entity.id, related) : `<p class="muted">${escapeHtml(t("relationship.empty"))}</p>`}
        </section>

        ${
          entity.tags?.length
            ? `<div class="reader-tags" style="margin-top: 16px;">${entity.tags.map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}</div>`
            : ""
        }
        ${
          entity.attributes?.timeline_date
            ? `<div class="item-meta reader-timeline-date-meta">${escapeHtml(t("entity.timelineDate"))}: ${escapeHtml(entity.attributes.timeline_date)}</div>`
            : ""
        }
      </article>
    </div>
  `;
}

function renderReaderRelationshipCards(entityId, relationships) {
  return `
    <div class="reader-card-list">
      ${relationships
        .map((relationship) => {
          const otherEntityId =
            relationship.source_entity_id === entityId ? relationship.target_entity_id : relationship.source_entity_id;
          return `
            <article class="reader-subcard">
              <div class="reader-card-head">
                <strong>${escapeHtml(entityName(otherEntityId))}</strong>
                <span class="badge">${escapeHtml(relationshipDisplayLabel(relationship))}</span>
              </div>
              <div class="reader-inline-actions">
                <span class="item-meta">${escapeHtml(entityName(relationship.source_entity_id))} -> ${escapeHtml(entityName(relationship.target_entity_id))}</span>
                <button class="ghost" data-reader-open-entity="${otherEntityId}" type="button">${escapeHtml(t("entity.open"))}</button>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderMapReaderPinsSection(entityId) {
  const pins = state.mapPins.filter((pin) => pin.map_entity_id === entityId);
  return `
    <section class="reader-section">
      <h3>${escapeHtml(t("map.pins"))}</h3>
      ${
        pins.length
          ? `<div class="reader-card-list">
              ${pins
                .map(
                  (pin) => `
                    <article class="reader-subcard">
                      <div class="reader-card-head">
                        <strong>${escapeHtml(pin.title)}</strong>
                        <span class="badge">${pin.is_secret ? escapeHtml(t("common.secretValue")) : escapeHtml(t("common.public"))}</span>
                      </div>
                      ${pin.note ? `<div class="reader-card-body">${renderMarkdown(pin.note)}</div>` : ""}
                      ${
                        pin.linked_entity_id
                          ? `<div class="reader-inline-actions">
                              <span class="item-meta">${escapeHtml(entityName(pin.linked_entity_id))}</span>
                              <button class="ghost" data-reader-open-entity="${pin.linked_entity_id}" type="button">${escapeHtml(t("entity.open"))}</button>
                            </div>`
                          : ""
                      }
                    </article>
                  `,
                )
                .join("")}
            </div>`
          : `<p class="muted">${escapeHtml(t("map.noPins"))}</p>`
      }
    </section>
  `;
}

function renderDetectiveNodeReader() {
  const node = state.detectiveNodes.find((item) => item.id === state.selectedReaderSourceId);
  if (!node) {
    $("entityReaderContent").innerHTML = "";
    $("entityReader").classList.add("hidden");
    return;
  }

  const linkedEntity = node.entity_id ? state.entities.find((item) => item.id === node.entity_id) : null;
  const nodeConnections = state.detectiveConnections.filter(
    (connection) => connection.source_node_id === node.id || connection.target_node_id === node.id,
  );
  const imageHtml = linkedEntity?.attributes?.image_url
    ? `<img class="reader-image" src="${escapeHtml(linkedEntity.attributes.image_url)}" alt="" onerror="this.hidden=true" />`
    : `<div class="reader-image placeholder">${escapeHtml(linkedEntity ? linkedEntity.name : t("detective.badge"))}</div>`;

  $("entityReaderContent").innerHTML = `
    ${renderReaderHeader({
      title: node.title,
      eyebrow: linkedEntity ? t(`entityType.${linkedEntity.type}`) : t("detective.freeNote"),
      summary: linkedEntity?.summary || node.note || "",
      badge: node.is_secret ? t("common.secretValue") : t("common.public"),
      imageHtml,
    })}
    <div class="reader-reading-layout">
      <article class="reader-article">
        <div class="reader-body">${renderMarkdown(node.note || linkedEntity?.description || linkedEntity?.summary || t("common.noSummary"))}</div>
      </article>
      <aside class="reader-aside">
        ${
          linkedEntity
            ? `<section class="reader-section">
                <h3>${escapeHtml(t("detective.linkedCard"))}</h3>
                <article class="reader-subcard">
                  <div class="reader-card-head">
                    <strong>${escapeHtml(linkedEntity.name)}</strong>
                    <span class="badge">${escapeHtml(t(`entityType.${linkedEntity.type}`))}</span>
                  </div>
                  ${linkedEntity.summary ? `<div class="reader-card-body">${escapeHtml(linkedEntity.summary)}</div>` : ""}
                  <div class="reader-inline-actions">
                    <button class="ghost" data-reader-open-entity="${linkedEntity.id}" type="button">${escapeHtml(t("entity.open"))}</button>
                  </div>
                </article>
              </section>`
            : ""
        }
        ${
          node.evidence_url
            ? `<section class="reader-section">
                <h3>${escapeHtml(t("detective.evidence"))}</h3>
                <a class="reader-evidence-link" href="${escapeHtml(node.evidence_url)}" target="_blank" rel="noreferrer">${escapeHtml(node.evidence_url)}</a>
              </section>`
            : ""
        }
        <section class="reader-section">
          <h3>${escapeHtml(t("detective.connectionsLabel"))}</h3>
          ${
            nodeConnections.length
              ? `<div class="reader-card-list">
                  ${nodeConnections
                    .map((connection) => {
                      const otherNodeId =
                        connection.source_node_id === node.id ? connection.target_node_id : connection.source_node_id;
                      return `
                        <article class="reader-subcard">
                          <div class="reader-card-head">
                            <strong>${escapeHtml(detectiveNodeTitle(otherNodeId))}</strong>
                            <span class="badge">${escapeHtml(connection.label || t("detective.connection"))}</span>
                          </div>
                          ${connection.note ? `<div class="reader-card-body">${renderMarkdown(connection.note)}</div>` : ""}
                          <div class="reader-inline-actions">
                            <span class="item-meta">${escapeHtml(detectiveNodeTitle(connection.source_node_id))} -> ${escapeHtml(detectiveNodeTitle(connection.target_node_id))}</span>
                            <button class="ghost" data-reader-open-detective-node="${otherNodeId}" type="button">${escapeHtml(t("entity.open"))}</button>
                          </div>
                        </article>
                      `;
                    })
                    .join("")}
                </div>`
              : `<p class="muted">${escapeHtml(t("detective.noConnections"))}</p>`
          }
        </section>
      </aside>
    </div>
  `;
  bindEntityReaderActions();
}

function bindEntityReaderActions() {
  $("entityReaderContent")
    .querySelectorAll("[data-reader-open-entity]")
    .forEach((button) => {
      button.addEventListener("click", () => openEntityReader(button.dataset.readerOpenEntity));
    });
  $("entityReaderContent")
    .querySelectorAll("[data-reader-open-detective-node]")
    .forEach((button) => {
      button.addEventListener("click", () => openDetectiveNodeReader(button.dataset.readerOpenDetectiveNode));
    });

  // Breadcrumb actions
  const backToWikiBtn = $("entityReaderContent").querySelector('[data-breadcrumb-action="back-to-wiki"]');
  if (backToWikiBtn) {
    backToWikiBtn.addEventListener("click", () => {
      closeEntityReader();
    });
  }

  const filterTypeBtn = $("entityReaderContent").querySelector('[data-breadcrumb-action="filter-type"]');
  if (filterTypeBtn) {
    filterTypeBtn.addEventListener("click", () => {
      state.entityTypeFilter = filterTypeBtn.dataset.filterType;
      closeEntityReader();
      renderEntities();
    });
  }

  // Tab-switching and active status for TOC links
  const tocLinks = $("entityReaderContent").querySelectorAll(".toc-link");

  function showSection(targetId) {
    $("entityReaderContent").querySelectorAll(".reader-section-block").forEach((sec) => {
      if (sec.id === targetId) {
        sec.style.display = "block";
      } else {
        sec.style.display = "none";
      }
    });
  }

  // Set initial active state based on active class
  const activeLink = $("entityReaderContent").querySelector(".toc-link.active");
  if (activeLink) {
    showSection(activeLink.getAttribute("href").slice(1));
  }

  tocLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      tocLinks.forEach((l) => l.classList.remove("active"));
      link.classList.add("active");

      const targetId = link.getAttribute("href").slice(1);
      showSection(targetId);
    });
  });
}

export function renderGraph() {
  const view = $("graphView");
  if (!view) return;
  if (!state.selectedWorldId) {
    view.className = "graph-view empty";
    view.textContent = t("entity.selectWorld");
    return;
  }
  if (!state.entities.length) {
    view.className = "graph-view empty";
    view.textContent = t("graph.empty");
    return;
  }

  loadGraphPositions();

  const width = 960;
  const height = 520;
  const nodes = state.entities.map((entity, index) => {
    if (state.graphPositions[entity.id]) {
      return {
        entity,
        x: state.graphPositions[entity.id].x,
        y: state.graphPositions[entity.id].y,
        fixed: true,
      };
    }
    const columns = Math.max(1, Math.ceil(Math.sqrt(state.entities.length * (width / height))));
    const rows = Math.max(1, Math.ceil(state.entities.length / columns));
    const column = index % columns;
    const row = Math.floor(index / columns);
    const initialX = 75 + column * ((width - 150) / Math.max(columns - 1, 1));
    const initialY = 75 + row * ((height - 150) / Math.max(rows - 1, 1));
    return {
      entity,
      x: initialX,
      y: initialY,
      fixed: false,
    };
  });

  const byId = new Map(nodes.map((node) => [node.entity.id, node]));
  const edges = state.relationships
    .map((relationship) => ({
      relationship,
      source: byId.get(relationship.source_entity_id),
      target: byId.get(relationship.target_entity_id),
    }))
    .filter((edge) => edge.source && edge.target);

  if (nodes.some((node) => !node.fixed)) {
    applyForceDirectedLayout(nodes, edges, width, height);
    nodes.forEach((node) => {
      state.graphPositions[node.entity.id] = { x: node.x, y: node.y };
    });
    saveGraphPositions();
  }

  view.className = "graph-view";

  const edgesHtml = edges.map(({ relationship, source, target }, edgeIndex) => {
    const x1 = source.x;
    const y1 = source.y;
    const x2 = target.x;
    const y2 = target.y;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    const r = 45; // circle radius is 45

    // Offset the target and source position by radius so the arrow is precisely on the border
    const tx = x2 - (dx / d) * r;
    const ty = y2 - (dy / d) * r;
    const sx = x1 + (dx / d) * r;
    const sy = y1 + (dy / d) * r;

    return `
      <line class="graph-edge"
            data-edge-id="${edgeIndex}"
            data-source-entity="${relationship.source_entity_id}"
            data-target-entity="${relationship.target_entity_id}"
            x1="${sx}" y1="${sy}" x2="${tx}" y2="${ty}"
            marker-end="url(#arrow)"
            style="stroke: var(--line); stroke-width: 2;" />
      <text class="graph-label"
            data-edge-id="${edgeIndex}"
            x="${(sx + tx) / 2}" y="${(sy + ty) / 2 - 4}"
            text-anchor="middle"
            style="font-size: 11px; fill: var(--text);">
        ${escapeHtml(relationshipDisplayLabel(relationship))}
      </text>
    `;
  }).join("");

  const nodesHtml = nodes.map(({ entity, x, y }, index) => {
    return `
      <g class="graph-node-group" data-node-index="${index}" style="cursor: grab; user-select: none;">
        <circle cx="${x}" cy="${y}" r="45"
                style="fill: var(--panel); stroke: var(--accent); stroke-width: 3; filter: drop-shadow(0 2px 5px rgba(0,0,0,0.15)); transition: stroke 0.2s, fill 0.2s;" />
        <foreignObject x="${x - 38}" y="${y - 38}" width="76" height="76" style="pointer-events: none;">
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; text-align: center; padding: 4px; overflow: hidden;">
            <div class="graph-node-name" style="font-size: 11px; font-weight: bold; color: var(--text); word-break: break-word; line-height: 1.15; max-height: 44px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;">
              ${escapeHtml(entity.name)}
            </div>
            <div style="font-size: 8px; color: var(--muted); text-transform: uppercase; margin-top: 2px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 68px;">
              ${escapeHtml(t(`entityType.${entity.type}`))}
            </div>
          </div>
        </foreignObject>
      </g>
    `;
  }).join("");

  view.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;" role="img" aria-label="${escapeHtml(t("graph.title"))}">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L6,3 z" fill="var(--line)" />
        </marker>
      </defs>
      ${edgesHtml}
      ${nodesHtml}
    </svg>
  `;

  // Attach interactive drag-and-drop and click events
  const svg = view.querySelector("svg");
  let dragNode = null;
  let dragOffset = { x: 0, y: 0 };

  function updateLinePosition(line) {
    const edgeId = line.dataset.edgeId;
    const sourceId = line.dataset.sourceEntity;
    const targetId = line.dataset.targetEntity;
    const srcNode = state.graphPositions[sourceId];
    const tgtNode = state.graphPositions[targetId];
    if (!srcNode || !tgtNode) return;

    const x1 = srcNode.x;
    const y1 = srcNode.y;
    const x2 = tgtNode.x;
    const y2 = tgtNode.y;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    const r = 45;

    const tx = x2 - (dx / d) * r;
    const ty = y2 - (dy / d) * r;
    const sx = x1 + (dx / d) * r;
    const sy = y1 + (dy / d) * r;

    line.setAttribute("x1", String(sx));
    line.setAttribute("y1", String(sy));
    line.setAttribute("x2", String(tx));
    line.setAttribute("y2", String(ty));

    const label = svg.querySelector(`text[data-edge-id="${edgeId}"]`);
    if (label) {
      label.setAttribute("x", String((sx + tx) / 2));
      label.setAttribute("y", String((sy + ty) / 2 - 4));
    }
  }

  svg.querySelectorAll(".graph-node-group").forEach((group) => {
    const index = Number(group.dataset.nodeIndex);
    const node = nodes[index];
    const circle = group.querySelector("circle");

    group.addEventListener("click", () => {
      if (group.dataset.dragged === "true") {
        group.dataset.dragged = "false";
        return;
      }
      openEntityReader(node.entity.id);
    });

    group.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      dragNode = node;
      const rect = svg.getBoundingClientRect();
      const clickX = ((event.clientX - rect.left) / rect.width) * width;
      const clickY = ((event.clientY - rect.top) / rect.height) * height;
      dragOffset = {
        x: clickX - node.x,
        y: clickY - node.y,
      };
      group.setPointerCapture(event.pointerId);
      group.style.cursor = "grabbing";
      circle.style.stroke = "var(--accent-strong)";
      circle.style.fill = "var(--panel-strong)";
      group.dataset.dragged = "false";
      event.preventDefault();
      event.stopPropagation();
    });

    group.addEventListener("pointermove", (event) => {
      if (dragNode !== node) return;
      const rect = svg.getBoundingClientRect();
      const currentX = ((event.clientX - rect.left) / rect.width) * width;
      const currentY = ((event.clientY - rect.top) / rect.height) * height;

      const newX = Math.max(45, Math.min(width - 45, currentX - dragOffset.x));
      const newY = Math.max(45, Math.min(height - 45, currentY - dragOffset.y));

      node.x = newX;
      node.y = newY;
      state.graphPositions[node.entity.id] = { x: newX, y: newY };

      circle.setAttribute("cx", String(newX));
      circle.setAttribute("cy", String(newY));

      const fo = group.querySelector("foreignObject");
      if (fo) {
        fo.setAttribute("x", String(newX - 38));
        fo.setAttribute("y", String(newY - 38));
      }

      svg.querySelectorAll(`[data-source-entity="${node.entity.id}"], [data-target-entity="${node.entity.id}"]`).forEach((line) => {
        updateLinePosition(line);
      });

      group.dataset.dragged = "true";
      event.preventDefault();
    });

    const stopDrag = (event) => {
      if (dragNode !== node) return;
      dragNode = null;
      group.style.cursor = "grab";
      circle.style.stroke = "var(--accent)";
      circle.style.fill = "var(--panel)";
      saveGraphPositions();
      if (group.hasPointerCapture?.(event.pointerId)) {
        group.releasePointerCapture(event.pointerId);
      }
    };

    group.addEventListener("pointerup", stopDrag);
    group.addEventListener("pointercancel", stopDrag);
  });
}

export function arrangeGraph() {
  const key = graphPositionStorageKey();
  if (key) localStorage.removeItem(key);
  state.graphPositions = {};
  state.graphPositionScope = key;
  renderGraph();
}

function applyForceDirectedLayout(nodes, edges, width, height) {
  const velocities = new Map(nodes.map((node) => [node.entity.id, { x: 0, y: 0 }]));
  const desiredDistance = nodes.length > 24 ? 105 : 145;
  const repulsion = nodes.length > 24 ? 5200 : 7600;

  for (let iteration = 0; iteration < 180; iteration += 1) {
    const cooling = 1 - iteration / 220;
    nodes.forEach((node, index) => {
      for (let otherIndex = index + 1; otherIndex < nodes.length; otherIndex += 1) {
        const other = nodes[otherIndex];
        if (node.fixed && other.fixed) continue;
        const dx = node.x - other.x || 0.5;
        const dy = node.y - other.y || 0.5;
        const distanceSquared = Math.max(dx * dx + dy * dy, 100);
        const force = repulsion / distanceSquared;
        const distance = Math.sqrt(distanceSquared);
        if (!node.fixed) {
          const velocity = velocities.get(node.entity.id);
          velocity.x += (dx / distance) * force;
          velocity.y += (dy / distance) * force;
        }
        if (!other.fixed) {
          const otherVelocity = velocities.get(other.entity.id);
          otherVelocity.x -= (dx / distance) * force;
          otherVelocity.y -= (dy / distance) * force;
        }
      }
    });

    edges.forEach(({ source, target }) => {
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const force = (distance - desiredDistance) * 0.018;
      if (!source.fixed) {
        const velocity = velocities.get(source.entity.id);
        velocity.x += (dx / distance) * force;
        velocity.y += (dy / distance) * force;
      }
      if (!target.fixed) {
        const velocity = velocities.get(target.entity.id);
        velocity.x -= (dx / distance) * force;
        velocity.y -= (dy / distance) * force;
      }
    });

    nodes.forEach((node) => {
      if (node.fixed) return;
      const velocity = velocities.get(node.entity.id);
      velocity.x += (width / 2 - node.x) * 0.004;
      velocity.y += (height / 2 - node.y) * 0.004;
      velocity.x *= 0.72;
      velocity.y *= 0.72;
      node.x = Math.max(55, Math.min(width - 55, node.x + Math.max(-12, Math.min(12, velocity.x)) * cooling));
      node.y = Math.max(55, Math.min(height - 55, node.y + Math.max(-12, Math.min(12, velocity.y)) * cooling));
    });
  }

  resolveGraphCollisions(nodes, width, height);
}

function resolveGraphCollisions(nodes, width, height) {
  const minimumDistance = 104;
  for (let iteration = 0; iteration < 36; iteration += 1) {
    let moved = false;
    nodes.forEach((node, index) => {
      for (let otherIndex = index + 1; otherIndex < nodes.length; otherIndex += 1) {
        const other = nodes[otherIndex];
        const rawDx = other.x - node.x;
        const rawDy = other.y - node.y;
        const distance = Math.sqrt(rawDx * rawDx + rawDy * rawDy);
        if (distance >= minimumDistance) continue;

        const dx = distance > 0.01 ? rawDx / distance : index % 2 === 0 ? 1 : -1;
        const dy = distance > 0.01 ? rawDy / distance : otherIndex % 2 === 0 ? 0.5 : -0.5;
        const overlap = (minimumDistance - Math.max(distance, 0.01)) / 2;
        if (!node.fixed) {
          node.x -= dx * overlap;
          node.y -= dy * overlap;
        }
        if (!other.fixed) {
          other.x += dx * overlap;
          other.y += dy * overlap;
        }
        moved = true;
      }
    });

    nodes.forEach((node) => {
      node.x = Math.max(55, Math.min(width - 55, node.x));
      node.y = Math.max(55, Math.min(height - 55, node.y));
    });
    if (!moved) break;
  }
}

export function renderTimeline() {
  const list = $("timelineList");
  if (!list) return;
  const events = state.entities
    .filter((entity) => entity.type === "event")
    .sort((left, right) => timelineSortKey(left).localeCompare(timelineSortKey(right), undefined, { numeric: true }));
  if (!events.length) {
    list.className = "timeline-list empty";
    list.textContent = t("timeline.empty");
    return;
  }

  list.className = "timeline-list";
  list.innerHTML = events
    .map(
      (event) => `
        <article class="timeline-item">
          <div class="timeline-date">${escapeHtml(event.attributes?.timeline_date || t("timeline.noDate"))}</div>
          <div class="item">
            <div class="item-title">${escapeHtml(event.name)}</div>
            <div class="item-body">${renderMarkdown(event.summary || event.description || t("common.noSummary"))}</div>
            ${event.tags?.length ? `<div class="item-meta">${event.tags.map(escapeHtml).join(", ")}</div>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

export function renderModules() {
  renderJournal();
  renderQuests();
  renderMaps();
  renderRandomTables();
  renderDetectiveBoard();
}

function renderJournal() {
  const list = $("journalList");
  if (!list) return;
  const events = state.entities.filter((entity) => entity.type === "event");
  renderEntityMiniList(list, events, t("journal.empty"));
}

function renderQuests() {
  const list = $("questList");
  if (!list) return;
  const quests = state.entities.filter((entity) => entity.tags?.some((tag) => tag.toLowerCase() === "quest"));
  renderEntityMiniList(list, quests, t("quest.empty"));
}

function renderMaps() {
  const list = $("mapList");
  const summary = $("mapSummary");
  const master = isMasterMode();
  if (!list) return;
  const locations = state.entities.filter((entity) => entity.type === "location");
  if (summary) {
    summary.textContent = `${locations.length} ${t("map.locationsLabel")} - ${state.mapPins.length} ${t("map.pins")}`;
  }
  if (summary) {
    summary.textContent = `${locations.length} ${t("map.locationsLabel")} · ${state.mapPins.length} ${t("map.pins")}`;
  }
  if (summary) {
    summary.textContent = `${locations.length} ${t("map.locationsLabel")} - ${state.mapPins.length} ${t("map.pins")}`;
  }
  if (!locations.length) {
    list.className = "grid-list empty";
    list.textContent = t("map.empty");
    return;
  }

  list.className = "grid-list map-list";
  list.innerHTML = locations
    .map((location) => {
      const pins = state.mapPins.filter((pin) => pin.map_entity_id === location.id);
      return `
        <article class="item entity-card map-card">
          <div class="map-image-wrap" data-map-image="${location.id}">
            ${
              location.attributes?.image_url
                ? `<img class="entity-image map-image" src="${escapeHtml(location.attributes.image_url)}" alt="" loading="lazy" onerror="this.hidden=true" />`
                : `<div class="map-placeholder">${escapeHtml(t("map.noImage"))}</div>`
            }
            <div class="map-card-banner">
              <div>
                <div class="map-card-title">${escapeHtml(location.name)}</div>
                <div class="map-card-subtitle">${escapeHtml(location.summary || location.description || t("common.noSummary"))}</div>
              </div>
              <span class="badge">${pins.length} ${escapeHtml(t("map.pins"))}</span>
            </div>
            ${pins
              .map(
                (pin) => `
                  <button class="map-pin ${pin.is_secret ? "secret" : ""}" ${master ? `data-edit-map-pin="${pin.id}"` : ""} style="left: ${pin.x * 100}%; top: ${pin.y * 100}%;" type="button" title="${escapeHtml(pin.title)}">
                    <span>${escapeHtml(pin.title.slice(0, 2).toUpperCase())}</span>
                  </button>
                  ${
                    master
                      ? `<button class="map-pin-delete-badge" data-delete-map-pin="${pin.id}" style="left: calc(${pin.x * 100}% + 8px); top: calc(${pin.y * 100}% - 24px);" type="button" title="${escapeHtml(t("map.pinDelete"))}">&times;</button>`
                      : ""
                  }
                `,
              )
              .join("")}
          </div>
          <div class="map-card-actions">
            <button class="ghost" data-open-map-reader="${location.id}" type="button">${t("entity.open")}</button>
            ${master ? `<button class="ghost" data-prepare-map-pin="${location.id}" type="button">${t("map.pinAdd")}</button>` : ""}
          </div>
          ${
            pins.length
              ? `<div class="pin-list">${pins
                  .map(
                    (pin) => `
                      <div class="pin-row">
                        <span>${escapeHtml(pin.title)}${pin.linked_entity_id ? ` - ${escapeHtml(entityName(pin.linked_entity_id))}` : ""}</span>
                        ${
                          master
                            ? `<span class="item-actions">
                                <button class="ghost" data-edit-map-pin="${pin.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                                <button class="ghost danger" data-delete-map-pin="${pin.id}" type="button">${escapeHtml(t("map.pinDelete"))}</button>
                              </span>`
                            : ""
                        }
                      </div>
                    `,
                  )
                  .join("")}</div>`
              : `<div class="item-meta">${escapeHtml(t("map.noPins"))}</div>`
          }
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("[data-map-image]").forEach((container) => {
    container.addEventListener("click", (event) => {
      if (!master) return;
      if (event.target.closest("[data-edit-map-pin]") || event.target.closest("[data-delete-map-pin]")) return;
      const rect = container.getBoundingClientRect();
      setMapPinDraft(
        container.dataset.mapImage,
        (event.clientX - rect.left) / Math.max(rect.width, 1),
        (event.clientY - rect.top) / Math.max(rect.height, 1),
      );
    });
  });
  list.querySelectorAll("[data-open-map-reader]").forEach((button) => {
    button.addEventListener("click", () => openMapReader(button.dataset.openMapReader));
  });
  list.querySelectorAll("[data-prepare-map-pin]").forEach((button) => {
    button.addEventListener("click", () => {
      $("mapPinMapEntity").value = button.dataset.prepareMapPin;
      openMapPinEditor();
    });
  });
  list.querySelectorAll("[data-edit-map-pin]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      editMapPin(button.dataset.editMapPin);
    });
  });
  list.querySelectorAll("[data-delete-map-pin]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteMapPin(button.dataset.deleteMapPin);
    });
  });
}

function renderRandomTables() {
  const list = $("randomTableList");
  const master = isMasterMode();
  if (!list) return;
  if (!state.randomTables.length) {
    list.className = "grid-list empty";
    list.textContent = t("randomTable.empty");
    return;
  }

  list.className = "grid-list random-table-list";
  list.innerHTML = state.randomTables
    .map((table) => {
      const roll = state.randomTableRolls[table.id];
      return `
        <article class="item random-table-card">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(table.name)}</div>
              <div class="item-meta">${table.rows.length} ${escapeHtml(t("randomTable.rows"))} - ${table.is_secret ? escapeHtml(t("common.secretValue")) : escapeHtml(t("common.public"))}</div>
            </div>
            <div class="item-actions">
              <button data-roll-random-table="${table.id}" type="button" ${table.rows.length ? "" : "disabled"}>${escapeHtml(t("randomTable.roll"))}</button>
              ${
                master
                  ? `<button class="ghost" data-edit-random-table="${table.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                     <button class="ghost danger" data-delete-random-table="${table.id}" type="button">${escapeHtml(t("randomTable.delete"))}</button>`
                  : ""
              }
            </div>
          </div>
          ${table.description ? `<div class="item-body">${renderMarkdown(table.description)}</div>` : ""}
          ${
            roll
              ? `<div class="roll-result">
                  <div class="item-meta">${escapeHtml(t("randomTable.lastRoll"))}</div>
                  <strong>${escapeHtml(roll.label || t("randomTable.result"))}</strong>
                  <div>${escapeHtml(roll.result)}</div>
                </div>`
              : ""
          }
          ${
            table.rows.length
              ? `<div class="random-row-list">
                  ${table.rows
                    .map(
                      (row) => `
                        <div class="random-row">
                          <div>
                            <strong>${escapeHtml(row.label || t("randomTable.result"))}</strong>
                            <span class="item-meta">${escapeHtml(t("randomTable.weight"))}: ${row.weight}${row.is_secret ? ` - ${escapeHtml(t("common.secretValue"))}` : ""}</span>
                            <div>${renderMarkdown(row.result)}</div>
                          </div>
                          ${
                            master
                              ? `<span class="item-actions">
                                  <button class="ghost" data-edit-random-row="${table.id}:${row.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                                  <button class="ghost danger" data-delete-random-row="${row.id}" type="button">${escapeHtml(t("randomTable.rowDelete"))}</button>
                                </span>`
                              : ""
                          }
                        </div>
                      `,
                    )
                    .join("")}
                </div>`
              : `<div class="item-meta">${escapeHtml(t("randomTable.noRows"))}</div>`
          }
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("[data-roll-random-table]").forEach((button) => {
    button.addEventListener("click", () => rollRandomTable(button.dataset.rollRandomTable));
  });
  list.querySelectorAll("[data-edit-random-table]").forEach((button) => {
    button.addEventListener("click", () => editRandomTable(button.dataset.editRandomTable));
  });
  list.querySelectorAll("[data-delete-random-table]").forEach((button) => {
    button.addEventListener("click", () => deleteRandomTable(button.dataset.deleteRandomTable));
  });
  list.querySelectorAll("[data-edit-random-row]").forEach((button) => {
    button.addEventListener("click", () => {
      const [tableId, rowId] = button.dataset.editRandomRow.split(":");
      editRandomTableRow(tableId, rowId);
    });
  });
  list.querySelectorAll("[data-delete-random-row]").forEach((button) => {
    button.addEventListener("click", () => deleteRandomTableRow(button.dataset.deleteRandomRow));
  });
}

function setDetectiveBoardNodePosition(nodeElement, x, y) {
  nodeElement.style.left = `${x * 100}%`;
  nodeElement.style.top = `${y * 100}%`;
  nodeElement.dataset.nodeX = String(x);
  nodeElement.dataset.nodeY = String(y);
}

function updateDetectiveBoardConnections(board, nodeId) {
  board.querySelectorAll(`[data-source-node="${nodeId}"], [data-target-node="${nodeId}"]`).forEach((element) => {
    const sourceElement = board.querySelector(`[data-detective-node="${element.dataset.sourceNode}"]`);
    const targetElement = board.querySelector(`[data-detective-node="${element.dataset.targetNode}"]`);
    if (!sourceElement || !targetElement) return;

    const sourceX = Number(sourceElement.dataset.nodeX || 0);
    const sourceY = Number(sourceElement.dataset.nodeY || 0);
    const targetX = Number(targetElement.dataset.nodeX || 0);
    const targetY = Number(targetElement.dataset.nodeY || 0);

    if (element.tagName.toLowerCase() === "line") {
      element.setAttribute("x1", String(sourceX * 100));
      element.setAttribute("y1", String(sourceY * 100));
      element.setAttribute("x2", String(targetX * 100));
      element.setAttribute("y2", String(targetY * 100));
      return;
    }

    element.setAttribute("x", String(((sourceX + targetX) / 2) * 100));
    element.setAttribute("y", String(((sourceY + targetY) / 2) * 100));
  });
}

function clampBoardCoordinate(value) {
  return Math.min(1, Math.max(0, value));
}

/*
function renderDetectiveBoardLegacy() {
  const board = $("detectiveBoardView");
  const connectionList = $("detectiveConnectionList");
  const summary = $("detectiveSummary");
  if (!board || !connectionList) return;
  if (summary) {
    summary.textContent = `${state.detectiveNodes.length} ${t("detective.nodesLabel")} · ${state.detectiveConnections.length} ${t("detective.connectionsLabel")}`;
  }
  board.onclick = (event) => {
    if (event.target.closest(".detective-node")) return;
    const rect = board.getBoundingClientRect();
    setDetectiveNodeDraft(
      (event.clientX - rect.left) / Math.max(rect.width, 1),
      (event.clientY - rect.top) / Math.max(rect.height, 1),
    );
  };

  if (!state.detectiveNodes.length) {
    board.className = "detective-board empty";
    board.textContent = t("detective.empty");
  } else {
    board.className = "detective-board";
    const nodeById = new Map(state.detectiveNodes.map((node) => [node.id, node]));
    const visibleConnections = state.detectiveConnections
      .map((connection) => ({
        connection,
        source: nodeById.get(connection.source_node_id),
        target: nodeById.get(connection.target_node_id),
      }))
      .filter((item) => item.source && item.target);

    board.innerHTML = `
      <svg class="detective-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        ${visibleConnections
          .map(
            ({ connection, source, target }) => `
              <line x1="${source.x * 100}" y1="${source.y * 100}" x2="${target.x * 100}" y2="${target.y * 100}" />
              ${
                connection.label
                  ? `<text x="${((source.x + target.x) / 2) * 100}" y="${((source.y + target.y) / 2) * 100}">${escapeHtml(connection.label)}</text>`
                  : ""
              }
            `,
          )
          .join("")}
      </svg>
      ${state.detectiveNodes
        .map(
          (node) => `
            <article class="detective-node ${node.is_secret ? "secret" : ""}" style="left: ${node.x * 100}%; top: ${node.y * 100}%;">
              <div class="item-title">${escapeHtml(node.title)}</div>
              <div class="item-meta">${node.entity_id ? escapeHtml(entityName(node.entity_id)) : escapeHtml(t("detective.freeNote"))}${node.is_secret ? ` - ${escapeHtml(t("common.secretValue"))}` : ""}</div>
              ${node.note ? `<div class="item-body">${renderMarkdown(node.note)}</div>` : ""}
              ${node.evidence_url ? `<a href="${escapeHtml(node.evidence_url)}" target="_blank" rel="noreferrer">${escapeHtml(t("detective.evidence"))}</a>` : ""}
              <div class="item-actions">
                <button class="ghost" data-open-detective-node="${node.id}" type="button">${escapeHtml(t("entity.open"))}</button>
                <button class="ghost" data-edit-detective-node="${node.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                <button class="ghost danger" data-delete-detective-node="${node.id}" type="button">${escapeHtml(t("detective.nodeDelete"))}</button>
              </div>
            </article>
          `,
        )
        .join("")}
    `;
  }

  board.querySelectorAll("[data-edit-detective-node]").forEach((button) => {
    button.addEventListener("click", () => editDetectiveNode(button.dataset.editDetectiveNode));
  });
  board.querySelectorAll("[data-open-detective-node]").forEach((button) => {
    button.addEventListener("click", () => openDetectiveNodeReader(button.dataset.openDetectiveNode));
  });
  board.querySelectorAll("[data-delete-detective-node]").forEach((button) => {
    button.addEventListener("click", () => deleteDetectiveNode(button.dataset.deleteDetectiveNode));
  });

  if (!state.detectiveConnections.length) {
    connectionList.className = "grid-list empty";
    connectionList.textContent = t("detective.noConnections");
    return;
  }

  connectionList.className = "grid-list detective-connection-list";
  connectionList.innerHTML = state.detectiveConnections
    .map(
      (connection) => `
        <article class="item detective-connection-card">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(detectiveNodeTitle(connection.source_node_id))} → ${escapeHtml(detectiveNodeTitle(connection.target_node_id))}</div>
              <div class="item-meta">${escapeHtml(connection.label || t("detective.connection"))}${connection.is_secret ? ` - ${escapeHtml(t("common.secretValue"))}` : ""}</div>
            </div>
            <div class="item-actions">
              <button class="ghost" data-edit-detective-connection="${connection.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
              <button class="ghost danger" data-delete-detective-connection="${connection.id}" type="button">${escapeHtml(t("detective.connectionDelete"))}</button>
            </div>
          </div>
          ${connection.note ? `<div class="item-body">${renderMarkdown(connection.note)}</div>` : ""}
        </article>
      `,
    )
    .join("");
  connectionList.querySelectorAll("[data-edit-detective-connection]").forEach((button) => {
    button.addEventListener("click", () => editDetectiveConnection(button.dataset.editDetectiveConnection));
  });
  connectionList.querySelectorAll("[data-delete-detective-connection]").forEach((button) => {
    button.addEventListener("click", () => deleteDetectiveConnection(button.dataset.deleteDetectiveConnection));
  });
}

*/
function renderEntityMiniList(list, entities, emptyText) {
  if (!entities.length) {
    list.className = "grid-list empty";
    list.textContent = emptyText;
    return;
  }
  list.className = "grid-list";
  list.innerHTML = entities
    .map(
      (entity) => `
        <article class="item entity-card compact-card">
          ${entity.attributes?.image_url ? `<img class="entity-image" src="${escapeHtml(entity.attributes.image_url)}" alt="" loading="lazy" onerror="this.hidden=true" />` : ""}
          <div class="item-title">${escapeHtml(entity.name)}</div>
          <div class="item-meta">${escapeHtml(t(`entityType.${entity.type}`))}${entity.attributes?.timeline_date ? ` - ${escapeHtml(entity.attributes.timeline_date)}` : ""}</div>
          <div class="item-body">${renderMarkdown(entity.summary || entity.description || t("common.noSummary"))}</div>
          ${entity.tags?.length ? `<div class="item-meta">${entity.tags.map(escapeHtml).join(", ")}</div>` : ""}
        </article>
      `,
    )
    .join("");
}

function timelineSortKey(entity) {
  return String(entity.attributes?.timeline_date || entity.created_at || entity.name);
}

function shortLabel(value) {
  const text = String(value || "");
  return text.length > 18 ? `${text.slice(0, 15)}...` : text;
}

const relationshipLabelTranslations = {
  is_involved_in: { en: "is involved in", ru: "участвует в" },
  involved_in: { en: "is involved in", ru: "участвует в" },
  member_of: { en: "member of", ru: "состоит в" },
  belongs_to: { en: "belongs to", ru: "принадлежит" },
  located_in: { en: "located in", ru: "находится в" },
  controls: { en: "controls", ru: "контролирует" },
  founded: { en: "founded", ru: "основал" },
  guards: { en: "guards", ru: "охраняет" },
  knows: { en: "knows", ru: "знает" },
  ally_of: { en: "ally of", ru: "союзник" },
  enemy_of: { en: "enemy of", ru: "враг" },
  related_to: { en: "related to", ru: "связан с" },
};

function relationshipDisplayLabel(relationship) {
  if (relationship.label) return relationship.label;
  const normalizedType = String(relationship.type || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const translated = relationshipLabelTranslations[normalizedType]?.[language()];
  if (translated) return translated;
  return normalizedType.replace(/_/g, " ") || relationship.type || "";
}

function graphPositionStorageKey() {
  return state.selectedWorldId ? `worldbuilder.graphPositions.${state.selectedWorldId}.${currentRole()}` : null;
}

function loadGraphPositions() {
  const key = graphPositionStorageKey();
  if (!key) {
    state.graphPositions = {};
    state.graphPositionScope = null;
    return;
  }
  if (state.graphPositionScope === key) return;
  state.graphPositionScope = key;
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "{}");
    state.graphPositions = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    state.graphPositions = {};
  }
}

function saveGraphPositions() {
  const key = graphPositionStorageKey();
  if (!key) return;
  state.graphPositionScope = key;
  localStorage.setItem(key, JSON.stringify(state.graphPositions));
}

export function renderRelationshipOptions() {
  const options = state.entities
    .map((entity) => `<option value="${entity.id}">${escapeHtml(entity.name)} (${escapeHtml(t(`entityType.${entity.type}`))})</option>`)
    .join("");
  $("relationshipSource").innerHTML = options;
  $("relationshipTarget").innerHTML = options;
}

export function renderMapPinOptions() {
  const mapOptions = state.entities
    .filter((entity) => entity.type === "location")
    .map((entity) => `<option value="${entity.id}">${escapeHtml(entity.name)}</option>`)
    .join("");
  const linkedOptions = state.entities
    .map((entity) => `<option value="${entity.id}">${escapeHtml(entity.name)} (${escapeHtml(t(`entityType.${entity.type}`))})</option>`)
    .join("");
  $("mapPinMapEntity").innerHTML = mapOptions;
  $("mapPinLinkedEntity").innerHTML = `<option value="">${escapeHtml(t("common.none"))}</option>${linkedOptions}`;
}

export function renderRandomTableOptions() {
  const options = state.randomTables
    .map((table) => `<option value="${table.id}">${escapeHtml(table.name)}</option>`)
    .join("");
  $("randomTableRowTable").innerHTML = options;
}

export function renderDetectiveOptions() {
  const entityOptions = state.entities
    .map((entity) => `<option value="${entity.id}">${escapeHtml(entity.name)} (${escapeHtml(t(`entityType.${entity.type}`))})</option>`)
    .join("");
  const nodeOptions = state.detectiveNodes
    .map((node) => `<option value="${node.id}">${escapeHtml(node.title)}</option>`)
    .join("");
  $("detectiveNodeEntity").innerHTML = `<option value="">${escapeHtml(t("detective.freeNote"))}</option>${entityOptions}`;
  $("detectiveConnectionSource").innerHTML = nodeOptions;
  $("detectiveConnectionTarget").innerHTML = nodeOptions;
}

export function entityName(id) {
  return state.entities.find((entity) => entity.id === id)?.name || id.slice(0, 8);
}

function renderDetectiveBoard() {
  const board = $("detectiveBoardView");
  const connectionList = $("detectiveConnectionList");
  const summary = $("detectiveSummary");
  const master = isMasterMode();
  if (!board || !connectionList) return;
  if (summary) {
    summary.textContent = `${state.detectiveNodes.length} ${t("detective.nodesLabel")} - ${state.detectiveConnections.length} ${t("detective.connectionsLabel")}`;
  }
  $("generateDetectiveBoard")?.classList.toggle("hidden", !master || state.detectiveNodes.length > 0);
  $("deleteDetectiveBoard")?.classList.toggle("hidden", !master || state.detectiveNodes.length === 0);

  let suppressBoardClick = false;
  let dragState = null;

  board.onclick = (event) => {
    if (!master) return;
    if (suppressBoardClick) {
      suppressBoardClick = false;
      return;
    }
    if (event.target.closest(".detective-node")) return;
    const rect = board.getBoundingClientRect();
    setDetectiveNodeDraft(
      (event.clientX - rect.left) / Math.max(rect.width, 1),
      (event.clientY - rect.top) / Math.max(rect.height, 1),
    );
  };

  if (!state.detectiveNodes.length) {
    board.className = "detective-board empty";
    board.textContent = t("detective.empty");
  } else {
    board.className = "detective-board";
    const nodeById = new Map(state.detectiveNodes.map((node) => [node.id, node]));
    const visibleConnections = state.detectiveConnections
      .map((connection) => ({
        connection,
        source: nodeById.get(connection.source_node_id),
        target: nodeById.get(connection.target_node_id),
      }))
      .filter((item) => item.source && item.target);

    board.innerHTML = `
      <svg class="detective-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        ${visibleConnections
          .map(
            ({ connection, source, target }) => `
              <line data-source-node="${source.id}" data-target-node="${target.id}" x1="${source.x * 100}" y1="${source.y * 100}" x2="${target.x * 100}" y2="${target.y * 100}" />
              ${
                connection.label
                  ? `<text data-source-node="${source.id}" data-target-node="${target.id}" x="${((source.x + target.x) / 2) * 100}" y="${((source.y + target.y) / 2) * 100}">${escapeHtml(connection.label)}</text>`
                  : ""
              }
            `,
          )
          .join("")}
      </svg>
      ${state.detectiveNodes
        .map(
          (node) => `
            <article class="detective-node ${node.is_secret ? "secret" : ""}" data-detective-node="${node.id}" data-node-x="${node.x}" data-node-y="${node.y}" style="left: ${node.x * 100}%; top: ${node.y * 100}%;">
              <div class="item-title">${escapeHtml(node.title)}</div>
              <div class="item-meta">${node.entity_id ? escapeHtml(entityName(node.entity_id)) : escapeHtml(t("detective.freeNote"))}${node.is_secret ? ` - ${escapeHtml(t("common.secretValue"))}` : ""}</div>
              ${node.note ? `<div class="item-body">${renderMarkdown(node.note)}</div>` : ""}
              ${node.evidence_url ? `<a href="${escapeHtml(node.evidence_url)}" target="_blank" rel="noreferrer">${escapeHtml(t("detective.evidence"))}</a>` : ""}
              <div class="item-actions">
                <button class="ghost" data-open-detective-node="${node.id}" type="button">${escapeHtml(t("entity.open"))}</button>
                ${
                  master
                    ? `<button class="ghost" data-edit-detective-node="${node.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                       <button class="ghost danger" data-delete-detective-node="${node.id}" type="button">${escapeHtml(t("detective.nodeDelete"))}</button>`
                    : ""
                }
              </div>
            </article>
          `,
        )
        .join("")}
    `;
  }

  board.querySelectorAll("[data-edit-detective-node]").forEach((button) => {
    button.addEventListener("click", () => editDetectiveNode(button.dataset.editDetectiveNode));
  });
  board.querySelectorAll("[data-open-detective-node]").forEach((button) => {
    button.addEventListener("click", () => openDetectiveNodeReader(button.dataset.openDetectiveNode));
  });
  board.querySelectorAll("[data-delete-detective-node]").forEach((button) => {
    button.addEventListener("click", () => deleteDetectiveNode(button.dataset.deleteDetectiveNode));
  });
  board.querySelectorAll("[data-detective-node]").forEach((nodeElement) => {
    nodeElement.addEventListener("pointerdown", (event) => {
      if (!master) return;
      if (event.button !== 0) return;
      if (event.target.closest("button, a")) return;

      const boardRect = board.getBoundingClientRect();
      const nodeRect = nodeElement.getBoundingClientRect();
      dragState = {
        pointerId: event.pointerId,
        nodeId: nodeElement.dataset.detectiveNode,
        nodeElement,
        boardRect,
        offsetX: event.clientX - (nodeRect.left + nodeRect.width / 2),
        offsetY: event.clientY - (nodeRect.top + nodeRect.height / 2),
        x: Number(nodeElement.dataset.nodeX || 0.5),
        y: Number(nodeElement.dataset.nodeY || 0.5),
        moved: false,
      };
      suppressBoardClick = false;
      nodeElement.classList.add("dragging");
      board.classList.add("dragging");
      nodeElement.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    nodeElement.addEventListener("pointermove", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId || dragState.nodeElement !== nodeElement) return;

      const nextX = clampBoardCoordinate(
        (event.clientX - dragState.boardRect.left - dragState.offsetX) / Math.max(dragState.boardRect.width, 1),
      );
      const nextY = clampBoardCoordinate(
        (event.clientY - dragState.boardRect.top - dragState.offsetY) / Math.max(dragState.boardRect.height, 1),
      );

      dragState.x = nextX;
      dragState.y = nextY;
      dragState.moved = true;
      setDetectiveBoardNodePosition(nodeElement, nextX, nextY);
      updateDetectiveBoardConnections(board, dragState.nodeId);

      if (state.editingDetectiveNodeId === dragState.nodeId) {
        $("detectiveNodeX").value = Math.round(nextX * 1000) / 10;
        $("detectiveNodeY").value = Math.round(nextY * 1000) / 10;
      }

      event.preventDefault();
    });

    const finishDrag = async (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId || dragState.nodeElement !== nodeElement) return;

      const currentDrag = dragState;
      dragState = null;
      currentDrag.nodeElement.classList.remove("dragging");
      board.classList.remove("dragging");
      if (currentDrag.nodeElement.hasPointerCapture?.(event.pointerId)) {
        currentDrag.nodeElement.releasePointerCapture(event.pointerId);
      }
      if (!currentDrag.moved) return;

      suppressBoardClick = true;
      window.setTimeout(() => {
        suppressBoardClick = false;
      }, 0);

      try {
        await persistDetectiveNodePosition(currentDrag.nodeId, currentDrag.x, currentDrag.y);
      } catch {
        renderAllWorldData();
      }
    };

    nodeElement.addEventListener("pointerup", (event) => {
      void finishDrag(event);
    });
    nodeElement.addEventListener("pointercancel", (event) => {
      void finishDrag(event);
    });
    nodeElement.addEventListener("lostpointercapture", (event) => {
      void finishDrag(event);
    });
  });

  if (!state.detectiveConnections.length) {
    connectionList.className = "grid-list empty";
    connectionList.textContent = t("detective.noConnections");
    return;
  }

  connectionList.className = "grid-list detective-connection-list";
  connectionList.innerHTML = state.detectiveConnections
    .map(
      (connection) => `
        <article class="item detective-connection-card">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(detectiveNodeTitle(connection.source_node_id))} -> ${escapeHtml(detectiveNodeTitle(connection.target_node_id))}</div>
              <div class="item-meta">${escapeHtml(connection.label || t("detective.connection"))}${connection.is_secret ? ` - ${escapeHtml(t("common.secretValue"))}` : ""}</div>
            </div>
            ${
              master
                ? `<div class="item-actions">
                    <button class="ghost" data-edit-detective-connection="${connection.id}" type="button">${escapeHtml(t("entity.edit"))}</button>
                    <button class="ghost danger" data-delete-detective-connection="${connection.id}" type="button">${escapeHtml(t("detective.connectionDelete"))}</button>
                  </div>`
                : ""
            }
          </div>
          ${connection.note ? `<div class="item-body">${renderMarkdown(connection.note)}</div>` : ""}
        </article>
      `,
    )
    .join("");
  connectionList.querySelectorAll("[data-edit-detective-connection]").forEach((button) => {
    button.addEventListener("click", () => editDetectiveConnection(button.dataset.editDetectiveConnection));
  });
  connectionList.querySelectorAll("[data-delete-detective-connection]").forEach((button) => {
    button.addEventListener("click", () => deleteDetectiveConnection(button.dataset.deleteDetectiveConnection));
  });
}

function detectiveNodeTitle(id) {
  return state.detectiveNodes.find((node) => node.id === id)?.title || id.slice(0, 8);
}

function randomTableName(id) {
  return state.randomTables.find((table) => table.id === id)?.name || id.slice(0, 8);
}

export function renderRelationships() {
  const list = $("relationshipList");
  const master = isMasterMode();
  if (!state.relationships.length) {
    list.className = "grid-list empty";
    list.textContent = t("relationship.empty");
    return;
  }

  list.className = "grid-list";
  list.innerHTML = state.relationships
    .map(
      (relationship) => `
        <article class="item">
          <div class="item-top" style="display: flex; justify-content: space-between; align-items: center;">
            <div class="item-title">${escapeHtml(entityName(relationship.source_entity_id))} &rarr; ${escapeHtml(entityName(relationship.target_entity_id))}</div>
            ${master ? `<div class="item-actions compact-actions">
              <button class="ghost" data-edit-relationship="${relationship.id}" type="button">${escapeHtml(t("common.edit"))}</button>
              <button class="ghost danger" data-delete-relationship="${relationship.id}" type="button">${escapeHtml(t("common.delete"))}</button>
            </div>` : ""}
          </div>
          <div class="item-meta">${escapeHtml(relationshipDisplayLabel(relationship))} - ${escapeHtml(relationshipConfidenceText(relationship.confidence))}</div>
          ${relationship.description ? `<div class="item-body">${renderMarkdown(relationship.description)}</div>` : ""}
        </article>
      `,
    )
    .join("");

  list.querySelectorAll("[data-delete-relationship]").forEach((btn) => {
    btn.addEventListener("click", () => deleteRelationship(btn.dataset.deleteRelationship));
  });
  list.querySelectorAll("[data-edit-relationship]").forEach((btn) => {
    btn.addEventListener("click", () => editRelationship(btn.dataset.editRelationship));
  });
}

function relationshipConfidenceText(confidence) {
  const value = Math.round(Number(confidence || 0) * 100);
  const level = value >= 85 ? "high" : value >= 50 ? "medium" : "low";
  return `${t("relationship.confidence")}: ${value}% - ${t(`relationship.confidence.${level}`)}`;
}

export function renderRules() {
  const list = $("ruleList");
  const master = isMasterMode();
  if (!state.rules.length) {
    list.className = "grid-list empty";
    list.textContent = t("rule.empty");
    return;
  }

  list.className = "grid-list";
  list.innerHTML = state.rules
    .map(
      (rule) => `
        <article class="item">
          <div class="item-top" style="display: flex; justify-content: space-between; align-items: center;">
            <div class="item-title">${t("rule.priority")} ${rule.priority}</div>
            <div style="display:flex; gap:8px; align-items:center;">
              <span class="badge">${rule.is_secret ? t("common.secretValue") : t("common.public")}</span>
              ${master ? `<button class="ghost danger small-delete-btn" data-delete-rule="${rule.id}" type="button">&times;</button>` : ""}
            </div>
          </div>
          <div class="item-body rule-markdown"><strong>${t("rule.if")}:</strong>${renderMarkdown(rule.condition)}<strong>${t("rule.then")}:</strong>${renderMarkdown(rule.effect)}</div>
          <div class="item-meta">${escapeHtml(rule.status)}${rule.tags?.length ? ` - ${rule.tags.map(escapeHtml).join(", ")}` : ""}</div>
        </article>
      `,
    )
    .join("");

  list.querySelectorAll("[data-delete-rule]").forEach((btn) => {
    btn.addEventListener("click", () => deleteRule(btn.dataset.deleteRule));
  });
}

export function renderProposals() {
  const list = $("proposalList");
  if (!state.proposals.length) {
    list.className = "grid-list empty";
    list.textContent = t("proposal.empty");
    return;
  }

  list.className = "grid-list";
  list.innerHTML = state.proposals
    .map((proposal) => {
      const counts = [
        `${proposal.payload.entities.length} ${t("proposal.entities")}`,
        `${proposal.payload.relationships.length} ${t("proposal.relationships")}`,
        `${proposal.payload.world_rules.length} ${t("proposal.rules")}`,
        `${(proposal.payload.random_tables || []).length} ${t("proposal.randomTables")}`,
        `${(proposal.payload.random_table_rows || []).length} ${t("proposal.randomRows")}`,
      ].join(" - ");
      return `
        <article class="item">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(t(`proposal.status.${proposal.status}`))}</div>
              <div class="item-meta">${counts} - ${escapeHtml(proposal.id.slice(0, 8))}</div>
            </div>
            <span class="badge">${new Date(proposal.created_at).toLocaleString()}</span>
          </div>
          <div class="item-body proposal-source">${renderMarkdown(proposal.source_text)}</div>
          ${proposal.error ? `<div class="item-body danger">${escapeHtml(proposal.error)}</div>` : ""}
          ${renderProposalReview(proposal)}
          <div class="item-actions">
            <button data-apply-proposal="${proposal.id}" type="button" title="${escapeHtml(t("proposal.applyTitle"))}" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.apply")}</button>
            <button data-apply-selected-proposal="${proposal.id}" class="ghost" type="button" title="${escapeHtml(t("proposal.applySelectedTitle"))}" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.applySelected")}</button>
            <button data-reject-proposal="${proposal.id}" class="ghost danger" type="button" title="${escapeHtml(t("proposal.rejectTitle"))}" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.reject")}</button>
            <button data-delete-proposal="${proposal.id}" class="ghost danger" type="button" title="${escapeHtml(t("proposal.deleteTitle"))}">${t("common.delete")}</button>
          </div>
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("[data-apply-proposal]").forEach((button) => {
    button.addEventListener("click", () => applyProposal(button.dataset.applyProposal));
  });
  list.querySelectorAll("[data-apply-selected-proposal]").forEach((button) => {
    button.addEventListener("click", () => applySelectedProposal(button.dataset.applySelectedProposal));
  });
  list.querySelectorAll("[data-reject-proposal]").forEach((button) => {
    button.addEventListener("click", () => rejectProposal(button.dataset.rejectProposal));
  });
  list.querySelectorAll("[data-delete-proposal]").forEach((button) => {
    button.addEventListener("click", () => deleteProposal(button.dataset.deleteProposal));
  });
}

function renderProposalReview(proposal) {
  const disabled = proposal.status !== "pending" ? "disabled" : "";
  const sections = [
    {
      title: t("proposal.entities"),
      kind: "entity",
      items: proposal.payload.entities.map((entity) => ({
        summary: `${t(`entityType.${entity.type}`)}: ${entity.name}${entity.summary ? ` - ${entity.summary}` : ""}`,
        excerpt: entity.source_excerpt || "",
        intent: entityReviewIntent(entity),
        changes: entityReviewChanges(entity),
        changeDetails: entityReviewChangeDetails(entity),
      })),
    },
    {
      title: t("proposal.relationships"),
      kind: "relationship",
      items: proposal.payload.relationships.map((relationship) => ({
        summary: `${relationship.source_client_id || relationship.source_entity_id} -> ${relationship.target_client_id || relationship.target_entity_id}: ${relationshipDisplayLabel(relationship)}`,
        excerpt: relationship.source_excerpt || "",
      })),
    },
    {
      title: t("proposal.rules"),
      kind: "rule",
      items: proposal.payload.world_rules.map((rule) => ({
        summary: `${t("rule.if")}: ${rule.condition} ${t("rule.then")}: ${rule.effect}`,
        excerpt: rule.source_excerpt || "",
      })),
    },
    {
      title: t("proposal.randomTables"),
      kind: "random-table",
      items: (proposal.payload.random_tables || []).map((table) => ({
        summary: `${table.name}${table.description ? ` - ${table.description}` : ""}`,
        excerpt: table.source_excerpt || "",
        changes: [table.is_secret ? t("common.secretValue") : t("common.public")],
      })),
    },
    {
      title: t("proposal.randomRows"),
      kind: "random-table-row",
      items: (proposal.payload.random_table_rows || []).map((row) => ({
        summary: `${proposalRandomTableName(proposal, row)}: ${row.label ? `${row.label} - ` : ""}${row.result}`,
        excerpt: row.source_excerpt || "",
        changes: [
          `${t("randomTable.weight")}: ${row.weight}`,
          row.is_secret ? t("common.secretValue") : t("common.public"),
        ],
      })),
    },
  ];
  return `
    <div class="proposal-review">
      ${sections
        .map((section) =>
          section.items.length
            ? `<div class="proposal-review-section">
                <div class="item-meta">${escapeHtml(section.title)}</div>
                ${section.items
                  .map(
                    (item, index) => `
                      <label class="check proposal-check">
                        <input data-proposal-id="${proposal.id}" data-proposal-kind="${section.kind}" data-proposal-index="${index}" type="checkbox" checked ${disabled} />
                        <div class="proposal-check-content">
                          ${renderMarkdown(item.summary)}
                          ${item.intent ? `<small class="proposal-intent">${escapeHtml(item.intent)}</small>` : ""}
                          ${item.changes?.length ? `<small class="proposal-change-summary">${escapeHtml(item.changes.join(", "))}</small>` : ""}
                          ${item.changeDetails?.length ? item.changeDetails.map((detail) => `<small class="proposal-change-detail">${escapeHtml(detail)}</small>`).join("") : ""}
                          ${item.excerpt ? `<div class="proposal-evidence"><small>${escapeHtml(t("proposal.sourceText"))}</small>${renderMarkdown(item.excerpt)}</div>` : ""}
                        </div>
                      </label>
                    `,
                  )
                  .join("")}
              </div>`
            : "",
        )
        .join("")}
      ${
        proposal.payload.notes?.length
          ? `<div class="proposal-review-section">
              <div class="item-meta">${escapeHtml(t("proposal.notes"))}</div>
              <div class="proposal-notes">${proposal.payload.notes.map((note) => renderMarkdown(note)).join("")}</div>
            </div>`
          : ""
      }
    </div>
  `;
}

function proposalRandomTableName(proposal, row) {
  if (row.table_id) return randomTableName(row.table_id);
  return (proposal.payload.random_tables || []).find((table) => table.client_id === row.table_client_id)?.name || row.table_client_id;
}

function findMatchedProposalEntity(entity) {
  return entity.match_entity_id
    ? state.entities.find((item) => item.id === entity.match_entity_id)
    : state.entities.find((item) => item.type === entity.type && item.name === entity.name);
}

function entityReviewIntent(entity) {
  const matchedEntity = findMatchedProposalEntity(entity);

  if (!matchedEntity) {
    return t("entity.add");
  }

  return `${t("entity.edit")}: ${matchedEntity.name} (${matchedEntity.id.slice(0, 8)})`;
}

function entityReviewChanges(entity) {
  const matchedEntity = findMatchedProposalEntity(entity);
  if (!matchedEntity) {
    return [];
  }

  const projectedEntity = projectEntityReviewResult(matchedEntity, entity);
  const changes = [];
  if (comparableValue(projectedEntity.type) !== comparableValue(matchedEntity.type)) changes.push(t("entity.type"));
  if (comparableValue(projectedEntity.name) !== comparableValue(matchedEntity.name)) changes.push(t("common.name"));
  if (comparableValue(projectedEntity.summary) !== comparableValue(matchedEntity.summary)) changes.push(t("entity.summary"));
  if (comparableValue(projectedEntity.description) !== comparableValue(matchedEntity.description)) changes.push(t("common.description"));
  if (!sameStringList(projectedEntity.aliases, matchedEntity.aliases)) changes.push("aliases");
  if (!sameStringList(projectedEntity.tags, matchedEntity.tags)) changes.push(t("common.tags"));
  if (Boolean(projectedEntity.is_secret) !== Boolean(matchedEntity.is_secret)) changes.push(t("common.secret"));
  if (comparableValue(projectedEntity.status) !== comparableValue(matchedEntity.status)) changes.push("status");
  changes.push(...attributeChangeLabels(projectedEntity.attributes || {}, matchedEntity.attributes || {}, entity.attributes || {}));

  return Array.from(new Set(changes));
}

function entityReviewChangeDetails(entity) {
  const matchedEntity = findMatchedProposalEntity(entity);
  if (!matchedEntity) {
    return [];
  }

  const projectedEntity = projectEntityReviewResult(matchedEntity, entity);
  const details = [];

  appendEntityChangeDetail(details, t("entity.type"), matchedEntity.type, projectedEntity.type, { formatter: formatEntityTypeValue });
  appendEntityChangeDetail(details, t("common.name"), matchedEntity.name, projectedEntity.name);
  appendEntityChangeDetail(details, t("entity.summary"), matchedEntity.summary, projectedEntity.summary);
  appendEntityChangeDetail(details, t("common.description"), matchedEntity.description, projectedEntity.description);
  appendEntityChangeDetail(details, "aliases", matchedEntity.aliases, projectedEntity.aliases, { formatter: formatListValue });
  appendEntityChangeDetail(details, t("common.tags"), matchedEntity.tags, projectedEntity.tags, { formatter: formatListValue });
  appendEntityChangeDetail(details, t("common.secret"), matchedEntity.is_secret, projectedEntity.is_secret, { formatter: formatSecretValue });
  appendEntityChangeDetail(details, "status", matchedEntity.status, projectedEntity.status);

  for (const key of Object.keys(entity.attributes || {}).sort()) {
    appendEntityChangeDetail(details, attributeLabel(key), matchedEntity.attributes?.[key], projectedEntity.attributes?.[key]);
  }

  return details;
}

function projectEntityReviewResult(matchedEntity, entity) {
  return {
    type: entity.type,
    name: entity.name,
    summary: entity.summary ?? matchedEntity.summary,
    description: entity.description ?? matchedEntity.description,
    aliases: mergeStringLists(matchedEntity.aliases, entity.aliases),
    tags: mergeStringLists(matchedEntity.tags, entity.tags),
    is_secret: entity.is_secret,
    status: entity.status,
    attributes: {
      ...(matchedEntity.attributes || {}),
      ...(entity.attributes || {}),
    },
  };
}

function attributeChangeLabels(projectedAttributes, currentAttributes, draftAttributes) {
  const keys = Object.keys(draftAttributes || {});
  const labels = [];

  for (const key of keys) {
    if (comparableValue(projectedAttributes[key]) !== comparableValue(currentAttributes[key])) {
      labels.push(attributeLabel(key));
    }
  }

  return labels;
}

function attributeLabel(key) {
  if (key === "image_url") return t("entity.imageUrl");
  if (key === "timeline_date") return t("entity.timelineDate");
  return key.replace(/[_-]+/g, " ").trim();
}

function sameStringList(left, right) {
  return comparableValue(normalizeStringList(left)) === comparableValue(normalizeStringList(right));
}

function mergeStringLists(currentValues, incomingValues) {
  return normalizeStringList([...(currentValues || []), ...(incomingValues || [])]);
}

function normalizeStringList(values) {
  return Array.isArray(values)
    ? Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean)))
    : [];
}

function appendEntityChangeDetail(details, label, currentValue, nextValue, options = {}) {
  const formatter = options.formatter || formatDisplayValue;
  if (comparableValue(currentValue) === comparableValue(nextValue)) {
    return;
  }
  details.push(`${label}: ${formatter(currentValue)} -> ${formatter(nextValue)}`);
}

function formatEntityTypeValue(value) {
  if (!value) {
    return t("common.none");
  }
  return t(`entityType.${value}`);
}

function formatSecretValue(value) {
  return value ? t("common.secretValue") : t("common.public");
}

function formatListValue(value) {
  const items = normalizeStringList(value);
  return items.length ? items.join(", ") : t("common.none");
}

function formatDisplayValue(value) {
  if (Array.isArray(value)) {
    return formatListValue(value);
  }
  if (value === null || value === undefined) {
    return t("common.none");
  }

  const text = String(value).replace(/\s+/g, " ").trim();
  if (!text) {
    return t("common.none");
  }
  if (text.length <= 80) {
    return text;
  }
  return `${text.slice(0, 77).trimEnd()}...`;
}

function comparableValue(value) {
  if (Array.isArray(value)) {
    return JSON.stringify(value.map((item) => comparableValue(item)));
  }
  if (value && typeof value === "object") {
    return JSON.stringify(
      Object.keys(value)
        .sort()
        .reduce((acc, key) => {
          acc[key] = comparableValue(value[key]);
          return acc;
        }, {}),
    );
  }
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

export function renderChat() {
  const log = $("chatLog");
  if (!state.chatMessages.length) {
    log.className = "chat-log empty";
    log.textContent = t("chat.empty");
    return;
  }

  log.className = "chat-log";
  const messagesHtml = state.chatMessages
    .map((message, index) => {
      const isEditing = state.editingChatMessageIndex === index;
      return `
        <div class="message ${message.role}">
          ${
            isEditing
              ? `<div class="message-editor">
                  <textarea id="chatMessageEdit-${index}" rows="6">${escapeHtml(message.content)}</textarea>
                  <div class="message-actions">
                    <button data-save-message-edit="${index}" type="button">${escapeHtml(t("common.save"))}</button>
                    <button class="ghost" data-cancel-message-edit type="button">${escapeHtml(t("common.cancel"))}</button>
                  </div>
                </div>`
              : `<div class="message-content">${renderMarkdown(message.content)}</div>
                <div class="message-actions">
                  ${message.role === "assistant" ? `<button class="ghost" data-save-message="${index}" type="button" title="${escapeHtml(t("chat.saveThisTitle"))}">${escapeHtml(t("chat.saveThis"))}</button>` : ""}
                  <button class="ghost" data-edit-message="${index}" type="button" title="${escapeHtml(t("chat.editMessageTitle"))}">${escapeHtml(t("common.edit"))}</button>
                  <button class="ghost danger" data-delete-message="${index}" type="button" title="${escapeHtml(t("chat.deleteMessageTitle"))}">${escapeHtml(t("common.delete"))}</button>
                </div>`
          }
        </div>
      `;
    })
    .join("");
  const loadingHtml = state.chatBusy
    ? `<div class="message assistant loading">
         <div class="message-content">
           <span class="spinner" aria-hidden="true"></span>
           ${escapeHtml(t("chat.loading"))}
         </div>
       </div>`
    : "";
  log.innerHTML = `${messagesHtml}${loadingHtml}`;
  log.querySelectorAll("[data-save-message]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      await saveAssistantMessageToWiki(Number(button.dataset.saveMessage));
      button.disabled = false;
    });
  });
  log.querySelectorAll("[data-edit-message]").forEach((button) => {
    button.addEventListener("click", () => editChatMessage(Number(button.dataset.editMessage)));
  });
  log.querySelectorAll("[data-delete-message]").forEach((button) => {
    button.addEventListener("click", () => deleteChatMessage(Number(button.dataset.deleteMessage)));
  });
  log.querySelectorAll("[data-save-message-edit]").forEach((button) => {
    button.addEventListener("click", () => saveChatMessageEdit(Number(button.dataset.saveMessageEdit)));
  });
  log.querySelectorAll("[data-cancel-message-edit]").forEach((button) => {
    button.addEventListener("click", cancelChatMessageEdit);
  });
  log.scrollTop = log.scrollHeight;
}

export function renderChatThreads() {
  const list = $("chatThreadList");
  if (!list) return;
  list.innerHTML = state.chatThreads
    .map((thread, index) => {
      const title = thread.title || t("chat.threadUntitled", { number: index + 1 });
      const active = thread.id === state.activeChatThreadId;
      if (state.editingChatThreadId === thread.id) {
        return `
          <div class="chat-thread-item editing">
            <input id="chatThreadEdit-${escapeHtml(thread.id)}" class="chat-thread-edit" type="text" maxlength="80" value="${escapeHtml(title)}" aria-label="${escapeHtml(t("chat.renameThread"))}" />
            <div class="chat-thread-actions">
              <button class="ghost icon-button" data-save-chat-thread-name="${escapeHtml(thread.id)}" type="button" title="${escapeHtml(t("common.save"))}" aria-label="${escapeHtml(t("common.save"))}">&#10003;</button>
              <button class="ghost icon-button" data-cancel-chat-thread-name type="button" title="${escapeHtml(t("common.cancel"))}" aria-label="${escapeHtml(t("common.cancel"))}">&times;</button>
            </div>
          </div>`;
      }
      return `
        <div class="chat-thread-item ${active ? "active" : ""}">
          <button class="chat-thread-main" data-change-chat-thread="${escapeHtml(thread.id)}" type="button">
            <span>${escapeHtml(title)}</span>
            <small>${thread.messages.length} ${escapeHtml(t("chat.messagesCount"))}</small>
          </button>
          <div class="chat-thread-actions">
            <button class="ghost icon-button" data-rename-chat-thread="${escapeHtml(thread.id)}" type="button" title="${escapeHtml(t("chat.renameThread"))}" aria-label="${escapeHtml(t("chat.renameThread"))}">&#9998;</button>
            <button class="ghost danger icon-button" data-delete-chat-thread="${escapeHtml(thread.id)}" type="button" title="${escapeHtml(t("chat.deleteThread"))}" aria-label="${escapeHtml(t("chat.deleteThread"))}">&times;</button>
          </div>
        </div>`;
    })
    .join("");
  list.querySelectorAll("[data-change-chat-thread]").forEach((button) => {
    button.addEventListener("click", () => changeChatThread(button.dataset.changeChatThread));
  });
  list.querySelectorAll("[data-rename-chat-thread]").forEach((button) => {
    button.addEventListener("click", () => renameChatThread(button.dataset.renameChatThread));
  });
  list.querySelectorAll("[data-delete-chat-thread]").forEach((button) => {
    button.addEventListener("click", () => deleteChatThread(button.dataset.deleteChatThread));
  });
  list.querySelectorAll("[data-save-chat-thread-name]").forEach((button) => {
    button.addEventListener("click", () => saveChatThreadRename(button.dataset.saveChatThreadName));
  });
  list.querySelectorAll("[data-cancel-chat-thread-name]").forEach((button) => {
    button.addEventListener("click", cancelChatThreadRename);
  });
  list.querySelectorAll(".chat-thread-edit").forEach((input) => {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") saveChatThreadRename(state.editingChatThreadId);
      if (event.key === "Escape") cancelChatThreadRename();
    });
  });
}

export function renderChatTemplates() {
  const container = $("chatTemplates");
  if (!container) return;
  const moduleVisible = {
    quest: state.moduleSettings.quests !== false,
    map: state.moduleSettings.maps !== false,
    randomTable: state.moduleSettings.randomTables !== false,
    clue: state.moduleSettings.detectiveBoard !== false,
  };
  container.querySelectorAll("[data-chat-template-module]").forEach((button) => {
    button.classList.toggle("hidden", !moduleVisible[button.dataset.chatTemplateModule]);
  });
}
