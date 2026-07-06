import { api } from "./api.js";
import { $, toast } from "./dom.js";
import { language, t } from "./i18n.js";
import { selectedWorld, state } from "./state.js";
import {
  activateTab,
  closeEntityDrawer,
  currentRole,
  openEntityDrawer,
  renderAllWorldData,
  renderChat,
  renderDetectiveConnectionFormMode,
  renderDetectiveNodeFormMode,
  renderEntityFormMode,
  renderLlmConfig,
  renderMapPinFormMode,
  renderRandomTableFormMode,
  renderRandomTableRowFormMode,
  renderSelectedWorld,
  renderWorlds,
} from "./render.js";

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

function setDisclosureOpen(id, isOpen) {
  const disclosure = $(id);
  if (disclosure?.tagName === "DETAILS") {
    disclosure.open = Boolean(isOpen);
  }
}

function normalizeStaticControlLabels() {
  const languageSelect = $("languageSelect");
  if (languageSelect?.options?.[0]) {
    languageSelect.options[0].textContent = "\u0420\u0443\u0441\u0441\u043a\u0438\u0439";
    return;
    languageSelect.options[0].textContent = "\u0420\u0443\u0441\u0441\u043a\u0438\u0439";
    languageSelect.options[0].textContent = "Русский";
  }
}

function isSupportedEntityType(value) {
  return ["character", "location", "faction", "item", "event", "clue", "concept"].includes(value);
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
    state.selectedEntityId = null;
    state.selectedReaderType = null;
    state.selectedReaderSourceId = null;
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
    state.mapPins = [];
    state.randomTables = [];
    state.detectiveNodes = [];
    state.detectiveConnections = [];
    state.proposals = [];
    state.selectedEntityId = null;
    state.selectedReaderType = null;
    state.selectedReaderSourceId = null;
    renderAllWorldData();
    return;
  }

  const role = currentRole();
  const query = $("entitySearch").value.trim();
  const queryPart = query ? `&q=${encodeURIComponent(query)}` : "";
  const [entities, relationships, rules, mapPins, randomTables, detectiveBoard, proposals] = await Promise.all([
    api(`/worlds/${state.selectedWorldId}/entities?role=${role}${queryPart}`),
    api(`/worlds/${state.selectedWorldId}/relationships?role=${role}`),
    api(`/worlds/${state.selectedWorldId}/world-rules?role=${role}&active_only=false`),
    api(`/worlds/${state.selectedWorldId}/map-pins?role=${role}`),
    api(`/worlds/${state.selectedWorldId}/random-tables?role=${role}`),
    api(`/worlds/${state.selectedWorldId}/detective-board?role=${role}`),
    api(`/worlds/${state.selectedWorldId}/proposals`),
  ]);
  state.entities = entities;
  state.relationships = relationships;
  state.rules = rules;
  state.mapPins = mapPins;
  state.randomTables = randomTables;
  state.detectiveNodes = detectiveBoard.nodes;
  state.detectiveConnections = detectiveBoard.connections;
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
    closeEntityDrawer();
    toast(t("entity.updated"));
    await loadWorldData();
    return;
  }

  await api(`/worlds/${state.selectedWorldId}/entities`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  resetEntityForm();
  closeEntityDrawer();
  toast(t("entity.created"));
  await loadWorldData();
}

export function startCreateEntity() {
  startCreateEntityWithType();
}

export function startCreateEntityWithType(entityType = "") {
  resetEntityForm({ keepDrawerOpen: true });
  if (entityType && isSupportedEntityType(entityType)) {
    $("entityType").value = entityType;
  }
  openEntityDrawer();
  $("entityName").focus();
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
  openEntityDrawer();
  $("entityName").focus();
}

