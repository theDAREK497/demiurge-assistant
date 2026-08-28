import { api, apiRaw } from "./api.js?v=20260826.4";
import { $, toast } from "./dom.js?v=20260826.4";
import { language, t } from "./i18n.js?v=20260826.4";
import {
  addAssistantRun,
  clearAssistantRuns as clearStoredAssistantRuns,
  createChatThreadFromMessages,
  deleteChatThread as deleteStoredChatThread,
  loadAssistantRunsForWorld,
  loadChatThreadsForContext,
  persistActiveChatMessages,
  renameChatThread as renameStoredChatThread,
  selectedWorld,
  state,
  switchChatThread,
  updateAssistantRun,
} from "./state.js?v=20260826.4";
import {
  activateTab,
  closeProposalEditor,
  closeEntityDrawer,
  closeEntityReader,
  currentRole,
  openEntityDrawer,
  renderAllWorldData,
  renderAssistant,
  renderChat,
  renderChatThreads,
  renderDetectiveConnectionFormMode,
  renderDetectiveNodeFormMode,
  renderEntityFormMode,
  renderEntityMergeResolver,
  renderExperience,
  renderLlmConfig,
  renderDocuments,
  renderMapPinFormMode,
  renderRelationshipFormMode,
  renderRandomTableFormMode,
  renderRandomTableRowFormMode,
  renderSelectedWorld,
  renderWorlds,
} from "./render.js?v=20260826.4";

const CHAT_CONTEXT_MESSAGE_LIMIT = 12;
let worldDataAbortController = null;
const documentExtractionPolling = {};
let embeddingOperation = 0;

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
  }
}

function isSupportedEntityType(value) {
  return state.entityTypes.some((definition) => definition.key === value);
}

export async function loadHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Health check failed");
    const health = await response.json();
    $("apiStatus").textContent = t("status.online");
    $("apiStatus").className = "status-pill ok";
    $("apiStatus").title = health.local_worker_enabled
      ? t("status.localWorkerActive")
      : t("status.externalWorker");
  } catch {
    $("apiStatus").textContent = t("status.offline");
    $("apiStatus").className = "status-pill fail";
    $("apiStatus").title = "";
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
    embedding_model: $("llmEmbeddingModel").value.trim() || null,
    api_key: $("llmApiKey").value.trim() || null,
    clear_api_key: $("llmClearApiKey").checked,
    timeout_seconds: Number($("llmTimeout").value),
    max_entities_per_extract: Number($("llmMaxExtract").value),
  };
  state.llmConfig = await api("/llm/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  if (state.selectedWorldId) {
    state.embeddingStatus = await api(`/worlds/${state.selectedWorldId}/embedding-status`);
    renderDocuments();
    await refreshWorldDataQuietly();
  }
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
  worldDataAbortController?.abort();
  worldDataAbortController = new AbortController();
  const { signal } = worldDataAbortController;
  if (!state.selectedWorldId) {
    state.entities = [];
    state.entityTypes = [];
    state.questStatuses = [];
    state.relationships = [];
    state.relationshipRevisions = [];
    state.rules = [];
    state.mapPins = [];
    state.randomTables = [];
    state.detectiveNodes = [];
    state.detectiveConnections = [];
    state.proposals = [];
    state.documents = [];
    state.worldChanges = [];
    state.documentExtractionJobs = {};
    state.embeddingStatus = null;
    state.worldDataLoadedAt = Date.now();
    state.selectedEntityId = null;
    state.selectedReaderType = null;
    state.selectedReaderSourceId = null;
    loadChatThreadsForContext(null, currentRole());
    loadAssistantRunsForWorld(null);
    renderAllWorldData();
    return;
  }

  const worldId = state.selectedWorldId;
  const role = currentRole();
  const query = $("entitySearch").value.trim();
  const queryPart = query ? `&q=${encodeURIComponent(query)}` : "";
  let results;
  try {
    results = await Promise.all([
      api(`/worlds/${worldId}/entities?role=${role}${queryPart}`, { signal }),
      api(`/worlds/${worldId}/relationships?role=${role}`, { signal }),
      role === "master"
        ? api(`/worlds/${worldId}/relationship-revisions`, { signal })
        : Promise.resolve([]),
      api(`/worlds/${worldId}/world-rules?role=${role}&active_only=false`, { signal }),
      api(`/worlds/${worldId}/map-pins?role=${role}`, { signal }),
      api(`/worlds/${worldId}/random-tables?role=${role}`, { signal }),
      api(`/worlds/${worldId}/detective-board?role=${role}`, { signal }),
      api(`/worlds/${worldId}/entity-types?role=${role}`, { signal }),
      api(`/worlds/${worldId}/quest-statuses?role=${role}`, { signal }),
      role === "master" ? api(`/worlds/${worldId}/proposals`, { signal }) : Promise.resolve([]),
      role === "master" ? api(`/worlds/${worldId}/documents`, { signal }) : Promise.resolve([]),
      role === "master"
        ? api(`/worlds/${worldId}/document-extraction-jobs`, { signal })
        : Promise.resolve([]),
      role === "master" ? api(`/worlds/${worldId}/embedding-status`, { signal }) : Promise.resolve(null),
      role === "master" && !state.llmConfig ? api("/llm/config", { signal }) : Promise.resolve(null),
      role === "master" ? api(`/worlds/${worldId}/changes?limit=200`, { signal }) : Promise.resolve([]),
    ]);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
  if (signal.aborted || state.selectedWorldId !== worldId || currentRole() !== role) return;
  const [
    entities,
    relationships,
    relationshipRevisions,
    rules,
    mapPins,
    randomTables,
    detectiveBoard,
    entityTypes,
    questStatuses,
    proposals,
    documents,
    extractionJobs,
    embeddingStatus,
    llmConfig,
    worldChanges,
  ] = results;
  let consolidatedProposals = proposals;
  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending");
  if (role === "master" && pendingProposals.length > 1) {
    const activeProposal = await api(`/worlds/${worldId}/proposals/consolidate`, {
      method: "POST",
      signal,
    });
    consolidatedProposals = [
      ...(activeProposal ? [activeProposal] : []),
      ...proposals.filter((proposal) => proposal.status !== "pending"),
    ];
    toast(t("proposal.consolidated", { count: pendingProposals.length }));
  }
  state.entities = entities;
  state.relationships = relationships;
  state.relationshipRevisions = relationshipRevisions;
  state.rules = rules;
  state.mapPins = mapPins;
  state.randomTables = randomTables;
  state.detectiveNodes = detectiveBoard.nodes;
  state.detectiveConnections = detectiveBoard.connections;
  state.entityTypes = entityTypes;
  state.questStatuses = questStatuses;
  state.proposals = consolidatedProposals;
  state.documents = documents;
  state.worldChanges = worldChanges;
  state.documentExtractionJobs = Object.fromEntries(
    extractionJobs.map((job) => [job.document_id, job]).reverse(),
  );
  state.embeddingStatus = embeddingStatus;
  state.worldDataLoadedAt = Date.now();
  if (llmConfig) {
    state.llmConfig = llmConfig;
    renderLlmConfig();
  }
  loadChatThreadsForContext(state.selectedWorldId, role);
  loadAssistantRunsForWorld(state.selectedWorldId);
  reconcileAssistantSourceRuns();
  renderAllWorldData();
  extractionJobs
    .filter((job) => ["queued", "running"].includes(job.status))
    .forEach((job) => monitorDocumentExtraction(job));
}

