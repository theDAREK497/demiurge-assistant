import { api } from "./api.js";
import { $, toast } from "./dom.js";
import { t } from "./i18n.js";
import { selectedWorld, state } from "./state.js";
import { activateTab, currentRole, renderAllWorldData, renderChat, renderEntityFormMode, renderLlmConfig, renderSelectedWorld, renderWorlds } from "./render.js";

export function splitTags(value) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

export function requireWorld() {
  if (!state.selectedWorldId) {
    toast(t("common.selectWorldFirst"), "error");
    return false;
  }
  return true;
}

export async function loadHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Health check failed");
    $("apiStatus").textContent = t("status.online");
    $("apiStatus").className = "status-pill ok";
  } catch {
    $("apiStatus").textContent = t("status.offline");
    $("apiStatus").className = "status-pill fail";
  }
}

export async function loadLlmConfig() {
  state.llmConfig = await api("/llm/config");
  renderLlmConfig();
}

export async function saveLlmConfig(event) {
  event.preventDefault();
  const payload = {
    base_url: $("llmBaseUrl").value.trim(),
    default_model: $("llmDefaultModel").value.trim(),
    chat_model: $("llmChatModel").value.trim() || null,
    extractor_model: $("llmExtractorModel").value.trim() || null,
    summarizer_model: $("llmSummarizerModel").value.trim() || null,
    critic_model: $("llmCriticModel").value.trim() || null,
    api_key: $("llmApiKey").value.trim() || null,
    clear_api_key: $("llmClearApiKey").checked,
    timeout_seconds: Number($("llmTimeout").value),
    max_entities_per_extract: Number($("llmMaxExtract").value),
  };
  state.llmConfig = await api("/llm/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  renderLlmConfig();
  toast(t("llm.saved"));
}

export async function testLlmConnection() {
  $("llmTestOutput").textContent = t("llm.testing");
  try {
    const response = await api("/llm/chat", {
      method: "POST",
      body: JSON.stringify({
        messages: [{ role: "user", content: "Reply with one short sentence: Worldbuilder LLM test OK." }],
        temperature: 0.1,
        max_tokens: 80,
      }),
    });
    $("llmTestOutput").textContent = `${t("llm.testOk")}\n${response.model}: ${response.message.content}`;
  } catch (error) {
    $("llmTestOutput").textContent = t("llm.testFailed", { message: error.message });
    toast(t("llm.testFailed", { message: error.message }), "error");
  }
}

export async function loadWorlds() {
  state.worlds = await api("/worlds");
  if (!state.selectedWorldId && state.worlds.length) {
    state.selectedWorldId = state.worlds[0].id;
  }
  if (state.selectedWorldId && !state.worlds.some((world) => world.id === state.selectedWorldId)) {
    state.selectedWorldId = state.worlds[0]?.id || null;
  }
  renderWorlds();
  renderSelectedWorld();
  await loadWorldData();
}

export async function loadWorldData() {
  if (!state.selectedWorldId) {
    state.entities = [];
    state.relationships = [];
    state.rules = [];
    state.proposals = [];
    renderAllWorldData();
    return;
  }

  const role = currentRole();
  const query = $("entitySearch").value.trim();
  const queryPart = query ? `&q=${encodeURIComponent(query)}` : "";
  const [entities, relationships, rules, proposals] = await Promise.all([
    api(`/worlds/${state.selectedWorldId}/entities?role=${role}${queryPart}`),
    api(`/worlds/${state.selectedWorldId}/relationships?role=${role}`),
    api(`/worlds/${state.selectedWorldId}/world-rules?role=${role}&active_only=false`),
    api(`/worlds/${state.selectedWorldId}/proposals`),
  ]);
  state.entities = entities;
  state.relationships = relationships;
  state.rules = rules;
  state.proposals = proposals;
  renderAllWorldData();
}

export async function createWorld(event) {
  event.preventDefault();
  const name = $("worldName").value.trim();
  if (!name) return;

  const world = await api("/worlds", {
    method: "POST",
    body: JSON.stringify({
      name,
      description: $("worldDescription").value.trim() || null,
    }),
  });
  state.selectedWorldId = world.id;
  $("worldForm").reset();
  toast(t("world.created"));
  await loadWorlds();
}

export async function createEntity(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const existing = state.entities.find((entity) => entity.id === state.editingEntityId);
  const attributes = {};
  const imageUrl = $("entityImageUrl").value.trim();
  const timelineDate = $("entityTimelineDate").value.trim();
  if (imageUrl) attributes.image_url = imageUrl;
  if (timelineDate) attributes.timeline_date = timelineDate;
  const mergedAttributes = { ...(existing?.attributes || {}), ...attributes };
  if (!imageUrl) delete mergedAttributes.image_url;
  if (!timelineDate) delete mergedAttributes.timeline_date;

  const payload = {
    type: $("entityType").value,
    name: $("entityName").value.trim(),
    summary: $("entitySummary").value.trim() || null,
    description: $("entityDescription").value.trim() || null,
    tags: splitTags($("entityTags").value),
    is_secret: $("entitySecret").checked,
    attributes: mergedAttributes,
  };

  if (state.editingEntityId) {
    await api(`/entities/${state.editingEntityId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    resetEntityForm();
    toast(t("entity.updated"));
    await loadWorldData();
    return;
  }

  await api(`/worlds/${state.selectedWorldId}/entities`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  resetEntityForm();
  toast(t("entity.created"));
  await loadWorldData();
}

export function editEntity(entityId) {
  const entity = state.entities.find((item) => item.id === entityId);
  if (!entity) return;

  state.editingEntityId = entity.id;
  $("entityType").value = entity.type;
  $("entityName").value = entity.name;
  $("entitySummary").value = entity.summary || "";
  $("entityDescription").value = entity.description || "";
  $("entityImageUrl").value = entity.attributes?.image_url || "";
  $("entityTimelineDate").value = entity.attributes?.timeline_date || "";
  $("entityTags").value = (entity.tags || []).join(", ");
  $("entitySecret").checked = Boolean(entity.is_secret);
  renderEntityFormMode();
  $("entityName").focus();
}

export function resetEntityForm() {
  state.editingEntityId = null;
  $("entityForm").reset();
  renderEntityFormMode();
}

export async function uploadEntityImage() {
  const file = $("entityImageFile").files?.[0];
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/gif", "image/webp"].includes(file.type)) {
    toast(t("asset.unsupportedType"), "error");
    $("entityImageFile").value = "";
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    toast(t("asset.tooLarge"), "error");
    $("entityImageFile").value = "";
    return;
  }

  const contentBase64 = await readFileAsBase64(file);
  const response = await api("/assets", {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      content_base64: contentBase64,
    }),
  });
  $("entityImageUrl").value = response.url;
  $("entityImageFile").value = "";
  toast(t("asset.uploaded"));
}

export async function createRelationship(event) {
  event.preventDefault();
  if (!requireWorld()) return;
  if (!$("relationshipSource").value || !$("relationshipTarget").value) {
    toast(t("relationship.needEntities"), "error");
    return;
  }

  await api(`/worlds/${state.selectedWorldId}/relationships`, {
    method: "POST",
    body: JSON.stringify({
      source_entity_id: $("relationshipSource").value,
      target_entity_id: $("relationshipTarget").value,
      type: $("relationshipType").value.trim(),
      label: $("relationshipLabel").value.trim() || null,
      is_secret: $("relationshipSecret").checked,
    }),
  });
  $("relationshipForm").reset();
  toast(t("relationship.created"));
  await loadWorldData();
}

export async function createRule(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  await api(`/worlds/${state.selectedWorldId}/world-rules`, {
    method: "POST",
    body: JSON.stringify({
      priority: Number($("rulePriority").value),
      condition: $("ruleCondition").value.trim(),
      effect: $("ruleEffect").value.trim(),
      tags: splitTags($("ruleTags").value),
      is_secret: $("ruleSecret").checked,
    }),
  });
  $("ruleForm").reset();
  $("rulePriority").value = "3";
  toast(t("rule.created"));
  await loadWorldData();
}

export async function sendChat(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const content = $("chatInput").value.trim();
  if (!content) return;

  $("chatInput").value = "";
  state.chatMessages.push({ role: "user", content });
  renderChat();

  const submit = event.submitter || $("chatForm").querySelector("button");
  submit.disabled = true;
  try {
    const response = await api(`/worlds/${state.selectedWorldId}/chat`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        save_to_wiki: $("saveToWiki").checked,
        messages: state.chatMessages.map((message) => ({
          role: message.role,
          content: message.content,
        })),
      }),
    });

    state.chatMessages.push(response.completion.message);
    if (response.proposal) {
      toast(t("chat.proposalCreated"));
    }
    if (response.wiki_save_error) {
      toast(t("chat.wikiSaveFailed", { message: response.wiki_save_error }), "error");
    }
    renderChat();
    await loadWorldData();
  } catch (error) {
    toast(t("chat.failed", { message: error.message }), "error");
  } finally {
    submit.disabled = false;
  }
}

export async function saveAssistantMessageToWiki(messageIndex) {
  if (!requireWorld()) return;

  const message = state.chatMessages[messageIndex];
  if (!message || message.role !== "assistant") {
    toast(t("chat.saveMessageFailed", { message: t("common.unexpectedError") }), "error");
    return;
  }

  toast(t("chat.savingMessage"));
  try {
    const proposal = await api(`/worlds/${state.selectedWorldId}/proposals/extract`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        source_text: message.content,
      }),
    });
    state.proposals = [proposal, ...state.proposals.filter((item) => item.id !== proposal.id)];
    renderAllWorldData();
    activateTab("proposals");
    toast(t("chat.savedDraftCreated"));
  } catch (error) {
    toast(t("chat.saveMessageFailed", { message: error.message }), "error");
  }
}

export async function createManualProposal(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  let payload;
  try {
    payload = JSON.parse($("proposalPayload").value);
  } catch (error) {
    toast(t("proposal.invalidJson", { message: error.message }), "error");
    return;
  }

  await api(`/worlds/${state.selectedWorldId}/proposals`, {
    method: "POST",
    body: JSON.stringify({
      source_text: $("proposalSourceText").value.trim(),
      payload,
    }),
  });
  $("manualProposalForm").reset();
  $("proposalPayload").value = '{ "entities": [], "relationships": [], "world_rules": [], "notes": [] }';
  toast(t("proposal.created"));
  await loadWorldData();
}

export async function applyProposal(id) {
  await api(`/proposals/${id}/apply`, { method: "POST" });
  toast(t("proposal.applied"));
  await loadWorldData();
}

export async function applySelectedProposal(id) {
  const checked = (kind) =>
    Array.from(document.querySelectorAll(`[data-proposal-id="${id}"][data-proposal-kind="${kind}"]:checked`)).map((input) =>
      Number(input.dataset.proposalIndex),
    );
  const payload = {
    entity_indices: checked("entity"),
    relationship_indices: checked("relationship"),
    world_rule_indices: checked("rule"),
  };
  const totalSelected = payload.entity_indices.length + payload.relationship_indices.length + payload.world_rule_indices.length;
  if (!totalSelected) {
    toast(t("proposal.selectAtLeastOne"), "error");
    return;
  }
  await api(`/proposals/${id}/apply-selected`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  toast(t("proposal.selectedApplied"));
  await loadWorldData();
}

export async function rejectProposal(id) {
  await api(`/proposals/${id}/reject`, { method: "POST" });
  toast(t("proposal.rejected"));
  await loadWorldData();
}

export async function buildContext() {
  if (!requireWorld()) return;
  const query = $("contextQuery").value.trim();
  const path = `/worlds/${state.selectedWorldId}/context?role=${currentRole()}${query ? `&q=${encodeURIComponent(query)}` : ""}`;
  const context = await api(path);
  $("contextPreview").textContent = context.context_text;
}

export async function exportWorld() {
  if (!requireWorld()) return;
  const snapshot = await api(`/worlds/${state.selectedWorldId}/export`);
  $("exportOutput").value = JSON.stringify(snapshot, null, 2);
  toast(t("backup.exported"));
}

export async function importWorld(event) {
  event.preventDefault();
  let snapshot;
  try {
    snapshot = JSON.parse($("importInput").value);
  } catch (error) {
    toast(t("proposal.invalidJson", { message: error.message }), "error");
    return;
  }
  const replace = $("replaceExisting").checked ? "?replace_existing=true" : "";
  const result = await api(`/worlds/import${replace}`, {
    method: "POST",
    body: JSON.stringify(snapshot),
  });
  state.selectedWorldId = result.world_id;
  toast(t("backup.imported"));
  await loadWorlds();
}

export function rerenderLocalizedState() {
  renderWorlds();
  renderSelectedWorld();
  renderAllWorldData();
  renderLlmConfig();
  renderChat();
  if (!$("contextPreview").textContent.trim()) {
    $("contextPreview").textContent = t("context.empty");
  }
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",").pop() : result);
    });
    reader.addEventListener("error", () => reject(reader.error || new Error("Cannot read file")));
    reader.readAsDataURL(file);
  });
}
