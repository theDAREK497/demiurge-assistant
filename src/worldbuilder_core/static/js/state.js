export const state = {
  worlds: [],
  selectedWorldId: null,
  entities: [],
  relationships: [],
  rules: [],
  proposals: [],
  llmConfig: null,
  chatMessages: [],
};

export function selectedWorld() {
  return state.worlds.find((world) => world.id === state.selectedWorldId) || null;
}
