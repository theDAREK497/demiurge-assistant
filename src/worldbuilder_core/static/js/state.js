export const defaultModuleSettings = {
  graph: true,
  timeline: true,
  journal: true,
  quests: true,
  maps: true,
};

export const state = {
  worlds: [],
  selectedWorldId: null,
  entities: [],
  relationships: [],
  rules: [],
  proposals: [],
  llmConfig: null,
  editingEntityId: null,
  chatMessages: [],
  moduleSettings: { ...defaultModuleSettings },
};

export function selectedWorld() {
  return state.worlds.find((world) => world.id === state.selectedWorldId) || null;
}