export async function uploadKnowledgeDocument(event) {
  event.preventDefault();
  if (!requireWorld()) return;
  const input = $("documentFile");
  const file = input.files?.[0];
  if (!file) {
    toast(t("documents.chooseFile"), "error");
    return;
  }
  const params = new URLSearchParams({
    filename: file.name,
    is_secret: String($("documentSecret").checked),
  });
  const document = await apiRaw(`/worlds/${state.selectedWorldId}/documents?${params}`, {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  state.documents.unshift(document);
  input.value = "";
  renderDocuments();
  toast(t("documents.uploaded"));
  await processKnowledgeDocument(document.id);
}

export async function processKnowledgeDocument(documentId) {
  const worldId = state.selectedWorldId;
  state.documentProcessing[documentId] = true;
  renderDocuments();
  try {
    while (state.selectedWorldId === worldId && state.documentProcessing[documentId]) {
      const result = await api(`/documents/${documentId}/process?batch_size=100`, { method: "POST" });
      replaceDocument(result.document);
      renderDocuments();
      if (result.document.status === "ready" || result.processed_in_batch === 0) break;
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    }
  } finally {
    delete state.documentProcessing[documentId];
    renderDocuments();
    await refreshWorldDataQuietly(worldId);
  }
}

export async function pauseKnowledgeDocument(documentId) {
  state.documentProcessing[documentId] = false;
  replaceDocument(await api(`/documents/${documentId}/pause`, { method: "POST" }));
  renderDocuments();
  await refreshWorldDataQuietly();
}

export async function resumeKnowledgeDocument(documentId) {
  replaceDocument(await api(`/documents/${documentId}/resume`, { method: "POST" }));
  renderDocuments();
  await processKnowledgeDocument(documentId);
}

export async function deleteKnowledgeDocument(documentId) {
  const document = state.documents.find((item) => item.id === documentId);
  if (!document || !window.confirm(t("documents.deleteConfirm", { name: document.filename }))) return;
  state.documentProcessing[documentId] = false;
  await api(`/documents/${documentId}`, { method: "DELETE" });
  state.documents = state.documents.filter((item) => item.id !== documentId);
  delete state.documentExtractionJobs[documentId];
  renderDocuments();
  await refreshWorldDataQuietly();
}

export async function extractKnowledgeDocument(documentId) {
  if (!requireWorld()) return;
  const job = await api(
    `/documents/${documentId}/extract?output_language=${encodeURIComponent(language())}`,
    { method: "POST" },
  );
  state.documentExtractionJobs[documentId] = job;
  renderDocuments();
  toast(t("documents.extractionQueued"));
  await monitorDocumentExtraction(job);
}

export async function pauseDocumentExtraction(jobId) {
  const job = await api(`/document-extraction-jobs/${jobId}/pause`, { method: "POST" });
  state.documentExtractionJobs[job.document_id] = job;
  renderDocuments();
  renderAssistant();
  toast(t("documents.extractionPaused"));
}

export async function resumeDocumentExtraction(jobId) {
  const job = await api(`/document-extraction-jobs/${jobId}/resume`, { method: "POST" });
  state.documentExtractionJobs[job.document_id] = job;
  renderDocuments();
  renderAssistant();
  toast(t("documents.extractionResumed"));
  await monitorDocumentExtraction(job);
}

async function monitorDocumentExtraction(initialJob) {
  if (documentExtractionPolling[initialJob.id]) return documentExtractionPolling[initialJob.id];
  const worldId = state.selectedWorldId;
  documentExtractionPolling[initialJob.id] = (async () => {
    let job = initialJob;
    while (
      state.selectedWorldId === worldId &&
      ["queued", "running"].includes(job.status)
    ) {
      await new Promise((resolve) => window.setTimeout(resolve, documentExtractionPollDelay(job)));
      job = await api(`/document-extraction-jobs/${job.id}`);
      state.documentExtractionJobs[job.document_id] = job;
      reconcileAssistantSourceRuns();
      renderDocuments();
      renderAssistant();
    }
    if (state.selectedWorldId !== worldId) return;
    if (job.status === "completed") {
      await refreshWorldDataQuietly(worldId);
      toast(t("documents.extractionReady", { count: job.proposal_count }));
    } else if (job.status === "failed") {
      await refreshWorldDataQuietly(worldId);
      toast(job.error || t("documents.extractionFailed"), "error");
    } else {
      await refreshWorldDataQuietly(worldId);
    }
  })().finally(() => {
    delete documentExtractionPolling[initialJob.id];
    renderDocuments();
  });
  return documentExtractionPolling[initialJob.id];
}

function documentExtractionPollDelay(job) {
  if (job.pause_requested) return 3_000;
  if (job.status === "running") return 5_000;
  if (job.retry_at) {
    const remaining = new Date(job.retry_at).getTime() - Date.now();
    return Math.max(3_000, Math.min(remaining, 10_000));
  }
  return 7_500;
}

async function refreshWorldDataQuietly(worldId = state.selectedWorldId) {
  if (!worldId || state.selectedWorldId !== worldId) return;
  try {
    await loadWorldData();
  } catch (error) {
    console.warn("World data refresh failed", error);
  }
}

export function selectAssistantScenario(scenario) {
  if (!["source", "audit", "adventure"].includes(scenario) || state.assistantBusy) return;
  state.assistantScenario = scenario;
  $("assistantConfirm").checked = false;
  renderAssistant();
}

export function clearAssistantHistory() {
  if (!state.assistantRuns.length || !confirm(t("assistant.clearConfirm"))) return;
  closeAssistantAuditResolver();
  clearStoredAssistantRuns();
  renderAssistant();
}

export async function runAssistantScenario(event) {
  event.preventDefault();
  if (!requireWorld() || state.assistantBusy) return;
  if (!$("assistantConfirm").checked) {
    toast(t("assistant.confirmRequired"), "error");
    return;
  }

  const scenario = state.assistantScenario;
  const input = assistantScenarioInput(scenario);
  if (!input) return;

  const run = addAssistantRun({
    scenario,
    title: input.title,
    documentId: input.documentId,
  });
  state.assistantBusy = true;
  renderAssistant();

  try {
    if (scenario === "source") {
      await extractKnowledgeDocument(input.documentId);
      const job = state.documentExtractionJobs[input.documentId];
      if (job?.status === "failed") {
        throw new Error(job.error || t("documents.extractionFailed"));
      }
      if (job?.status === "paused") {
        updateAssistantRun(run.id, {
          status: "interrupted",
          result: t("documents.extraction.paused"),
        });
        toast(t("documents.extractionPaused"));
        return;
      }
      updateAssistantRun(run.id, {
        status: "completed",
        result: t("assistant.source.completed", { count: job?.proposal_count || 0 }),
        proposalId: job?.proposal_id || null,
      });
    } else if (scenario === "adventure") {
      const proposal = await api(`/worlds/${state.selectedWorldId}/proposals/generate-adventure`, {
        method: "POST",
        body: JSON.stringify({
          role: currentRole(),
          output_language: language(),
          premise: input.query,
          scale: input.scale,
          tone: input.tone || null,
          enabled_modules: input.enabledModules,
          query: input.query,
          max_entities: input.maxExtractEntities,
        }),
      });
      state.proposals = [proposal, ...state.proposals.filter((item) => item.id !== proposal.id)];
      updateAssistantRun(run.id, {
        status: "completed",
        result: t("assistant.adventure.created", {
          entities: proposal.payload.entities.length,
          relationships: proposal.payload.relationships.length,
        }),
        proposalId: proposal.id,
      });
    } else {
      const response = await api(`/worlds/${state.selectedWorldId}/chat`, {
        method: "POST",
        body: JSON.stringify({
          role: currentRole(),
          output_language: language(),
          query: input.query,
          messages: [{ role: "user", content: input.prompt }],
          max_entities: 50,
          max_rules: 25,
          max_relationships: 100,
          save_to_wiki: false,
          temperature: 0.25,
          max_tokens: input.maxTokens,
        }),
      });
      updateAssistantRun(run.id, {
        status: "completed",
        result: response.completion.message.content,
        auditFindings: parseAssistantAuditFindings(response.completion.message.content),
      });
    }
    $("assistantConfirm").checked = false;
    toast(t("assistant.completed"));
  } catch (error) {
    updateAssistantRun(run.id, { status: "failed", error: error.message });
    toast(t("assistant.failed", { message: error.message }), "error");
  } finally {
    state.assistantBusy = false;
    renderAllWorldData();
  }
}

function reconcileAssistantSourceRuns() {
  state.assistantRuns
    .filter((run) => (
      run.scenario === "source" && ["running", "interrupted", "failed"].includes(run.status)
    ))
    .forEach((run) => {
      const job = state.documentExtractionJobs[run.documentId];
      if (!job) return;
      if (["queued", "running"].includes(job.status)) {
        updateAssistantRun(run.id, { status: "running", error: null });
      } else if (job.status === "completed") {
        updateAssistantRun(run.id, {
          status: "completed",
          result: t("assistant.source.completed", { count: job.proposal_count || 0 }),
          proposalId: job.proposal_id || null,
          error: null,
        });
      } else if (job.status === "failed") {
        updateAssistantRun(run.id, {
          status: "failed",
          error: job.error || t("documents.extractionFailed"),
        });
      }
    });
}

function assistantScenarioInput(scenario) {
  if (scenario === "source") {
    const documentId = $("assistantDocument").value;
    const document = state.documents.find((item) => item.id === documentId);
    if (!document || document.status !== "ready") {
      toast(t("assistant.source.chooseReady"), "error");
      return null;
    }
    return {
      documentId,
      title: document.filename,
    };
  }

  if (scenario === "audit") {
    const focus = $("assistantAuditFocus").value.trim();
    const full = $("assistantAuditDepth").value === "full";
    const query = focus || t("assistant.audit.defaultQuery");
    return {
      title: focus || t("assistant.audit.title"),
      query,
      prompt: buildAssistantAuditPrompt(query, full),
      maxTokens: full ? 2_800 : 1_600,
    };
  }

  const brief = $("assistantAdventureBrief").value.trim();
  if (!brief) {
    toast(t("assistant.adventure.briefRequired"), "error");
    $("assistantAdventureBrief").focus();
    return null;
  }
  const scale = $("assistantAdventureScale").value;
  const tone = $("assistantAdventureTone").value.trim();
  const enabledModules = Object.entries(state.moduleSettings)
    .filter(([, enabled]) => enabled !== false)
    .map(([name]) => name);
  return {
    title: brief,
    query: brief,
    scale,
    tone,
    enabledModules,
    maxExtractEntities: { small: 8, medium: 16, large: 28 }[scale] || 16,
  };
}

function buildAssistantAuditPrompt(focus, full) {
  const reportSize = full ? "detailed" : "concise";
  const languageRule = language() === "ru" ? "Write the report in Russian." : "Write the report in English.";
  return [
    "Audit the supplied world context without inventing new lore.",
    `Focus: ${focus}`,
    `Produce a ${reportSize} Markdown report.`,
    "Use sections: Summary, Contradictions, Probable duplicates, Missing links, Weak evidence, Next actions.",
    "Write every finding as a numbered item under exactly one section.",
    "If a section has no findings, write only 'None' under that heading and do not create a numbered item.",
    "For every finding, name the exact entities, relationships, rules, or sources that support it.",
    "Separate confirmed problems from hypotheses. If evidence is insufficient, say so.",
    "A duplicate requires direct same-identity evidence or matching identity markers. A shared location, group membership, relationship, similar role, or participation in the same event is not duplicate evidence.",
    "For each supported duplicate, give an explicit resolution: which card stays canonical, which unique facts and aliases move into it, and which card can be removed after manual confirmation.",
    "A short name such as Alexander must not be merged when it can refer to several full-name entities. In that case list the competing candidates and the exact missing identity evidence.",
    "Never infer reincarnation, transformation, kinship, or identity replacement unless the world context states it directly.",
    "Do not put ordinary clusters or strong relationships in Probable duplicates. Do not expose UUIDs, client IDs, or database keys.",
    "Do not create drafts and do not rewrite the world.",
    languageRule,
  ].join("\n");
}

export function parseAssistantAuditFindings(markdown) {
  const findings = [];
  let section = null;
  let current = null;

  const flush = () => {
    if (!current) return;
    if (auditFindingIsEmpty(current.title, current.body)) {
      current = null;
      return;
    }
    findings.push({
      id: `audit-${findings.length + 1}`,
      kind: section?.kind || "review",
      title: current.title,
      body: current.body.trim(),
      defaultSelected: section?.kind === "confirmed",
    });
    current = null;
  };

  String(markdown || "").split(/\r?\n/).forEach((line) => {
    const heading = line.match(/^#{2,3}\s+(.+?)\s*$/);
    if (heading) {
      flush();
      section = auditSection(heading[1]);
      return;
    }
    if (!section || section.kind === "skip") return;

    const item = line.match(/^\s*(?:\*\*)?(\d+)[.)]\s+(.+?)\s*$/);
    if (item) {
      flush();
      const cleaned = item[2].replace(/\*\*/g, "").trim();
      const separator = cleaned.indexOf(":");
      const title = (separator >= 0 ? cleaned.slice(0, separator) : cleaned).trim().slice(0, 200);
      const body = separator >= 0 ? cleaned.slice(separator + 1).trim() : "";
      current = { title, body };
      return;
    }
    if (current) current.body += `\n${line}`;
  });
  flush();
  return findings;
}

function auditSection(title) {
  const normalized = String(title || "").toLocaleLowerCase();
  if (/резюме|summary|следующ|next action/.test(normalized)) return { kind: "skip" };
  if (/подтверж|проблем|contradiction|confirmed/.test(normalized)) return { kind: "confirmed" };
  if (/гипотез|probable|possible|предполага/.test(normalized)) return { kind: "probable" };
  if (/отсутств|missing|пробел/.test(normalized)) return { kind: "missing" };
  if (/слаб|weak/.test(normalized)) return { kind: "weak" };
  return { kind: "review" };
}

function auditFindingIsEmpty(title, body) {
  const normalizedTitle = String(title || "").replace(/\*/g, "").trim().toLocaleLowerCase();
  if (/^(?:отсутствуют|отсутствует|нет|none|no findings?|not found)(?:\s|[:.,-]|$)/.test(normalizedTitle)) return true;
  const normalizedBody = String(body || "").replace(/[*_`#>-]/g, " ").replace(/\s+/g, " ").trim().toLocaleLowerCase();
  return /^(?:\d+[.)]\s*)?(?:отсутствуют|отсутствует|нет|none|no findings?)(?:\s|[:.,-]|$)/.test(normalizedBody);
}

export function openAssistantAuditResolver(runId) {
  const run = state.assistantRuns.find((item) => item.id === runId && item.scenario === "audit" && item.result);
  if (!run) return;
  const auditFindings = parseAssistantAuditFindings(run.result);
  updateAssistantRun(run.id, { auditFindings });
  state.activeAuditRunId = run.id;
  state.auditFindingSelection = auditFindings
    .filter((finding) => finding.defaultSelected)
    .map((finding) => finding.id);
  state.duplicateCandidatesBusy = true;
  renderAssistant();
  void loadEntityDuplicateCandidates();
}

export function closeAssistantAuditResolver() {
  state.activeAuditRunId = null;
  state.auditFindingSelection = [];
  $("assistantAuditResolverBackdrop")?.classList.add("hidden");
  document.body.classList.remove("drawer-open");
}

export async function loadEntityDuplicateCandidates() {
  if (!state.selectedWorldId) return;
  state.duplicateCandidatesBusy = true;
  renderAssistant();
  try {
    state.duplicateCandidates = await api(`/worlds/${state.selectedWorldId}/entities/duplicate-candidates`);
  } catch (error) {
    state.duplicateCandidates = [];
    toast(t("duplicates.loadFailed", { message: error.message }), "error");
  } finally {
    state.duplicateCandidatesBusy = false;
    renderAssistant();
  }
}

export function openEntityMergeResolver(leftId, rightId) {
  const candidate = state.duplicateCandidates.find(
    (item) => item.left.id === leftId && item.right.id === rightId,
  );
  if (!candidate) return;
  state.activeDuplicateCandidate = candidate;
  state.entityMergePrimaryId = entityCompleteness(candidate.left) >= entityCompleteness(candidate.right)
    ? candidate.left.id
    : candidate.right.id;
  renderEntityMergeResolver();
}

export function closeEntityMergeResolver() {
  state.activeDuplicateCandidate = null;
  state.entityMergePrimaryId = null;
  $("entityMergeBackdrop")?.classList.add("hidden");
  renderAssistant();
}

export function selectEntityMergePrimary(entityId) {
  const candidate = state.activeDuplicateCandidate;
  if (!candidate || ![candidate.left.id, candidate.right.id].includes(entityId)) return;
  state.entityMergePrimaryId = entityId;
  renderEntityMergeResolver();
}

export async function submitEntityMerge(event) {
  event.preventDefault();
  const candidate = state.activeDuplicateCandidate;
  if (!candidate || state.entityMergeBusy || !requireWorld()) return;
  const primary = candidate.left.id === state.entityMergePrimaryId ? candidate.left : candidate.right;
  const duplicate = primary.id === candidate.left.id ? candidate.right : candidate.left;
  if (!window.confirm(t("duplicates.confirm", { primary: primary.name, duplicate: duplicate.name }))) return;
  const requestPayload = {
    primary_entity_id: primary.id,
    duplicate_entity_id: duplicate.id,
    type: primary.type,
    name: $("entityMergeName").value.trim(),
    summary: $("entityMergeSummary").value.trim() || null,
    description: $("entityMergeDescription").value.trim() || null,
    aliases: splitTags($("entityMergeAliases").value),
    tags: splitTags($("entityMergeTags").value),
    is_secret: $("entityMergeSecret").checked,
    status: primary.status,
    attributes: { ...(duplicate.attributes || {}), ...(primary.attributes || {}) },
  };

  state.entityMergeBusy = true;
  renderEntityMergeResolver();
  try {
    const result = await api(`/worlds/${state.selectedWorldId}/entities/merge`, {
      method: "POST",
      body: JSON.stringify(requestPayload),
    });
    closeEntityMergeResolver();
    await loadWorldData();
    await loadEntityDuplicateCandidates();
    toast(t("duplicates.merged", {
      name: result.entity.name,
      relationships: result.rewired_relationships + result.merged_relationships,
    }));
  } catch (error) {
    toast(t("duplicates.mergeFailed", { message: error.message }), "error");
  } finally {
    state.entityMergeBusy = false;
    renderEntityMergeResolver();
  }
}

function entityCompleteness(entity) {
  return String(entity.name || "").length * 2
    + String(entity.summary || "").length
    + String(entity.description || "").length
    + (entity.aliases || []).length * 20
    + (entity.tags || []).length * 10
    + Object.keys(entity.attributes || {}).length * 15;
}

export async function createAssistantAuditDraft(event) {
  event.preventDefault();
  if (!requireWorld() || state.assistantBusy) return;
  const run = state.assistantRuns.find((item) => item.id === state.activeAuditRunId);
  const selectedIds = new Set(state.auditFindingSelection);
  const selectedFindings = (run?.auditFindings || []).filter((finding) => selectedIds.has(finding.id));
  if (!selectedFindings.length) {
    toast(t("assistant.audit.selectRequired"), "error");
    return;
  }

  state.assistantBusy = true;
  renderAssistant();
  try {
    const sourceText = selectedFindings.map((finding) => `## ${finding.title}\n${finding.body}`).join("\n\n");
    const proposal = await api(`/worlds/${state.selectedWorldId}/proposals/extract`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        output_language: language(),
        query: selectedFindings.map((finding) => finding.title).join("; ").slice(0, 2_000),
        source_text: sourceText,
        intent_text: [
          "Prepare one review draft only from the audit findings explicitly selected by the user.",
          "Do not turn hypotheses into facts. Do not invent identity, aliases, dates, or relationships.",
          "For a duplicate, update aliases only when the selected finding directly proves the same identity; otherwise add a note for manual review.",
          "For missing objects or links, create them only when the selected evidence states the fact directly.",
        ].join(" "),
        max_entities: 50,
      }),
    });
    state.proposals = [proposal, ...state.proposals.filter((item) => item.id !== proposal.id)];
    updateAssistantRun(run.id, {
      proposalId: proposal.id,
      resolvedFindingIds: Array.from(selectedIds),
    });
    closeAssistantAuditResolver();
    renderAllWorldData();
    activateTab("proposals");
    toast(t("assistant.audit.draftCreated"));
  } catch (error) {
    toast(t("assistant.audit.draftFailed", { message: error.message }), "error");
  } finally {
    state.assistantBusy = false;
    renderAllWorldData();
  }
}

