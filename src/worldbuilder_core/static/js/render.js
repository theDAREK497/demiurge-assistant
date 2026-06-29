import { $, escapeHtml } from "./dom.js";
import { selectedWorld, state } from "./state.js";
import { t } from "./i18n.js";
import { applyProposal, applySelectedProposal, editEntity, rejectProposal, loadWorldData, saveAssistantMessageToWiki } from "./actions.js";

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

export function currentRole() {
  return $("viewerRole").value;
}

export function renderAllWorldData() {
  renderEntities();
  renderRelationshipOptions();
  renderRelationships();
  renderRules();
  renderProposals();
  renderGraph();
  renderTimeline();
  renderModules();
  renderModuleVisibility();
}

export function renderModuleVisibility() {
  const settings = state.moduleSettings;
  const modulePanelVisible = ["journal", "quests", "maps"].some((key) => settings[key] !== false);

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
    panel.classList.toggle("hidden", settings[panel.dataset.modulePanel] === false);
  });

  const activeTab = document.querySelector(".tab.active");
  if (activeTab?.classList.contains("hidden")) {
    activateTab("wiki");
  }
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
  list.innerHTML = state.worlds
    .map(
      (world) => `
        <button class="item ${world.id === state.selectedWorldId ? "active" : ""}" data-world-id="${world.id}" type="button">
          <div class="item-top">
            <span class="item-title">${escapeHtml(world.name)}</span>
          </div>
          <div class="item-meta">${escapeHtml(world.description || t("common.noDescription"))}</div>
        </button>
      `,
    )
    .join("");

  list.querySelectorAll("[data-world-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedWorldId = button.dataset.worldId;
      state.chatMessages = [];
      renderWorlds();
      renderSelectedWorld();
      renderChat();
      await loadWorldData();
    });
  });
}

export function renderSelectedWorld() {
  const world = selectedWorld();
  $("selectedWorldName").textContent = world?.name || t("common.none");
  $("selectedWorldDescription").textContent = world?.description || t("world.selectPrompt");
}

