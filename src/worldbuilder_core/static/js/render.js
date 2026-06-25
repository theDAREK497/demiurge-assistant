import { $, escapeHtml } from "./dom.js";
import { selectedWorld, state } from "./state.js";
import { t } from "./i18n.js";
import { applyProposal, rejectProposal, loadWorldData } from "./actions.js";

export function currentRole() {
  return $("viewerRole").value;
}

export function renderAllWorldData() {
  renderEntities();
  renderRelationshipOptions();
  renderRelationships();
  renderRules();
  renderProposals();
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
        <article class="item">
          <div class="item-top">
            <div>
              <div class="item-title">${escapeHtml(entity.name)}</div>
              <div class="item-meta">${escapeHtml(t(`entityType.${entity.type}`))} - ${escapeHtml(entity.status)} - ${entity.is_secret ? t("common.secretValue") : t("common.public")}</div>
            </div>
            <span class="badge">${escapeHtml(entity.id.slice(0, 8))}</span>
          </div>
          <div class="item-body">${escapeHtml(entity.summary || entity.description || t("common.noSummary"))}</div>
          ${entity.tags?.length ? `<div class="item-meta">${entity.tags.map(escapeHtml).join(", ")}</div>` : ""}
        </article>
      `,
    )
    .join("");
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
          <div class="item-actions">
            <button data-apply-proposal="${proposal.id}" type="button" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.apply")}</button>
            <button data-reject-proposal="${proposal.id}" class="ghost danger" type="button" ${proposal.status !== "pending" ? "disabled" : ""}>${t("proposal.reject")}</button>
          </div>
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("[data-apply-proposal]").forEach((button) => {
    button.addEventListener("click", () => applyProposal(button.dataset.applyProposal));
  });
  list.querySelectorAll("[data-reject-proposal]").forEach((button) => {
    button.addEventListener("click", () => rejectProposal(button.dataset.rejectProposal));
  });
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
    .map((message) => `<div class="message ${message.role}">${escapeHtml(message.content)}</div>`)
    .join("");
  log.scrollTop = log.scrollHeight;
}