function replaceDocument(document) {
  const index = state.documents.findIndex((item) => item.id === document.id);
  if (index >= 0) state.documents[index] = document;
  else state.documents.unshift(document);
}

export async function buildEmbeddingIndex() {
  if (!requireWorld() || state.embeddingBusy) return;
  const worldId = state.selectedWorldId;
  const operation = ++embeddingOperation;
  state.embeddingBusy = true;
  state.embeddingJob = null;
  renderDocuments();
  try {
    let job = await api(`/worlds/${worldId}/embeddings/process?batch_size=16`, { method: "POST" });
    if (operation !== embeddingOperation) return;
    state.embeddingJob = job;
    while (
      operation === embeddingOperation &&
      state.embeddingBusy &&
      state.selectedWorldId === worldId &&
      !["completed", "failed", "cancelled"].includes(job.status)
    ) {
      await new Promise((resolve) => window.setTimeout(resolve, embeddingJobPollDelay(job)));
      if (operation !== embeddingOperation || !state.embeddingBusy || state.selectedWorldId !== worldId) return;
      job = await api(`/embedding-jobs/${job.id}`);
      if (operation !== embeddingOperation) return;
      state.embeddingJob = job;
      renderDocuments();
    }
    if (operation !== embeddingOperation || state.selectedWorldId !== worldId) return;
    if (job.status === "failed") throw new Error(job.error || t("embeddings.failed"));
    state.embeddingStatus = await api(`/worlds/${worldId}/embedding-status`);
    await refreshWorldDataQuietly();
    toast(t("embeddings.ready"));
  } finally {
    if (operation === embeddingOperation) {
      state.embeddingBusy = false;
      renderDocuments();
    }
  }
}

