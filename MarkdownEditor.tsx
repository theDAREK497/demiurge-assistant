import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { usePlayerMode } from '../contexts/PlayerModeContext';
import { api } from '../api';
import { analyzeJournalLog } from '../services/aiService';
import { Sparkles, Save, Check, X, Plus, ArrowLeft, Trash2, Calendar, ScrollText, EyeOff } from 'lucide-react';

import { MarkdownEditor } from './MarkdownEditor';

import { MarkdownRenderer } from './MarkdownRenderer';
import { SectionHelp } from './SectionHelp';

export const JournalView = () => {
  const { t } = useLanguage();
  const { isPlayerMode } = usePlayerMode();
  const [viewMode, setViewMode] = useState<'list' | 'new' | 'view'>('list');
  const [logs, setLogs] = useState<any[]>([]);
  const [currentLog, setCurrentLog] = useState<any>(null);
  
  const [title, setTitle] = useState('');
  const [sessionDate, setSessionDate] = useState(new Date().toISOString().split('T')[0]);
  const [logText, setLogText] = useState('');
  const [isSecret, setIsSecret] = useState(false);
  
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState<{ entities: any[], events: any[] } | null>(null);
  const [selectedEntities, setSelectedEntities] = useState<Set<number>>(new Set());
  const [selectedEvents, setSelectedEvents] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    loadLogs();
  }, []);

  // Effect to handle opening specific journal by ID from event
  useEffect(() => {
    const processNavigationDetail = async (detail: any) => {
      if (detail?.journalId) {
        try {
          const data = await api.getJournalLogs();
          setLogs(data);
          const log = data.find((l: any) => l.id === detail.journalId);
          if (log) {
            setCurrentLog(log);
            setViewMode('view');
          }
        } catch (err) {
          console.error("Failed to load log", err);
        }
      }
    };

    if ((window as any).__lastNavigateDetail) {
      processNavigationDetail((window as any).__lastNavigateDetail);
      // Wait, we don't delete __lastNavigateDetail everywhere because multiple components might need to check it?
      // No, they are in different tabs, so only one mounts per navigate! Safe to delete or ignore deletion. Let's delete it.
      delete (window as any).__lastNavigateDetail;
    }

    const handleNavigate = (e: CustomEvent) => processNavigationDetail(e.detail);
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  const loadLogs = async () => {
    try {
      const data = await api.getJournalLogs();
      setLogs(data);
    } catch (err) {
      console.error('Failed to load journal logs', err);
    }
  };

  const handleAnalyze = async () => {
    if (!logText.trim()) return;
    
    setIsAnalyzing(true);
    setError(null);
    setSuccessMsg(null);
    
    try {
      const data = await analyzeJournalLog(logText);
      setResults(data);
      
      // Select all by default
      setSelectedEntities(new Set(data.entities?.map((_: any, i: number) => i) || []));
      setSelectedEvents(new Set(data.events?.map((_: any, i: number) => i) || []));
    } catch (err: any) {
      console.error(err);
      setError(err.message || t.journal_error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSaveLog = async () => {
    if (!title.trim() || !logText.trim()) return;

    try {
      await api.saveJournalLog({
        title,
        content: logText,
        session_date: sessionDate,
        is_secret: isSecret
      });

      // Save selected entities
      if (results) {
        const entitiesToSave = results.entities?.filter((_, i) => selectedEntities.has(i)) || [];
        for (const ent of entitiesToSave) {
          await api.saveEntity({
            type: ent.type || 'npc',
            name: ent.name,
            description: ent.description,
            tags: 'journal_auto',
            data: {}
          });
        }

        // Save selected events
        const eventsToSave = results.events?.filter((_, i) => selectedEvents.has(i)) || [];
        for (const ev of eventsToSave) {
          await api.saveEvent({
            title: ev.title,
            description: ev.description,
            event_date: ev.date || sessionDate,
            order_index: 0
          });
        }
      }

      setSuccessMsg(t.journal_saved_success);
      setTimeout(() => {
        setSuccessMsg(null);
        setViewMode('list');
        loadLogs();
      }, 2000);
    } catch (err) {
      console.error("Failed to save journal data", err);
      setError("Failed to save data");
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm(t.journal_delete_confirm)) {
      try {
        await api.deleteJournalLog(id);
        loadLogs();
        if (currentLog?.id === id) {
          setViewMode('list');
        }
      } catch (err) {
        console.error('Failed to delete log', err);
      }
    }
  };

  const toggleEntity = (index: number) => {
    const newSet = new Set(selectedEntities);
    if (newSet.has(index)) newSet.delete(index);
    else newSet.add(index);
    setSelectedEntities(newSet);
  };

  const toggleEvent = (index: number) => {
    const newSet = new Set(selectedEvents);
    if (newSet.has(index)) newSet.delete(index);
    else newSet.add(index);
    setSelectedEvents(newSet);
  };

  const startNewLog = () => {
    setTitle('');
    setSessionDate(new Date().toISOString().split('T')[0]);
    setLogText('');
    setIsSecret(false);
    setResults(null);
    setError(null);
    setSuccessMsg(null);
    setViewMode('new');
  };

  const visibleLogs = logs.filter(log => !(isPlayerMode && log.is_secret));

  if (viewMode === 'list') {
    return (
      <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold text-stone-100 flex items-center">
            {t.journal_title}
            <SectionHelp content={
              <>
                <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Журналу сессий</h3>
                <p>Ведите здесь свободные текстовые записи событий сессии: какие локации посетили игроки, с кем разговаривали, какие предметы нашли.</p>
                <ul className="list-disc list-inside space-y-2 mt-2">
                  <li><strong>AI Экстракция:</strong> Главная особенность журнала — после завершения сессии и написания лога нажмите кнопку ✨ (Analyze with AI). ИИ прочтет весь лог и автоматически предложит создать недостающие карточки в Вики (новых NPC, локации) и добавить события в Хронологию.</li>
                  <li><strong>Секретность:</strong> Логи можно помечать секретными (иконка перечеркнутого глаза), чтобы скрыть их в Режиме Игрока (например, если лог содержит ваши мастерские заметки).</li>
                </ul>
              </>
            } />
          </h2>
          {!isPlayerMode && (
            <button
              onClick={startNewLog}
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl font-medium flex items-center transition-colors"
            >
              <Plus size={20} className="mr-2" />
              {t.journal_new_log}
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto space-y-4">
          {visibleLogs.length === 0 ? (
            <div className="text-center text-stone-500 mt-12">
              <ScrollText size={48} className="mx-auto mb-4 opacity-50" />
              <p>{t.journal_empty}</p>
            </div>
          ) : (
            visibleLogs.map(log => (
              <div key={log.id} className="bg-stone-900 border border-stone-800 rounded-xl p-4 hover:border-stone-700 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center space-x-3">
                    <h3 
                      className="text-xl font-bold text-stone-200 cursor-pointer hover:text-emerald-400 transition-colors"
                      onClick={() => {
                        setCurrentLog(log);
                        setViewMode('view');
                      }}
                    >
                      {log.title}
                    </h3>
                    {log.is_secret ? (
                      <span className="flex items-center text-xs font-medium bg-amber-500/20 text-amber-500 px-2 py-1 rounded-md">
                        <EyeOff size={12} className="mr-1" />
                        Секретно
                      </span>
                    ) : null}
                  </div>
                  {!isPlayerMode && (
                    <button 
                      onClick={() => handleDelete(log.id)}
                      className="text-stone-500 hover:text-red-400 p-1"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </div>
                <div className="flex items-center text-stone-500 text-sm mb-3">
                  <Calendar size={14} className="mr-1" />
                  {log.session_date}
                </div>
                <div className="text-stone-400 line-clamp-3">
                  <MarkdownRenderer>{log.content}</MarkdownRenderer>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  if (viewMode === 'view' && currentLog) {
    return (
      <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col">
        <div className="mb-6">
          <button 
            onClick={() => setViewMode('list')}
            className="text-stone-400 hover:text-stone-200 flex items-center mb-4"
          >
            <ArrowLeft size={20} className="mr-1" /> {t.journal_back}
          </button>
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-3xl font-bold text-stone-100 mb-2">{currentLog.title}</h2>
              <div className="flex items-center text-stone-500">
                <Calendar size={16} className="mr-2" />
                {currentLog.session_date}
              </div>
            </div>
            <button 
              onClick={() => handleDelete(currentLog.id)}
              className="text-red-400 hover:text-red-300 bg-red-400/10 hover:bg-red-400/20 px-3 py-2 rounded-lg flex items-center transition-colors"
            >
              <Trash2 size={18} className="mr-2" />
              Delete
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto bg-stone-900 border border-stone-800 rounded-xl p-6">
          <div className="prose prose-invert prose-emerald max-w-none">
            <MarkdownRenderer>{currentLog.content}</MarkdownRenderer>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col">
      <div className="mb-6 flex items-center justify-between">
        <button 
          onClick={() => setViewMode('list')}
          className="text-stone-400 hover:text-stone-200 flex items-center"
        >
          <ArrowLeft size={20} className="mr-1" /> {t.journal_back}
        </button>
        <h2 className="text-2xl font-bold text-stone-100">{t.journal_new_log}</h2>
      </div>
      
      <div className="flex-1 flex flex-col gap-6 overflow-y-auto">
        <div className="flex flex-col md:flex-row gap-4">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t.journal_title_placeholder}
            className="flex-1 bg-stone-900 border border-stone-800 rounded-xl p-3 text-stone-200 focus:outline-none focus:border-emerald-500"
          />
          <input
            type="date"
            value={sessionDate}
            onChange={(e) => setSessionDate(e.target.value)}
            className="bg-stone-900 border border-stone-800 rounded-xl p-3 text-stone-200 focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={() => setIsSecret(!isSecret)}
            className={`flex items-center px-4 py-3 md:py-0 rounded-xl transition-colors border ${isSecret ? 'bg-amber-500/20 text-amber-500 border-amber-500/30' : 'bg-stone-900 text-stone-500 border-stone-800 hover:text-stone-400'}`}
          >
            <EyeOff size={20} className="mr-2" />
            Секретно
          </button>
        </div>

        <div className="flex flex-col gap-4">
          <MarkdownEditor
            value={logText}
            onChange={setLogText}
            placeholder={t.journal_placeholder}
            minHeight="200px"
          />
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !logText.trim()}
            className="self-end bg-stone-800 hover:bg-stone-700 disabled:bg-stone-900 disabled:text-stone-600 text-emerald-400 px-6 py-3 rounded-xl font-medium flex items-center transition-colors border border-stone-700"
          >
            <Sparkles size={20} className="mr-2" />
            {isAnalyzing ? t.journal_analyzing : t.journal_analyze}
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-900 text-red-400 p-4 rounded-xl">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="bg-emerald-900/30 border border-emerald-900 text-emerald-400 p-4 rounded-xl flex items-center">
            <Check size={20} className="mr-2" />
            {successMsg}
          </div>
        )}

        {results && (
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-6 space-y-6">
            <h3 className="text-xl font-bold text-emerald-400">{t.journal_results_title}</h3>
            
            {(!results.entities?.length && !results.events?.length) ? (
              <p className="text-stone-400">{t.journal_no_results}</p>
            ) : (
              <>
                {results.entities && results.entities.length > 0 && (
                  <div>
                    <h4 className="text-lg font-medium text-stone-200 mb-3">{t.journal_entities_found}</h4>
                    <div className="space-y-2">
                      {results.entities.map((ent, i) => (
                        <div 
                          key={i} 
                          onClick={() => toggleEntity(i)}
                          className={`p-3 rounded-lg border cursor-pointer flex items-start gap-3 transition-colors ${selectedEntities.has(i) ? 'bg-emerald-900/20 border-emerald-500/50' : 'bg-stone-950 border-stone-800 hover:border-stone-700'}`}
                        >
                          <div className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center shrink-0 ${selectedEntities.has(i) ? 'bg-emerald-500 text-stone-950' : 'border border-stone-600'}`}>
                            {selectedEntities.has(i) && <Check size={14} />}
                          </div>
                          <div>
                            <div className="font-medium text-stone-200">
                              {ent.name} <span className="text-xs text-stone-500 uppercase ml-2 bg-stone-800 px-2 py-0.5 rounded">{ent.type}</span>
                            </div>
                            <div className="text-sm text-stone-400 mt-1">{ent.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {results.events && results.events.length > 0 && (
                  <div>
                    <h4 className="text-lg font-medium text-stone-200 mb-3">{t.journal_events_found}</h4>
                    <div className="space-y-2">
                      {results.events.map((ev, i) => (
                        <div 
                          key={i} 
                          onClick={() => toggleEvent(i)}
                          className={`p-3 rounded-lg border cursor-pointer flex items-start gap-3 transition-colors ${selectedEvents.has(i) ? 'bg-emerald-900/20 border-emerald-500/50' : 'bg-stone-950 border-stone-800 hover:border-stone-700'}`}
                        >
                          <div className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center shrink-0 ${selectedEvents.has(i) ? 'bg-emerald-500 text-stone-950' : 'border border-stone-600'}`}>
                            {selectedEvents.has(i) && <Check size={14} />}
                          </div>
                          <div>
                            <div className="font-medium text-stone-200">
                              {ev.title} {ev.date && <span className="text-xs text-stone-500 ml-2">{ev.date}</span>}
                            </div>
                            <div className="text-sm text-stone-400 mt-1">{ev.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div className="pt-4 flex justify-end pb-8">
          <button
            onClick={handleSaveLog}
            disabled={!title.trim() || !logText.trim()}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-stone-800 disabled:text-stone-500 text-white px-6 py-3 rounded-xl font-medium flex items-center transition-colors"
          >
            <Save size={20} className="mr-2" />
            {t.journal_save_log}
          </button>
        </div>
      </div>
    </div>
  );
};
