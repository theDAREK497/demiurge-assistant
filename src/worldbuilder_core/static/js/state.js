export const defaultModuleSettings = {
  graph: true,
  timeline: true,
  journal: true,
  quests: true,
  maps: true,
  randomTables: true,
  detectiveBoard: true,
};

export const state = {
  worlds: [],
  selectedWorldId: null,
  entities: [],
  relationships: [],
  rules: [],
  mapPins: [],
  randomTables: [],
  detectiveNodes: [],
  detectiveConnections: [],
  proposals: [],
  llmConfig: null,
  editingEntityId: null,
  editingRelationshipId: null,
  editingMapPinId: null,
  editingRandomTableId: null,
  editingRandomTableRowId: null,
  editingDetectiveNodeId: null,
  editingDetectiveConnectionId: null,
  selectedEntityId: null,
  selectedReaderType: null,
  selectedReaderSourceId: null,
  activeModuleView: "journal",
  randomTableRolls: {},
  chatMessages: [],
  chatThreads: [],
  activeChatThreadId: null,
  chatStorageScope: null,
  chatBusy: false,
  editingChatMessageIndex: null,
  editingChatThreadId: null,
  moduleSettings: { ...defaultModuleSettings },
  entityTypeFilter: "all",
  graphPositions: {},
  graphPositionScope: null,
};

export function selectedWorld() {
  return state.worlds.find((world) => world.id === state.selectedWorldId) || null;
}

function chatStorageKey(worldId, role) {
  return `worldbuilder.chatThreads.${worldId}.${role}`;
}

function makeChatThread(messages = []) {
  const now = new Date().toISOString();
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    messages: messages.map((message) => ({ role: message.role, content: message.content })),
    createdAt: now,
    updatedAt: now,
  };
}

function deriveChatTitle(messages) {
  const firstUserMessage = messages.find((message) => message.role === "user" && message.content.trim());
  if (!firstUserMessage) return "";
  const normalized = firstUserMessage.content.replace(/\s+/g, " ").trim();
  return normalized.length > 42 ? `${normalized.slice(0, 39)}...` : normalized;
}

function saveChatThreadsForScope() {
  if (!state.chatStorageScope) return;
  localStorage.setItem(state.chatStorageScope, JSON.stringify(state.chatThreads));
}

export function loadChatThreadsForContext(worldId, role) {
  if (!worldId) {
    state.chatThreads = [];
    state.activeChatThreadId = null;
    state.chatMessages = [];
    state.chatStorageScope = null;
    state.editingChatMessageIndex = null;
    state.editingChatThreadId = null;
    return;
  }

  const scope = chatStorageKey(worldId, role);
  state.chatStorageScope = scope;
  try {
    const parsed = JSON.parse(localStorage.getItem(scope) || "[]");
    state.chatThreads = Array.isArray(parsed) ? parsed.filter((thread) => Array.isArray(thread.messages)) : [];
  } catch {
    state.chatThreads = [];
  }

  if (!state.chatThreads.length) {
    state.chatThreads = [makeChatThread()];
  }

  if (!state.chatThreads.some((thread) => thread.id === state.activeChatThreadId)) {
    state.activeChatThreadId = state.chatThreads[0].id;
  }

  const active = activeChatThread();
  state.chatMessages = active ? active.messages.map((message) => ({ ...message })) : [];
  state.editingChatMessageIndex = null;
  state.editingChatThreadId = null;
  saveChatThreadsForScope();
}

export function activeChatThread() {
  return state.chatThreads.find((thread) => thread.id === state.activeChatThreadId) || null;
}

export function persistActiveChatMessages() {
  const thread = activeChatThread();
  if (!thread) return;
  thread.messages = state.chatMessages.map((message) => ({ role: message.role, content: message.content }));
  thread.title = thread.title || deriveChatTitle(thread.messages);
  thread.updatedAt = new Date().toISOString();
  saveChatThreadsForScope();
}

export function createChatThreadFromMessages(messages = []) {
  const thread = makeChatThread(messages);
  thread.title = deriveChatTitle(thread.messages);
  state.chatThreads = [thread, ...state.chatThreads];
  state.activeChatThreadId = thread.id;
  state.chatMessages = thread.messages.map((message) => ({ ...message }));
  state.editingChatMessageIndex = null;
  state.editingChatThreadId = null;
  saveChatThreadsForScope();
  return thread;
}

export function switchChatThread(threadId) {
  const thread = state.chatThreads.find((item) => item.id === threadId);
  if (!thread) return;
  state.activeChatThreadId = thread.id;
  state.chatMessages = thread.messages.map((message) => ({ ...message }));
  state.editingChatMessageIndex = null;
  state.editingChatThreadId = null;
}

export function clearActiveChatThread() {
  state.chatMessages = [];
  persistActiveChatMessages();
}

export function renameChatThread(threadId, title) {
  const thread = state.chatThreads.find((item) => item.id === threadId);
  const nextTitle = String(title || "").replace(/\s+/g, " ").trim().slice(0, 80);
  if (!thread || !nextTitle) return false;
  thread.title = nextTitle;
  thread.updatedAt = new Date().toISOString();
  saveChatThreadsForScope();
  return true;
}

export function deleteChatThread(threadId) {
  const threadIndex = state.chatThreads.findIndex((item) => item.id === threadId);
  if (threadIndex === -1) return false;

  const wasActive = state.activeChatThreadId === threadId;
  state.chatThreads.splice(threadIndex, 1);
  if (!state.chatThreads.length) {
    state.chatThreads.push(makeChatThread());
  }
  if (wasActive || !state.chatThreads.some((thread) => thread.id === state.activeChatThreadId)) {
    state.activeChatThreadId = state.chatThreads[Math.min(threadIndex, state.chatThreads.length - 1)].id;
  }

  const active = activeChatThread();
  state.chatMessages = active ? active.messages.map((message) => ({ ...message })) : [];
  state.editingChatMessageIndex = null;
  state.editingChatThreadId = null;
  saveChatThreadsForScope();
  return true;
}
