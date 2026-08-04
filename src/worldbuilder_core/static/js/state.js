export const defaultModuleSettings = {
  graph: true,
  timeline: true,
  journal: true,
  quests: true,
  maps: true,
  randomTables: true,
  detectiveBoard: true,
};

const MAX_CHAT_THREADS = 30;
const MAX_CHAT_MESSAGES_PER_THREAD = 80;
const MAX_CHAT_MESSAGE_CHARS = 20_000;
const MAX_CHAT_STORAGE_CHARS = 2_000_000;

export const state = {
  worlds: [],
  selectedWorldId: null,
  entities: [],
  entityTypes: [],
  questStatuses: [],
  relationships: [],
  relationshipRevisions: [],
  rules: [],
  mapPins: [],
  randomTables: [],
  detectiveNodes: [],
  detectiveConnections: [],
  proposals: [],
  documents: [],
  documentProcessing: {},
  documentExtractionJobs: {},
  embeddingStatus: null,
  embeddingBusy: false,
  embeddingJob: null,
  worldDataLoadedAt: 0,
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
  assistantScenario: "source",
  assistantBusy: false,
  assistantRuns: [],
  assistantStorageScope: null,
  moduleSettings: { ...defaultModuleSettings },
  entityTypeFilter: "all",
  graphPositions: {},
  graphPositionScope: null,
  graphZoom: 1,
};

export function selectedWorld() {
  return state.worlds.find((world) => world.id === state.selectedWorldId) || null;
}

function assistantStorageKey(worldId) {
  return `worldbuilder.assistantRuns.${worldId}`;
}

export function loadAssistantRunsForWorld(worldId) {
  state.assistantStorageScope = worldId ? assistantStorageKey(worldId) : null;
  state.assistantBusy = false;
  if (!state.assistantStorageScope) {
    state.assistantRuns = [];
    return;
  }
  try {
    const stored = JSON.parse(localStorage.getItem(state.assistantStorageScope) || "[]");
    state.assistantRuns = Array.isArray(stored)
      ? stored.slice(0, 20).map((run) => (
          run.status === "running"
            ? { ...run, status: "interrupted", updatedAt: new Date().toISOString() }
            : run
        ))
      : [];
    persistAssistantRuns();
  } catch {
    state.assistantRuns = [];
  }
}

export function addAssistantRun(run) {
  const timestamp = new Date().toISOString();
  const item = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    scenario: run.scenario,
    title: String(run.title || "").slice(0, 160),
    status: run.status || "running",
    result: String(run.result || "").slice(0, 100_000),
    proposalId: run.proposalId || null,
    documentId: run.documentId || null,
    error: null,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  state.assistantRuns = [item, ...state.assistantRuns].slice(0, 20);
  persistAssistantRuns();
  return item;
}

export function updateAssistantRun(runId, changes) {
  const run = state.assistantRuns.find((item) => item.id === runId);
  if (!run) return null;
  Object.assign(run, changes, { updatedAt: new Date().toISOString() });
  persistAssistantRuns();
  return run;
}

export function clearAssistantRuns() {
  state.assistantRuns = [];
  persistAssistantRuns();
}

function persistAssistantRuns() {
  if (!state.assistantStorageScope) return;
  try {
    localStorage.setItem(state.assistantStorageScope, JSON.stringify(state.assistantRuns));
  } catch (error) {
    console.warn("Assistant history could not be persisted", error);
  }
}

function chatStorageKey(worldId, role) {
  return `worldbuilder.chatThreads.${worldId}.${role}`;
}

function makeChatThread(messages = []) {
  const now = new Date().toISOString();
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    messages: compactChatMessages(messages),
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
  state.chatThreads = compactChatThreads(state.chatThreads, state.activeChatThreadId);
  let serialized = JSON.stringify(state.chatThreads);
  while (serialized.length > MAX_CHAT_STORAGE_CHARS && state.chatThreads.length > 1) {
    const removableIndex = state.chatThreads.findLastIndex((thread) => thread.id !== state.activeChatThreadId);
    if (removableIndex < 0) break;
    state.chatThreads.splice(removableIndex, 1);
    serialized = JSON.stringify(state.chatThreads);
  }
  const active = activeChatThread();
  while (serialized.length > MAX_CHAT_STORAGE_CHARS && active?.messages.length > 1) {
    active.messages.shift();
    serialized = JSON.stringify(state.chatThreads);
  }
  try {
    localStorage.setItem(state.chatStorageScope, serialized);
  } catch (error) {
    console.warn("Chat history could not be persisted", error);
  }
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
    state.chatThreads = Array.isArray(parsed)
      ? compactChatThreads(parsed.filter((thread) => Array.isArray(thread.messages)), state.activeChatThreadId)
      : [];
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
  thread.messages = compactChatMessages(state.chatMessages);
  state.chatMessages = thread.messages.map((message) => ({ ...message }));
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

function compactChatMessages(messages) {
  return messages
    .filter((message) => message && (message.role === "user" || message.role === "assistant"))
    .slice(-MAX_CHAT_MESSAGES_PER_THREAD)
    .map((message) => ({
      role: message.role,
      content: String(message.content || "").slice(0, MAX_CHAT_MESSAGE_CHARS),
    }));
}

function compactChatThreads(threads, activeThreadId) {
  const compacted = threads.slice(0, MAX_CHAT_THREADS).map((thread) => ({
    id: String(thread.id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`),
    title: String(thread.title || "").slice(0, 80),
    messages: compactChatMessages(thread.messages || []),
    createdAt: String(thread.createdAt || new Date().toISOString()),
    updatedAt: String(thread.updatedAt || thread.createdAt || new Date().toISOString()),
  }));
  if (activeThreadId && !compacted.some((thread) => thread.id === activeThreadId)) {
    const active = threads.find((thread) => thread.id === activeThreadId);
    if (active) {
      compacted[MAX_CHAT_THREADS - 1] = {
        ...active,
        title: String(active.title || "").slice(0, 80),
        messages: compactChatMessages(active.messages || []),
      };
    }
  }
  return compacted;
}
