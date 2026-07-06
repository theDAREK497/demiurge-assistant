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
  chatBusy: false,
  moduleSettings: { ...defaultModuleSettings },
};

export function selectedWorld() {
  return state.worlds.find((world) => world.id === state.selectedWorldId) || null;
}
