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
  getMapNodes: async (parentId?: string, type?: string) => {
    const params = new URLSearchParams();
    if (currentUniverseId) params.append('universe_id', currentUniverseId);
    if (parentId) params.append('parent_id', parentId);
    if (type) params.append('type', type);
    const res = await fetch(`/api/map-nodes?${params.toString()}`);
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
  }
};