export function resetEntityForm(options = {}) {
  state.editingEntityId = null;
  $("entityForm").reset();
  renderEntityFormMode();
  if (!options.keepDrawerOpen) {
    closeEntityDrawer();
  }
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

export async function saveMapPin(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const payload = {
    map_entity_id: $("mapPinMapEntity").value,
    linked_entity_id: $("mapPinLinkedEntity").value || null,
    title: $("mapPinTitle").value.trim(),
    note: $("mapPinNote").value.trim() || null,
    x: clampPercent($("mapPinX").value),
    y: clampPercent($("mapPinY").value),
    is_secret: $("mapPinSecret").checked,
  };
  if (!payload.map_entity_id) {
    toast(t("map.needMap"), "error");
    return;
  }
  if (!payload.title) {
    toast(t("map.needTitle"), "error");
    return;
  }

  if (state.editingMapPinId) {
    await api(`/map-pins/${state.editingMapPinId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("map.pinUpdated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/map-pins`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("map.pinCreated"));
  }
  resetMapPinForm();
  await loadWorldData();
}

export function editMapPin(pinId) {
  const pin = state.mapPins.find((item) => item.id === pinId);
  if (!pin) return;

  state.editingMapPinId = pin.id;
  $("mapPinMapEntity").value = pin.map_entity_id;
  $("mapPinLinkedEntity").value = pin.linked_entity_id || "";
  $("mapPinTitle").value = pin.title;
  $("mapPinNote").value = pin.note || "";
  $("mapPinX").value = Math.round(pin.x * 1000) / 10;
  $("mapPinY").value = Math.round(pin.y * 1000) / 10;
  $("mapPinSecret").checked = Boolean(pin.is_secret);
  setDisclosureOpen("mapPinEditor", true);
  renderMapPinFormMode();
  $("mapPinTitle").focus();
}

export async function deleteMapPin(pinId) {
  await api(`/map-pins/${pinId}`, { method: "DELETE" });
  if (state.editingMapPinId === pinId) {
    resetMapPinForm();
  }
  toast(t("map.pinDeleted"));
  await loadWorldData();
}

export function resetMapPinForm() {
  state.editingMapPinId = null;
  $("mapPinForm").reset();
  $("mapPinX").value = "50";
  $("mapPinY").value = "50";
  setDisclosureOpen("mapPinEditor", false);
  renderMapPinFormMode();
}

export function setMapPinDraft(mapEntityId, x, y) {
  $("mapPinMapEntity").value = mapEntityId;
  $("mapPinX").value = Math.round(x * 1000) / 10;
  $("mapPinY").value = Math.round(y * 1000) / 10;
  setDisclosureOpen("mapPinEditor", true);
  $("mapPinTitle").focus();
}

export function openMapPinEditor() {
  setDisclosureOpen("mapPinEditor", true);
  $("mapPinTitle").focus();
}

export async function saveRandomTable(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const payload = {
    name: $("randomTableName").value.trim(),
    description: $("randomTableDescription").value.trim() || null,
    is_secret: $("randomTableSecret").checked,
  };
  if (!payload.name) return;

  if (state.editingRandomTableId) {
    await api(`/random-tables/${state.editingRandomTableId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("randomTable.updated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/random-tables`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("randomTable.created"));
  }
  resetRandomTableForm();
  await loadWorldData();
}

export function editRandomTable(tableId) {
  const table = state.randomTables.find((item) => item.id === tableId);
  if (!table) return;

  state.editingRandomTableId = table.id;
  $("randomTableName").value = table.name;
  $("randomTableDescription").value = table.description || "";
  $("randomTableSecret").checked = Boolean(table.is_secret);
  setDisclosureOpen("randomTableEditor", true);
  renderRandomTableFormMode();
  $("randomTableName").focus();
}

export async function deleteRandomTable(tableId) {
  await api(`/random-tables/${tableId}`, { method: "DELETE" });
  if (state.editingRandomTableId === tableId) {
    resetRandomTableForm();
  }
  if ($("randomTableRowTable").value === tableId) {
    resetRandomTableRowForm();
  }
  delete state.randomTableRolls[tableId];
  toast(t("randomTable.deleted"));
  await loadWorldData();
}

export function resetRandomTableForm() {
  state.editingRandomTableId = null;
  $("randomTableForm").reset();
  setDisclosureOpen("randomTableEditor", false);
  renderRandomTableFormMode();
}

export async function saveRandomTableRow(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const tableId = $("randomTableRowTable").value;
  if (!tableId) {
    toast(t("randomTable.needTable"), "error");
    return;
  }
  const payload = {
    label: $("randomTableRowLabel").value.trim() || null,
    result: $("randomTableRowResult").value.trim(),
    weight: Number($("randomTableRowWeight").value),
    is_secret: $("randomTableRowSecret").checked,
  };
  if (!payload.result) return;

  if (state.editingRandomTableRowId) {
    await api(`/random-table-rows/${state.editingRandomTableRowId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("randomTable.rowUpdated"));
  } else {
    await api(`/random-tables/${tableId}/rows`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("randomTable.rowCreated"));
  }
  resetRandomTableRowForm();
  await loadWorldData();
}

export function editRandomTableRow(tableId, rowId) {
  const table = state.randomTables.find((item) => item.id === tableId);
  const row = table?.rows.find((item) => item.id === rowId);
  if (!row) return;

  state.editingRandomTableRowId = row.id;
  $("randomTableRowTable").value = tableId;
  $("randomTableRowLabel").value = row.label || "";
  $("randomTableRowResult").value = row.result;
  $("randomTableRowWeight").value = row.weight;
  $("randomTableRowSecret").checked = Boolean(row.is_secret);
  setDisclosureOpen("randomTableRowEditor", true);
  renderRandomTableRowFormMode();
  $("randomTableRowResult").focus();
}

export async function deleteRandomTableRow(rowId) {
  await api(`/random-table-rows/${rowId}`, { method: "DELETE" });
  if (state.editingRandomTableRowId === rowId) {
    resetRandomTableRowForm();
  }
  toast(t("randomTable.rowDeleted"));
  await loadWorldData();
}

export function resetRandomTableRowForm() {
  state.editingRandomTableRowId = null;
  $("randomTableRowForm").reset();
  $("randomTableRowWeight").value = "1";
  setDisclosureOpen("randomTableRowEditor", false);
  renderRandomTableRowFormMode();
}

export async function rollRandomTable(tableId) {
  const response = await api(`/random-tables/${tableId}/roll?role=${currentRole()}`, { method: "POST" });
  state.randomTableRolls[tableId] = response.row;
  renderAllWorldData();
}

export async function saveDetectiveNode(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const payload = {
    entity_id: $("detectiveNodeEntity").value || null,
    title: $("detectiveNodeTitle").value.trim(),
    note: $("detectiveNodeNote").value.trim() || null,
    evidence_url: $("detectiveNodeEvidenceUrl").value.trim() || null,
    x: clampPercent($("detectiveNodeX").value),
    y: clampPercent($("detectiveNodeY").value),
    is_secret: $("detectiveNodeSecret").checked,
  };
  if (!payload.title) return;

  if (state.editingDetectiveNodeId) {
    await api(`/detective-board/nodes/${state.editingDetectiveNodeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("detective.nodeUpdated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/detective-board/nodes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("detective.nodeCreated"));
  }
  resetDetectiveNodeForm();
  await loadWorldData();
}

export function editDetectiveNode(nodeId) {
  const node = state.detectiveNodes.find((item) => item.id === nodeId);
  if (!node) return;

  state.editingDetectiveNodeId = node.id;
  $("detectiveNodeEntity").value = node.entity_id || "";
  $("detectiveNodeTitle").value = node.title;
  $("detectiveNodeNote").value = node.note || "";
  $("detectiveNodeEvidenceUrl").value = node.evidence_url || "";
  $("detectiveNodeX").value = Math.round(node.x * 1000) / 10;
  $("detectiveNodeY").value = Math.round(node.y * 1000) / 10;
  $("detectiveNodeSecret").checked = Boolean(node.is_secret);
  setDisclosureOpen("detectiveNodeEditor", true);
  renderDetectiveNodeFormMode();
  $("detectiveNodeTitle").focus();
}

export async function deleteDetectiveNode(nodeId) {
  await api(`/detective-board/nodes/${nodeId}`, { method: "DELETE" });
  if (state.editingDetectiveNodeId === nodeId) {
    resetDetectiveNodeForm();
  }
  toast(t("detective.nodeDeleted"));
  await loadWorldData();
}

export async function persistDetectiveNodePosition(nodeId, x, y) {
  const payload = {
    x: clampUnit(x),
    y: clampUnit(y),
  };
  const node = await api(`/detective-board/nodes/${nodeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  const index = state.detectiveNodes.findIndex((item) => item.id === nodeId);
  if (index >= 0) {
    state.detectiveNodes[index] = node;
  }
  if (state.editingDetectiveNodeId === nodeId) {
    $("detectiveNodeX").value = Math.round(payload.x * 1000) / 10;
    $("detectiveNodeY").value = Math.round(payload.y * 1000) / 10;
  }
  renderAllWorldData();
}

export function resetDetectiveNodeForm() {
  state.editingDetectiveNodeId = null;
  $("detectiveNodeForm").reset();
  $("detectiveNodeX").value = "50";
  $("detectiveNodeY").value = "50";
  setDisclosureOpen("detectiveNodeEditor", false);
  renderDetectiveNodeFormMode();
}

export function setDetectiveNodeDraft(x, y) {
  $("detectiveNodeX").value = Math.round(x * 1000) / 10;
  $("detectiveNodeY").value = Math.round(y * 1000) / 10;
  setDisclosureOpen("detectiveNodeEditor", true);
  $("detectiveNodeTitle").focus();
}

export function openDetectiveNodeEditor() {
  setDisclosureOpen("detectiveNodeEditor", true);
  $("detectiveNodeTitle").focus();
}

export async function saveDetectiveConnection(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const payload = {
    source_node_id: $("detectiveConnectionSource").value,
    target_node_id: $("detectiveConnectionTarget").value,
    label: $("detectiveConnectionLabel").value.trim() || null,
    note: $("detectiveConnectionNote").value.trim() || null,
    is_secret: $("detectiveConnectionSecret").checked,
  };
  if (!payload.source_node_id || !payload.target_node_id || payload.source_node_id === payload.target_node_id) {
    toast(t("detective.needNodes"), "error");
    return;
  }

  if (state.editingDetectiveConnectionId) {
    await api(`/detective-board/connections/${state.editingDetectiveConnectionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("detective.connectionUpdated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/detective-board/connections`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("detective.connectionCreated"));
  }
  resetDetectiveConnectionForm();
  await loadWorldData();
}

export function editDetectiveConnection(connectionId) {
  const connection = state.detectiveConnections.find((item) => item.id === connectionId);
  if (!connection) return;

  state.editingDetectiveConnectionId = connection.id;
  $("detectiveConnectionSource").value = connection.source_node_id;
  $("detectiveConnectionTarget").value = connection.target_node_id;
  $("detectiveConnectionLabel").value = connection.label || "";
  $("detectiveConnectionNote").value = connection.note || "";
  $("detectiveConnectionSecret").checked = Boolean(connection.is_secret);
  setDisclosureOpen("detectiveConnectionEditor", true);
  renderDetectiveConnectionFormMode();
  $("detectiveConnectionLabel").focus();
}

export async function deleteDetectiveConnection(connectionId) {
  await api(`/detective-board/connections/${connectionId}`, { method: "DELETE" });
  if (state.editingDetectiveConnectionId === connectionId) {
    resetDetectiveConnectionForm();
  }
  toast(t("detective.connectionDeleted"));
  await loadWorldData();
}

export function resetDetectiveConnectionForm() {
  state.editingDetectiveConnectionId = null;
  $("detectiveConnectionForm").reset();
  setDisclosureOpen("detectiveConnectionEditor", false);
  renderDetectiveConnectionFormMode();
}

export function openDetectiveConnectionEditor() {
  setDisclosureOpen("detectiveConnectionEditor", true);
  $("detectiveConnectionLabel").focus();
}

export async function sendChat(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const content = $("chatInput").value.trim();
  if (!content) return;

  $("chatInput").value = "";
  state.chatMessages.push({ role: "user", content });
  state.chatBusy = true;
  renderChat();

  const submit = event.submitter || $("chatForm").querySelector("button");
  submit.disabled = true;
  $("chatInput").disabled = true;
  try {
    const response = await api(`/worlds/${state.selectedWorldId}/chat`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        output_language: language(),
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
    state.chatBusy = false;
    submit.disabled = false;
    $("chatInput").disabled = false;
    renderChat();
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
        output_language: language(),
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
  $("proposalPayload").value = '{ "entities": [], "relationships": [], "world_rules": [], "random_table_rows": [], "notes": [] }';
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
    random_table_row_indices: checked("random-table-row"),
  };
  const totalSelected =
    payload.entity_indices.length +
    payload.relationship_indices.length +
    payload.world_rule_indices.length +
    payload.random_table_row_indices.length;
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
  normalizeStaticControlLabels();
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

function clampPercent(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return 0.5;
  return Math.min(1, Math.max(0, number / 100));
}

function clampUnit(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return 0.5;
  return Math.min(1, Math.max(0, number));
}
