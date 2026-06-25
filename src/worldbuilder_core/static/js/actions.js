import { api } from "./api.js";
import { $, toast } from "./dom.js";
import { t } from "./i18n.js";
import { selectedWorld, state } from "./state.js";
import { currentRole, renderAllWorldData, renderChat, renderSelectedWorld, renderWorlds } from "./render.js";

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

  await api(`/worlds/${state.selectedWorldId}/entities`, {
    method: "POST",
    body: JSON.stringify({
      type: $("entityType").value,
      name: $("entityName").value.trim(),
      summary: $("entitySummary").value.trim() || null,
      tags: splitTags($("entityTags").value),
      is_secret: $("entitySecret").checked,
    }),
  });
  $("entityForm").reset();
  toast(t("entity.created"));
  await loadWorldData();
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
  renderChat();
  if (!$("contextPreview").textContent.trim()) {
    $("contextPreview").textContent = t("context.empty");
  }
}