export function renderEntities() {
  const list = $("entityList");
  if (!state.selectedWorldId) {
    list.className = "grid-list empty";
    list.textContent = t("entity.selectWorld");
    return;
  }
  if (!state.entities.length) {
    list.className = "grid-list empty";
    list.textContent = t("entity.empty");
    return;
  }

  list.className = "grid-list";
  list.innerHTML = state.entities
    .map(
      (entity) => `
        <article class="item entity-card">
          ${entity.attributes?.image_url ? `<img class="entity-image" src="${escapeHtml(entity.attributes.image_url)}" alt="" loading="lazy" onerror="this.hidden=true" />` : ""}
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(entity.name)}</div>
              <div class="item-meta">${escapeHtml(t(`entityType.${entity.type}`))} - ${escapeHtml(entity.status)} - ${entity.is_secret ? t("common.secretValue") : t("common.public")}</div>
            </div>
            <span class="badge">${escapeHtml(entity.id.slice(0, 8))}</span>
          </div>
          <div class="item-body">${escapeHtml(entity.summary || entity.description || t("common.noSummary"))}</div>
          ${entity.attributes?.timeline_date ? `<div class="item-meta">${t("entity.timelineDate")}: ${escapeHtml(entity.attributes.timeline_date)}</div>` : ""}
          ${entity.tags?.length ? `<div class="item-meta">${entity.tags.map(escapeHtml).join(", ")}</div>` : ""}
          <div class="item-actions">
            <button class="ghost" data-edit-entity="${entity.id}" type="button">${t("entity.edit")}</button>
          </div>
        </article>
      `,
    )
    .join("");

  list.querySelectorAll("[data-edit-entity]").forEach((button) => {
    button.addEventListener("click", () => editEntity(button.dataset.editEntity));
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

  const width = 960;
  const height = 520;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.36;
  const nodes = state.entities.map((entity, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(state.entities.length, 1) - Math.PI / 2;
    return {
      entity,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
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

  view.className = "graph-view";
  view.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(t("graph.title"))}">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" />
        </marker>
      </defs>
      ${edges
        .map(
          ({ relationship, source, target }) => `
            <line class="graph-edge" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" marker-end="url(#arrow)" />
            <text class="graph-label" x="${(source.x + target.x) / 2}" y="${(source.y + target.y) / 2}">${escapeHtml(relationship.label || relationship.type)}</text>
          `,
        )
        .join("")}
      ${nodes
        .map(
          ({ entity, x, y }) => `
            <g class="graph-node">
              <circle cx="${x}" cy="${y}" r="32" />
              <text x="${x}" y="${y - 4}" text-anchor="middle">${escapeHtml(shortLabel(entity.name))}</text>
              <text class="graph-node-type" x="${x}" y="${y + 12}" text-anchor="middle">${escapeHtml(t(`entityType.${entity.type}`))}</text>
            </g>
          `,
        )
        .join("")}
    </svg>
  `;
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
            <div class="item-body">${escapeHtml(event.summary || event.description || t("common.noSummary"))}</div>
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
  if (!list) return;
  const locations = state.entities.filter((entity) => entity.type === "location");
  renderEntityMiniList(list, locations, t("map.empty"));
}

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
          <div class="item-body">${escapeHtml(entity.summary || entity.description || t("common.noSummary"))}</div>
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

export function renderRelationshipOptions() {
  const options = state.entities
    .map((entity) => `<option value="${entity.id}">${escapeHtml(entity.name)} (${escapeHtml(t(`entityType.${entity.type}`))})</option>`)
    .join("");
  $("relationshipSource").innerHTML = options;
  $("relationshipTarget").innerHTML = options;
}

export function entityName(id) {
  return state.entities.find((entity) => entity.id === id)?.name || id.slice(0, 8);
}

export function renderRelationships() {
  const list = $("relationshipList");
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
          <div class="item-title">${escapeHtml(entityName(relationship.source_entity_id))} -> ${escapeHtml(entityName(relationship.target_entity_id))}</div>
          <div class="item-meta">${escapeHtml(relationship.label || relationship.type)} - ${escapeHtml(relationship.status)} - ${t("relationship.confidence")} ${relationship.confidence}</div>
          ${relationship.description ? `<div class="item-body">${escapeHtml(relationship.description)}</div>` : ""}
        </article>
      `,
    )
    .join("");
}

export function renderRules() {
  const list = $("ruleList");
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
          <div class="item-top">
            <div class="item-title">${t("rule.priority")} ${rule.priority}</div>
            <span class="badge">${rule.is_secret ? t("common.secretValue") : t("common.public")}</span>
          </div>
          <div class="item-body"><strong>${t("rule.if")}:</strong> ${escapeHtml(rule.condition)}\n<strong>${t("rule.then")}:</strong> ${escapeHtml(rule.effect)}</div>
          <div class="item-meta">${escapeHtml(rule.status)}${rule.tags?.length ? ` - ${rule.tags.map(escapeHtml).join(", ")}` : ""}</div>
        </article>
      `,
    )
    .join("");
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
      ].join(" - ");
      return `
        <article class="item">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(proposal.status)}</div>
              <div class="item-meta">${counts} - ${escapeHtml(proposal.id.slice(0, 8))}</div>
            </div>
            <span class="badge">${new Date(proposal.created_at).toLocaleString()}</span>
          </div>
          <div class="item-body">${escapeHtml(proposal.source_text)}</div>
          ${proposal.error ? `<div class="item-body danger">${escapeHtml(proposal.error)}</div>` : ""}
          ${renderProposalReview(proposal)}
          <div class="item-actions">
            <button data-apply-proposal="${proposal.id}" type="button" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.apply")}</button>
            <button data-apply-selected-proposal="${proposal.id}" class="ghost" type="button" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.applySelected")}</button>
            <button data-reject-proposal="${proposal.id}" class="ghost danger" type="button" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.reject")}</button>
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
}

function renderProposalReview(proposal) {
  const disabled = proposal.status !== "pending" ? "disabled" : "";
  const sections = [
    {
      title: t("proposal.entities"),
      kind: "entity",
      items: proposal.payload.entities.map((entity) => `${t(`entityType.${entity.type}`)}: ${entity.name}${entity.summary ? ` - ${entity.summary}` : ""}`),
    },
    {
      title: t("proposal.relationships"),
      kind: "relationship",
      items: proposal.payload.relationships.map((relationship) => `${relationship.source_client_id || relationship.source_entity_id} -> ${relationship.target_client_id || relationship.target_entity_id}: ${relationship.label || relationship.type}`),
    },
    {
      title: t("proposal.rules"),
      kind: "rule",
      items: proposal.payload.world_rules.map((rule) => `${t("rule.if")}: ${rule.condition} ${t("rule.then")}: ${rule.effect}`),
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
                        <span>${escapeHtml(item)}</span>
                      </label>
                    `,
                  )
                  .join("")}
              </div>`
            : "",
        )
        .join("")}
    </div>
  `;
}

export function renderChat() {
  const log = $("chatLog");
  if (!state.chatMessages.length) {
    log.className = "chat-log empty";
    log.textContent = t("chat.empty");
    return;
  }

  log.className = "chat-log";
  log.innerHTML = state.chatMessages
    .map(
      (message, index) => `
        <div class="message ${message.role}">
          <div class="message-content">${escapeHtml(message.content)}</div>
          ${
            message.role === "assistant"
              ? `<div class="message-actions">
                  <button class="ghost" data-save-message="${index}" type="button">${t("chat.saveThis")}</button>
                </div>`
              : ""
          }
        </div>
      `,
    )
    .join("");
  log.querySelectorAll("[data-save-message]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      await saveAssistantMessageToWiki(Number(button.dataset.saveMessage));
      button.disabled = false;
    });
  });
  log.scrollTop = log.scrollHeight;
}