function embeddingJobPollDelay(job) {
  if (job.retry_at) {
    const remaining = new Date(job.retry_at).getTime() - Date.now();
    return Math.max(2_500, Math.min(remaining, 10_000));
  }
  return job.status === "running" ? 3_000 : 5_000;
}

export async function clearEmbeddingIndex() {
  if (!requireWorld() || !window.confirm(t("embeddings.clearConfirm"))) return;
  embeddingOperation += 1;
  state.embeddingBusy = false;
  state.embeddingJob = null;
  state.embeddingStatus = await api(`/worlds/${state.selectedWorldId}/embeddings`, { method: "DELETE" });
  renderDocuments();
  await refreshWorldDataQuietly();
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
  const color = $("entityColor")?.value;
  if (imageUrl) attributes.image_url = imageUrl;
  if (timelineDate) attributes.timeline_date = timelineDate;
  if (color) attributes.color = color;
  const mergedAttributes = { ...(existing?.attributes || {}), ...attributes };
  if (!imageUrl) delete mergedAttributes.image_url;
  if (!timelineDate) delete mergedAttributes.timeline_date;
  if (!color) delete mergedAttributes.color;

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

export async function saveWorldChange(event) {
  event.preventDefault();
  if (!requireWorld()) return;
  const subjectValue = $("experienceSubject").value;
  const isEntity = subjectValue.startsWith("entity:");
  const payload = {
    subject_type: isEntity ? "entity" : "world",
    subject_id: isEntity ? subjectValue.slice("entity:".length) : null,
    change_kind: $("experienceKind").value,
    summary: $("experienceSummary").value.trim(),
    effective_at: $("experienceEffectiveAt").value.trim() || null,
    evidence: $("experienceEvidence").value.trim() || null,
    confidence: Number($("experienceConfidence").value),
    causal_change_ids: Array.from($("experienceCauses").selectedOptions, (option) => option.value),
    supersedes_change_id: $("experienceSupersedes").value || null,
    is_secret: $("experienceSecret").checked,
  };
  if (state.editingWorldChangeId) {
    await api(`/changes/${state.editingWorldChangeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("experience.updated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/changes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("experience.created"));
  }
  resetWorldChangeForm();
  await loadWorldData();
}

export function editWorldChange(changeId) {
  const change = state.worldChanges.find((item) => item.id === changeId && item.source_type === "manual");
  if (!change) return;
  state.editingWorldChangeId = change.id;
  renderExperience();
  $("experienceSummary").value = change.summary || "";
  $("experienceSubject").value = change.subject_type === "entity" && change.subject_id
    ? `entity:${change.subject_id}`
    : "world";
  $("experienceKind").value = change.change_kind;
  $("experienceEffectiveAt").value = change.effective_at || "";
  $("experienceEvidence").value = change.evidence || "";
  $("experienceConfidence").value = String(change.confidence ?? 1);
  $("experienceSecret").checked = Boolean(change.is_secret);
  Array.from($("experienceCauses").options).forEach((option) => {
    option.selected = change.causal_change_ids.includes(option.value);
  });
  $("experienceSupersedes").value = change.supersedes_change_id || "";
  $("experienceSubmit").textContent = t("common.save");
  $("experienceFormTitle").textContent = t("experience.editTitle");
  $("cancelExperienceEdit").classList.remove("hidden");
  $("experienceSummary").focus();
}

export function resetWorldChangeForm() {
  state.editingWorldChangeId = null;
  $("experienceForm")?.reset();
  if ($("experienceConfidence")) $("experienceConfidence").value = "1";
  if ($("experienceFormTitle")) $("experienceFormTitle").textContent = t("experience.createTitle");
  $("cancelExperienceEdit")?.classList.add("hidden");
  renderExperience();
}

export function startCreateEntity() {
  startCreateEntityWithType();
}

export function startCreateEntityWithType(entityType = "", initialTags = []) {
  resetEntityForm({ keepDrawerOpen: true });
  if (entityType && isSupportedEntityType(entityType)) {
    $("entityType").value = entityType;
  }
  $("entityTags").value = Array.isArray(initialTags)
    ? initialTags.map((tag) => String(tag).trim()).filter(Boolean).join(", ")
    : "";
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
  if ($("entityColor")) $("entityColor").value = entity.attributes?.color || entityTypeColor(entity.type);
  $("entityTags").value = (entity.tags || []).join(", ");
  $("entitySecret").checked = Boolean(entity.is_secret);
  renderEntityFormMode();
  openEntityDrawer();
  $("entityName").focus();
}

export function resetEntityForm(options = {}) {
  state.editingEntityId = null;
  $("entityForm").reset();
  if ($("entityColor")) $("entityColor").value = entityTypeColor($("entityType")?.value);
  renderEntityFormMode();
  if (!options.keepDrawerOpen) {
    closeEntityDrawer();
  }
}

function entityTypeColor(typeKey) {
  return state.entityTypes.find((definition) => definition.key === typeKey)?.color || "#6B7280";
}

export async function createEntityType(event) {
  event.preventDefault();
  if (!requireWorld()) return;
  await api(`/worlds/${state.selectedWorldId}/entity-types`, {
    method: "POST",
    body: JSON.stringify({
      name: $("entityTypeName").value.trim(),
      color: $("entityTypeColor").value,
    }),
  });
  $("entityTypeForm").reset();
  $("entityTypeColor").value = "#6B7280";
  await loadWorldData();
}

export async function updateEntityType(typeId, payload) {
  await api(`/entity-types/${typeId}`, { method: "PATCH", body: JSON.stringify(payload) });
  await loadWorldData();
}

export async function deleteEntityType(typeId) {
  if (!confirm(language() === "ru" ? "Удалить тип сущности?" : "Delete entity type?")) return;
  await api(`/entity-types/${typeId}`, { method: "DELETE" });
  await loadWorldData();
}

export async function createQuestStatus(event) {
  event.preventDefault();
  if (!requireWorld()) return;
  await api(`/worlds/${state.selectedWorldId}/quest-statuses`, {
    method: "POST",
    body: JSON.stringify({
      name: $("questStatusName").value.trim(),
      color: $("questStatusColor").value,
    }),
  });
  $("questStatusForm").reset();
  $("questStatusColor").value = "#6B7280";
  await loadWorldData();
}

export async function updateQuestStatus(statusId, payload) {
  await api(`/quest-statuses/${statusId}`, { method: "PATCH", body: JSON.stringify(payload) });
  await loadWorldData();
}

export async function deleteQuestStatus(statusId) {
  if (!confirm(language() === "ru" ? "Удалить статус? Квесты перейдут в первый оставшийся статус." : "Delete status? Quests will move to the first remaining status.")) return;
  await api(`/quest-statuses/${statusId}`, { method: "DELETE" });
  await loadWorldData();
}

export async function reorderEntities(entityIds, orderAttribute, statusKey = null) {
  const updates = entityIds.map((entityId, index) => {
    const entity = state.entities.find((item) => item.id === entityId);
    if (!entity) return Promise.resolve();
    const attributes = { ...(entity.attributes || {}), [orderAttribute]: index };
    if (statusKey !== null) attributes.quest_status = statusKey;
    entity.attributes = attributes;
    return api(`/entities/${entityId}`, {
      method: "PATCH",
      body: JSON.stringify({ attributes }),
    });
  });
  await Promise.all(updates);
  await loadWorldData();
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

  const payload = {
    source_entity_id: $("relationshipSource").value,
    target_entity_id: $("relationshipTarget").value,
    type: $("relationshipType").value.trim(),
    label: $("relationshipLabel").value.trim() || null,
    description: $("relationshipDescription").value.trim() || null,
    confidence: Number($("relationshipConfidence").value),
    weight: Number($("relationshipWeight").value),
    valid_from: $("relationshipValidFrom").value.trim() || null,
    valid_to: $("relationshipValidTo").value.trim() || null,
    evidence: $("relationshipEvidence").value.trim() || null,
    effective_at: $("relationshipEffectiveAt").value.trim() || null,
    change_note: $("relationshipChangeNote").value.trim() || null,
    is_secret: $("relationshipSecret").checked,
  };
  if (state.editingRelationshipId) {
    await api(`/relationships/${state.editingRelationshipId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toast(t("relationship.updated"));
  } else {
    await api(`/worlds/${state.selectedWorldId}/relationships`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(t("relationship.created"));
  }
  resetRelationshipForm();
  await loadWorldData();
}

export function editRelationship(relationshipId) {
  const relationship = state.relationships.find((item) => item.id === relationshipId);
  if (!relationship) return;
  state.editingRelationshipId = relationship.id;
  $("relationshipSource").value = relationship.source_entity_id;
  $("relationshipTarget").value = relationship.target_entity_id;
  $("relationshipType").value = relationship.type;
  $("relationshipLabel").value = relationship.label || "";
  $("relationshipDescription").value = relationship.description || "";
  $("relationshipConfidence").value = String(relationship.confidence);
  $("relationshipWeight").value = String(relationship.weight ?? 1);
  $("relationshipValidFrom").value = relationship.valid_from || "";
  $("relationshipValidTo").value = relationship.valid_to || "";
  $("relationshipEvidence").value = relationship.evidence || "";
  $("relationshipEffectiveAt").value = relationship.valid_from || "";
  $("relationshipChangeNote").value = "";
  $("relationshipSecret").checked = Boolean(relationship.is_secret);
  renderRelationshipFormMode();
  $("relationshipType").focus();
}

export function resetRelationshipForm() {
  state.editingRelationshipId = null;
  $("relationshipForm").reset();
  $("relationshipConfidence").value = "1";
  $("relationshipWeight").value = "1";
  renderRelationshipFormMode();
}

export async function deleteWorld(worldId) {
  const world = state.worlds.find((item) => item.id === worldId);
  if (!world || !confirm(t("world.confirmDelete", { name: world.name }))) return;
  await api(`/worlds/${worldId}`, { method: "DELETE" });
  toast(t("world.deleted"));
  await loadWorlds();
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

export async function generateDetectiveBoard() {
  if (!requireWorld()) return;
  const button = $("generateDetectiveBoard");
  button.disabled = true;
  toast(t("detective.generating"));
  try {
    await api(`/worlds/${state.selectedWorldId}/detective-board/generate`, {
      method: "POST",
      body: JSON.stringify({ output_language: language() }),
    });
    toast(t("detective.generated"));
    await loadWorldData();
  } finally {
    button.disabled = false;
  }
}

export async function deleteDetectiveBoard() {
  if (!requireWorld() || !confirm(t("detective.confirmBoardDelete"))) return;
  await api(`/worlds/${state.selectedWorldId}/detective-board`, { method: "DELETE" });
  toast(t("detective.boardDeleted"));
  resetDetectiveNodeForm();
  resetDetectiveConnectionForm();
  await loadWorldData();
}

export async function sendChat(event) {
  event.preventDefault();
  if (!requireWorld()) return;

  const content = $("chatInput").value.trim();
  if (!content) return;

  $("chatInput").value = "";
  state.chatMessages.push({ role: "user", content });
  persistActiveChatMessages();
  renderChatThreads();
  state.chatBusy = true;
  renderChat();

  const submit = event.submitter || $("chatForm").querySelector("button");
  submit.disabled = true;
  $("chatInput").disabled = true;
  try {
    const requestMessages = state.chatMessages.slice(-CHAT_CONTEXT_MESSAGE_LIMIT).map((message) => ({
      role: message.role,
      content: message.content,
    }));
    const response = await api(`/worlds/${state.selectedWorldId}/chat`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        output_language: language(),
        query: content,
        messages: requestMessages,
      }),
    });

    state.chatMessages.push(response.completion.message);
    persistActiveChatMessages();
    renderChatThreads();
    if (response.proposal) {
      toast(t("chat.proposalCreated"));
    }
    if (response.wiki_save_error) {
      toast(t("chat.wikiSaveFailed", { message: response.wiki_save_error }), "error");
    }
    renderChat();
    await loadWorldData();
  } catch (error) {
    persistActiveChatMessages();
    toast(t("chat.failed", { message: error.message }), "error");
  } finally {
    state.chatBusy = false;
    submit.disabled = false;
    $("chatInput").disabled = false;
    renderChat();
  }
}

export function startNewChatThread() {
  createChatThreadFromMessages();
  renderChatThreads();
  renderChat();
}

export function branchChatThread() {
  createChatThreadFromMessages(state.chatMessages);
  renderChatThreads();
  renderChat();
}

export function changeChatThread(threadId) {
  switchChatThread(threadId);
  renderChatThreads();
  renderChat();
}

export function renameChatThread(threadId) {
  const thread = state.chatThreads.find((item) => item.id === threadId);
  if (!thread) return;
  state.editingChatThreadId = threadId;
  renderChatThreads();
  $(`chatThreadEdit-${threadId}`)?.focus();
}

export function cancelChatThreadRename() {
  state.editingChatThreadId = null;
  renderChatThreads();
}

export function saveChatThreadRename(threadId) {
  const input = $(`chatThreadEdit-${threadId}`);
  if (!renameStoredChatThread(threadId, input?.value)) {
    toast(t("chat.renameEmpty"), "error");
    return;
  }
  state.editingChatThreadId = null;
  renderChatThreads();
}

export function deleteChatThread(threadId) {
  if (!confirm(t("chat.confirmDeleteThread"))) return;
  deleteStoredChatThread(threadId);
  renderChatThreads();
  renderChat();
}

export function editChatMessage(messageIndex) {
  if (!state.chatMessages[messageIndex]) return;
  state.editingChatMessageIndex = messageIndex;
  renderChat();
  $(`chatMessageEdit-${messageIndex}`)?.focus();
}

export function cancelChatMessageEdit() {
  state.editingChatMessageIndex = null;
  renderChat();
}

export function saveChatMessageEdit(messageIndex) {
  const input = $(`chatMessageEdit-${messageIndex}`);
  const content = input?.value.trim() || "";
  if (!content) {
    toast(t("chat.messageEmpty"), "error");
    return;
  }
  state.chatMessages[messageIndex] = { ...state.chatMessages[messageIndex], content };
  state.editingChatMessageIndex = null;
  persistActiveChatMessages();
  renderChatThreads();
  renderChat();
}

export function deleteChatMessage(messageIndex) {
  if (!state.chatMessages[messageIndex] || !confirm(t("chat.confirmDeleteMessage"))) return;
  state.chatMessages.splice(messageIndex, 1);
  state.editingChatMessageIndex = null;
  persistActiveChatMessages();
  renderChatThreads();
  renderChat();
}

export function insertChatTemplate(templateId) {
  const input = $("chatInput");
  const text = t(`chatTemplate.${templateId}.text`);
  if (!input || text === `chatTemplate.${templateId}.text`) return;
  const prefix = input.value.trim() ? "\n\n" : "";
  input.value = `${input.value}${prefix}${text}`;
  input.focus();
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
    const intentMessage = [...state.chatMessages.slice(0, messageIndex)]
      .reverse()
      .find((item) => item.role === "user");
    const proposal = await api(`/worlds/${state.selectedWorldId}/proposals/extract`, {
      method: "POST",
      body: JSON.stringify({
        role: currentRole(),
        output_language: language(),
        source_text: message.content,
        intent_text: intentMessage?.content || null,
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
  $("proposalPayload").value = '{ "entities": [], "relationships": [], "world_rules": [], "random_tables": [], "random_table_rows": [], "notes": [] }';
  toast(t("proposal.created"));
  await loadWorldData();
}

export async function saveProposalEdits(event) {
  event.preventDefault();
  if (!state.editingProposalId || !state.editingProposalPayload) return;

  const sourceText = $("proposalEditorSource").value.trim();
  if (!sourceText) return;
  const proposal = await api(`/proposals/${state.editingProposalId}`, {
    method: "PATCH",
    body: JSON.stringify({
      source_text: sourceText,
      payload: state.editingProposalPayload,
    }),
  });
  state.proposals = [proposal, ...state.proposals.filter((item) => item.id !== proposal.id)];
  closeProposalEditor();
  renderAllWorldData();
  toast(t("proposal.saved"));
}

export async function setProposalItemSecret(proposalId, collection, index, isSecret) {
  const allowedCollections = new Set([
    "entities",
    "relationships",
    "world_rules",
    "random_tables",
    "random_table_rows",
  ]);
  const proposal = state.proposals.find((item) => item.id === proposalId && item.status === "pending");
  const draftItem = allowedCollections.has(collection) ? proposal?.payload?.[collection]?.[index] : null;
  if (!proposal || !draftItem) return;

  const previousValue = Boolean(draftItem.is_secret);
  draftItem.is_secret = Boolean(isSecret);
  document.querySelectorAll(`[data-proposal-secret="${proposalId}"]`).forEach((input) => {
    input.disabled = true;
  });
  document
    .querySelectorAll(
      `[data-apply-proposal="${proposalId}"], [data-edit-proposal="${proposalId}"], [data-delete-proposal="${proposalId}"]`,
    )
    .forEach((button) => {
      button.disabled = true;
    });
  try {
    const updated = await api(`/proposals/${proposalId}`, {
      method: "PATCH",
      body: JSON.stringify({
        source_text: proposal.source_text,
        payload: proposal.payload,
      }),
    });
    state.proposals = [updated, ...state.proposals.filter((item) => item.id !== updated.id)];
    renderAllWorldData();
    toast(t("proposal.visibilitySaved"));
  } catch (error) {
    draftItem.is_secret = previousValue;
    renderAllWorldData();
    toast(t("proposal.visibilityFailed", { message: error.message }), "error");
  }
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
    random_table_indices: checked("random-table"),
    random_table_row_indices: checked("random-table-row"),
  };
  const totalSelected =
    payload.entity_indices.length +
    payload.relationship_indices.length +
    payload.world_rule_indices.length +
    payload.random_table_indices.length +
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

export async function deleteProposal(id) {
  if (!confirm(t("proposal.confirmDelete"))) return;
  await api(`/proposals/${id}`, { method: "DELETE" });
  toast(t("proposal.deleted"));
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

export async function deleteEntity(entityId) {
  if (!confirm(t("entity.confirmDelete") || "Удалить эту карточку?")) return;
  await api(`/entities/${entityId}`, { method: "DELETE" });
  if (state.selectedEntityId === entityId) {
    closeEntityReader();
  }
  toast(t("entity.deleted") || "Карточка удалена.");
  await loadWorldData();
}

export async function deleteRelationship(relationshipId) {
  if (!confirm(t("relationship.confirmDelete") || "Удалить эту связь?")) return;
  await api(`/relationships/${relationshipId}`, { method: "DELETE" });
  toast(t("relationship.deleted") || "Связь удалена.");
  await loadWorldData();
}

export async function deleteRule(ruleId) {
  if (!confirm(t("rule.confirmDelete") || "Удалить этот закон?")) return;
  await api(`/world-rules/${ruleId}`, { method: "DELETE" });
  toast(t("rule.deleted") || "Закон удален.");
  await loadWorldData();
}
