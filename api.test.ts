import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { useUndo } from '../contexts/UndoContext';
import { usePlayerMode } from '../contexts/PlayerModeContext';
import { api } from '../api';
import { Plus, Trash2, GripVertical, Sparkles, EyeOff } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { SectionHelp } from './SectionHelp';

export const QuestBoardView = () => {
  const { t } = useLanguage();
  const { addUndo } = useUndo();
  const { isPlayerMode } = usePlayerMode();
  const [quests, setQuests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightedQuestId, setHighlightedQuestId] = useState<string | null>(null);
  const [generatingQuestId, setGeneratingQuestId] = useState<string | null>(null);
  const [editingQuestId, setEditingQuestId] = useState<string | null>(null);

  const columns = [
    { id: 'todo', title: t.quests_todo, color: 'border-stone-500' },
    { id: 'in_progress', title: t.quests_in_progress, color: 'border-blue-500' },
    { id: 'done', title: t.quests_done, color: 'border-emerald-500' },
    { id: 'failed', title: t.quests_failed, color: 'border-red-500' },
  ];

  useEffect(() => {
    loadQuests();
  }, []);

  // Effect to handle opening specific quest by ID from event
  useEffect(() => {
    const processNavigationDetail = async (detail: any) => {
      if (detail?.questId) {
        await loadQuests();
        setHighlightedQuestId(detail.questId);
        setTimeout(() => setHighlightedQuestId(null), 3000); // Remove highlight after 3 seconds
      }
    };

    if ((window as any).__lastNavigateDetail) {
      processNavigationDetail((window as any).__lastNavigateDetail);
      delete (window as any).__lastNavigateDetail;
    }

    const handleNavigate = (e: CustomEvent) => processNavigationDetail(e.detail);
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  const loadQuests = async () => {
    setLoading(true);
    try {
      const data = await api.getQuests();
      setQuests(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleAddQuest = async (status: string) => {
    const newQuest = {
      title: t.quests_new_title,
      description: '',
      status,
      order_index: quests.filter(q => q.status === status).length
    };
    await api.saveQuest(newQuest);
    loadQuests();
  };

  const handleUpdateQuest = async (quest: any, updates: any) => {
    const updated = { ...quest, ...updates };
    setQuests(quests.map(q => q.id === quest.id ? updated : q));
    await api.saveQuest(updated);
  };

  const handleGenerateQuestDesc = async (quest: any) => {
    if (!quest.title || quest.title === t.quests_new_title) {
      alert("Сначала введите осмысленное название квеста.");
      return;
    }
    setGeneratingQuestId(quest.id);
    try {
      const prompt = `Как гейм-мастер настольной ролевой игры, придумай интересную завязку, подробности или следующие шаги для квеста с названием "${quest.title}". 
Сделай описание интригующим. Только текст описания, без JSON и без Markdown заголовков, 1-2 абзаца на русском языке.`;
      const reply = await api.chat([{ role: 'user', content: prompt }]);
      
      const oldDescription = quest.description || '';
      const newDescription = (oldDescription ? oldDescription + '\n\n' : '') + reply;
      
      await handleUpdateQuest(quest, { description: newDescription });
      
      addUndo(`Генерация шагов квеста "${quest.title}"`, async () => {
        await handleUpdateQuest(quest, { description: oldDescription });
      });

    } catch (e: any) {
      console.error(e);
      alert("Ошибка при генерации: " + e.message);
    } finally {
      setGeneratingQuestId(null);
    }
  };

  const handleDeleteQuest = async (id: string) => {
    if (confirm(t.quests_delete_confirm)) {
      const questToDelete = quests.find(q => q.id === id);
      await api.deleteQuest(id);
      
      if (questToDelete) {
        addUndo(`Удаление квеста "${questToDelete.title}"`, async () => {
          await api.saveQuest(questToDelete);
          loadQuests();
        });
      }
      loadQuests();
    }
  };

  const handleDragStart = (e: React.DragEvent, questId: string) => {
    e.dataTransfer.setData('questId', questId);
  };

  const handleDrop = async (e: React.DragEvent, status: string) => {
    e.preventDefault();
    const questId = e.dataTransfer.getData('questId');
    if (!questId) return;

    const quest = quests.find(q => q.id === questId);
    if (quest && quest.status !== status) {
      // Optimistic update
      const updatedQuests = quests.map(q => 
        q.id === questId ? { ...q, status } : q
      );
      setQuests(updatedQuests);
      await api.saveQuest({ ...quest, status });
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  if (loading) return <div className="p-8 text-stone-400">{t.loading}</div>;

  const visibleQuests = quests.filter(q => !(isPlayerMode && q.is_secret));

  return (
    <div className="p-4 md:p-8 h-full flex flex-col">
      <h2 className="text-3xl font-bold mb-6 text-stone-100 flex items-center">
        {t.quests_title}
        <SectionHelp content={
          <>
            <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Квестам</h3>
            <p><strong>Доска квестов</strong> помогает отслеживать задачи, сюжетные зацепки (Hooks) и задания для игроков в виде удобной канбан-доски.</p>
            <ul className="list-disc list-inside space-y-2 mt-2">
              <li><strong>Статусы:</strong> Перетаскивайте карточки между колонками для изменения их статуса.</li>
              <li><strong>Секретность:</strong> Для GM можно помечать квесты секретными. "Секретные" квесты будут видны только вам и полностью скроются в Режиме Игрока.</li>
              <li><strong>AI-Генерация:</strong> Нажмите на иконку ✨ для выбранного квеста, и ИИ сгенерирует для него интересное продолжение или детали. Убедитесь, что заголовок квеста информативен.</li>
              <li><strong>Редактирование:</strong> Кликните на заголовок или текст карточки, чтобы отредактировать её описание. Можно использовать Markdown и броски кубиков.</li>
            </ul>
          </>
        } />
      </h2>
      
      <div className="flex-1 flex gap-4 overflow-x-auto pb-4">
        {columns.map(col => (
          <div 
            key={col.id} 
            className="flex-1 min-w-[300px] bg-stone-900/50 rounded-2xl border border-stone-800 flex flex-col"
            onDrop={!isPlayerMode ? (e) => handleDrop(e, col.id) : undefined}
            onDragOver={!isPlayerMode ? handleDragOver : undefined}
          >
            <div className={`p-4 border-b-2 ${col.color} bg-stone-900 rounded-t-2xl flex justify-between items-center`}>
              <h3 className="font-bold text-stone-200">{col.title}</h3>
            </div>
            
            <div className="p-4 flex-1 overflow-y-auto space-y-3">
              {visibleQuests.filter(q => q.status === col.id).map(quest => (
                <div 
                  key={quest.id}
                  draggable={!isPlayerMode}
                  onDragStart={!isPlayerMode ? (e) => handleDragStart(e, quest.id) : undefined}
                  className={`bg-stone-800 border ${highlightedQuestId === quest.id ? 'border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.5)]' : 'border-stone-700'} rounded-xl p-3 ${isPlayerMode ? '' : 'cursor-grab active:cursor-grabbing hover:border-emerald-500/50'} transition-all duration-500 group relative`}
                >
                  <div className="flex justify-between items-start mb-2 pr-12">
                    <input 
                      type="text"
                      value={quest.title}
                      readOnly={isPlayerMode}
                      onChange={(e) => handleUpdateQuest(quest, { title: e.target.value })}
                      className="bg-transparent border-none text-stone-200 font-medium focus:outline-none focus:ring-1 focus:ring-emerald-500 rounded px-1 w-full"
                    />
                    {!isPlayerMode && (
                      <div className="absolute right-2 top-2 flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => handleUpdateQuest(quest, { is_secret: !quest.is_secret })}
                          className={`p-1 rounded-md transition-colors ${quest.is_secret ? 'bg-amber-500/20 text-amber-400' : 'text-stone-500 hover:text-stone-300 bg-stone-700/50'}`}
                          title="Секретно (только для GM)"
                        >
                          <EyeOff size={16} />
                        </button>
                        <button 
                          onClick={() => handleDeleteQuest(quest.id)}
                          className="text-stone-500 hover:text-red-400 p-1"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  {quest.is_secret && isPlayerMode && null /* handled by visibility */}
                  {quest.is_secret && !isPlayerMode && (
                     <div className="absolute -top-2 -right-2 transform translate-x-0 translate-y-0 text-xs font-bold bg-amber-500 text-amber-950 px-1.5 py-0.5 rounded shadow-sm z-10 pointer-events-none">
                       Секретно
                     </div>
                  )}
                  <div className="relative mt-2">
                    {!isPlayerMode && (
                      <div className="absolute right-2 top-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => handleGenerateQuestDesc(quest)}
                          disabled={generatingQuestId === quest.id}
                          className="bg-emerald-900/50 hover:bg-emerald-800 text-emerald-400 p-1 rounded-md"
                          title="AI Генерация идей для квеста"
                        >
                          <Sparkles size={14} className={generatingQuestId === quest.id ? "animate-pulse" : ""} />
                        </button>
                      </div>
                    )}
                    {isPlayerMode ? (
                      <div className="w-full text-sm text-stone-400 whitespace-pre-wrap px-2 py-1">
                        <MarkdownRenderer>{quest.description || ''}</MarkdownRenderer>
                      </div>
                    ) : editingQuestId === quest.id ? (
                      <textarea
                        value={quest.description || ''}
                        onChange={(e) => handleUpdateQuest(quest, { description: e.target.value })}
                        onBlur={() => setEditingQuestId(null)}
                        autoFocus
                        placeholder="Описание..."
                        className="w-full bg-stone-900/50 border border-stone-700 rounded-lg p-2 pr-8 text-sm text-stone-400 focus:outline-none focus:border-emerald-500 resize-none min-h-[80px]"
                      />
                    ) : (
                      <div 
                        className="w-full text-sm text-stone-400 whitespace-pre-wrap px-2 py-1 cursor-text hover:bg-stone-800/50 rounded-lg border border-transparent hover:border-stone-700 transition-colors min-h-[40px]"
                        onClick={() => setEditingQuestId(quest.id)}
                        title="Нажмите, чтобы редактировать"
                      >
                         <MarkdownRenderer>{quest.description || 'Описание...'}</MarkdownRenderer>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {!isPlayerMode && (
                <button 
                  onClick={() => handleAddQuest(col.id)}
                  className="w-full py-2 border-2 border-dashed border-stone-700 rounded-xl text-stone-500 hover:text-emerald-400 hover:border-emerald-500/50 transition-colors flex items-center justify-center gap-2"
                >
                  <Plus size={16} /> {t.quests_add}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
