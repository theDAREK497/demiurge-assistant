let currentUniverseId: string | null = null;

export const api = {
  setUniverseId: (id: string) => {
    currentUniverseId = id;
  },
  getUniverseId: () => currentUniverseId,
  getUniverses: async () => {
    const res = await fetch('/api/universes');
    return res.json();
  },
  createUniverse: async (name: string, description: string) => {
    const res = await fetch('/api/universes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    });
    return res.json();
  },
  deleteUniverse: async (id: string) => {
    await fetch(`/api/universes/${id}`, { method: 'DELETE' });
  },
  seedUniverse: async () => {
    const res = await fetch('/api/universes/seed', { method: 'POST' });
    return res.json();
  },
  getSettings: async (key: string) => {
    const res = await fetch(`/api/settings/${key}`);
    const data = await res.json();
    return data.value;
  },
  saveSettings: async (key: string, value: string) => {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
  },
  getBacklinks: async (name: string) => {
    if (!currentUniverseId || !name) return { entities: [], quests: [], journals: [] };
    const res = await fetch(`/api/backlinks?universe_id=${currentUniverseId}&name=${encodeURIComponent(name)}`);
    return res.json();
  },
  getEntities: async () => {
    const res = await fetch(`/api/entities?universe_id=${currentUniverseId || ''}`);
    const data = await res.json();
    return data.map((e: any) => {
      let parsedData = {};
      if (e.data) {
        try {
          parsedData = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        } catch (err) {}
      }
      return { ...e, data: parsedData };
    });
  },
  saveEntity: async (entity: any) => {
    const res = await fetch('/api/entities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...entity, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteEntity: async (id: string) => {
    await fetch(`/api/entities/${id}`, { method: 'DELETE' });
  },
  getEvents: async () => {
    const res = await fetch(`/api/events?universe_id=${currentUniverseId || ''}`);
    return res.json();
  },
  saveEvent: async (event: any) => {
    const res = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...event, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteEvent: async (id: string) => {
    await fetch(`/api/events/${id}`, { method: 'DELETE' });
  },
  getJournalLogs: async () => {
    const res = await fetch(`/api/journal-logs?universe_id=${currentUniverseId || ''}`);
    return res.json();
  },
  saveJournalLog: async (log: any) => {
    const res = await fetch('/api/journal-logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...log, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteJournalLog: async (id: string) => {
    await fetch(`/api/journal-logs/${id}`, { method: 'DELETE' });
  },
  getQuests: async () => {
    const res = await fetch(`/api/quests?universe_id=${currentUniverseId || ''}`);
    return res.json();
  },
  saveQuest: async (quest: any) => {
    const res = await fetch('/api/quests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...quest, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteQuest: async (id: string) => {
    await fetch(`/api/quests/${id}`, { method: 'DELETE' });
  },
  getBoards: async () => {
    const res = await fetch(`/api/boards?universe_id=${currentUniverseId || ''}`);
    const data = await res.json();
    return data.map((b: any) => ({ ...b, data: b.data ? JSON.parse(b.data) : null }));
  },
  saveBoard: async (board: any) => {
    const res = await fetch('/api/boards', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...board, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteBoard: async (id: string) => {
    await fetch(`/api/boards/${id}`, { method: 'DELETE' });
  },
  getMapNodes: async (parentId?: string, type?: string) => {
    const params = new URLSearchParams();
    if (currentUniverseId) params.append('universe_id', currentUniverseId);
    if (parentId) params.append('parent_id', parentId);
    if (type) params.append('type', type);
    const res = await fetch(`/api/map-nodes?${params.toString()}`);
    return res.json();
  },
  getMapNode: async (id: string) => {
    const res = await fetch(`/api/map-nodes/${id}`);
    if (!res.ok) return null;
    return res.json();
  },
  saveMapNode: async (node: any) => {
    const res = await fetch('/api/map-nodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...node, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  saveMapNodesBulk: async (nodes: any[]) => {
    const res = await fetch('/api/map-nodes/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  generateImage: async (prompt: string) => {
    const res = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Failed to generate image');
    }
    const data = await res.json();
    return data.url;
  },
  deleteMapNode: async (id: string) => {
    await fetch(`/api/map-nodes/${id}`, { method: 'DELETE' });
  },
  uploadImage: async (file: File) => {
    const formData = new FormData();
    formData.append('image', file);
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      throw new Error('Failed to upload image');
    }
    const data = await res.json();
    return data.url;
  },
  getRandomTables: async () => {
    const res = await fetch(`/api/random-tables?universe_id=${currentUniverseId || ''}`);
    return res.json();
  },
  saveRandomTable: async (table: any) => {
    await fetch('/api/random-tables', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...table, universe_id: currentUniverseId }),
    });
  },
  deleteRandomTable: async (id: string) => {
    await fetch(`/api/random-tables/${id}`, { method: 'DELETE' });
  },
  chat: async (messages: {role: string, content: string}[]) => {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, universe_id: currentUniverseId }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || 'Failed to chat');
    }
    const data = await res.json();
    return data.reply;
  },
  extractEntities: async (text: string) => {
    const res = await fetch('/api/extract-entities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, universe_id: currentUniverseId }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || 'Failed to extract entities');
    }
    return res.json();
  },
  getChatSessions: async () => {
    const res = await fetch(`/api/chat-sessions?universe_id=${currentUniverseId || ''}`);
    return res.json();
  },
  getChatSession: async (id: string) => {
    const res = await fetch(`/api/chat-sessions/${id}`);
    if (!res.ok) return null;
    return res.json();
  },
  saveChatSession: async (session: any) => {
    const res = await fetch('/api/chat-sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...session, universe_id: currentUniverseId }),
    });
    return res.json();
  },
  deleteChatSession: async (id: string) => {
    await fetch(`/api/chat-sessions/${id}`, { method: 'DELETE' });
  }
};
