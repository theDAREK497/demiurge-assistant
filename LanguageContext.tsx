import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { useUndo } from '../contexts/UndoContext';
import { usePlayerMode } from '../contexts/PlayerModeContext';
import { Search, Filter, Hash, Book, Edit2, Save, X, Plus, Trash2, ArrowLeft, Image as ImageIcon, MapPin, Sparkles, EyeOff } from 'lucide-react';

import { MarkdownEditor } from './MarkdownEditor';
import { MarkdownRenderer } from './MarkdownRenderer';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { GraphView } from './GraphView';

import { SectionHelp } from './SectionHelp';

export const WikiView = () => {
  const { t } = useLanguage();
  const { addUndo } = useUndo();
  const { isPlayerMode } = usePlayerMode();
  const [entities, setEntities] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterTag, setFilterTag] = useState<string>('all');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [viewingEntity, setViewingEntity] = useState<any>(null);
  const [viewMode, setViewMode] = useState<'list' | 'graph'>('list');
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [locationNode, setLocationNode] = useState<any>(null);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [isGeneratingDesc, setIsGeneratingDesc] = useState(false);
  const [backlinks, setBacklinks] = useState<{entities: any[], quests: any[], journals: any[]}>({ entities: [], quests: [], journals: [] });
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const loadEntities = async () => {
    const data = await api.getEntities();
    setEntities(data);
  };

  useEffect(() => {
    loadEntities();
  }, []);

  useEffect(() => {
    if (viewingEntity) {
      if (viewingEntity.data?.locationId) {
        api.getMapNode(viewingEntity.data.locationId).then(node => {
          setLocationNode(node);
        }).catch(e => {
          console.error("Failed to fetch location node", e);
          setLocationNode(null);
        });
      } else {
        setLocationNode(null);
      }
      
      api.getBacklinks(viewingEntity.name).then(data => {
        setBacklinks(data);
      }).catch(e => {
        console.error("Failed to fetch backlinks", e);
        setBacklinks({ entities: [], quests: [], journals: [] });
      });
      
    } else {
      setLocationNode(null);
      setBacklinks({ entities: [], quests: [], journals: [] });
    }
  }, [viewingEntity]);

  // Effect to handle opening specific entity by ID from event
  useEffect(() => {
    const processNavigationDetail = async (detail: any) => {
      if (detail?.entityId || detail?.search) {
        try {
          const freshEntities = await api.getEntities();
          setEntities(freshEntities);
          
          if (detail.entityId) {
            const entity = freshEntities.find((ent: any) => ent.id === detail.entityId);
            if (entity) setViewingEntity(entity);
          } else if (detail.search) {
            const decodedSearch = decodeURIComponent(detail.search);
            const exactMatch = freshEntities.find((ent: any) => ent.name.toLowerCase() === decodedSearch.toLowerCase());
            if (exactMatch) {
              setViewingEntity(exactMatch);
            } else {
              setSearch(decodedSearch);
              setViewingEntity(null);
            }
          }
        } catch (err) {
          console.error("Failed to load entity", err);
        }
      }
    };

    // Check for pending navigation that triggered this mount
    if ((window as any).__lastNavigateDetail) {
      processNavigationDetail((window as any).__lastNavigateDetail);
      delete (window as any).__lastNavigateDetail;
    }

    const handleNavigate = (e: CustomEvent) => processNavigationDetail(e.detail);

    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  const types = ['all', 'npc', 'enemy', 'item', 'location', 'country', 'faction', 'settlement', 'pc'];
  const entityTypes = ['npc', 'enemy', 'item', 'location', 'country', 'faction', 'settlement', 'pc'];

  const visibleEntities = entities.filter(e => !(isPlayerMode && e.is_secret));

  const allTags = Array.from(new Set(
    visibleEntities.flatMap(e => (e.tags || '').split(',').map((t: string) => t.trim()).filter(Boolean))
  )).sort();

  const filteredEntities = visibleEntities.filter(e => {
    const matchesSearch = e.name.toLowerCase().includes(search.toLowerCase()) || 
                          (e.description && e.description.toLowerCase().includes(search.toLowerCase()));
    const matchesType = filterType === 'all' || e.type === filterType;
    const matchesTag = filterTag === 'all' || (e.tags && e.tags.split(',').map((t: string) => t.trim()).includes(filterTag));
    return matchesSearch && matchesType && matchesTag;
  });

  const handleEdit = (entity: any, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingId(entity.id);
    setEditForm({ ...entity });
  };

  const handleSave = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const entityToSave = { ...editForm };
    if (entityToSave.id === 'new') {
      delete entityToSave.id;
    }
    const res = await api.saveEntity(entityToSave);
    setEditingId(null);
    loadEntities();
    if (viewingEntity) {
      setViewingEntity({ ...editForm, id: res.id || editForm.id });
    }
  };

  const handleCancel = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingId(null);
    if (viewingEntity?.id === 'new') {
      setViewingEntity(null);
    }
  };

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (id === 'new') {
      setEditingId(null);
      setViewingEntity(null);
      return;
    }
    if (deleteConfirmId === id) {
      const entityToDelete = entities.find(ent => ent.id === id);
      await api.deleteEntity(id);
      
      if (entityToDelete) {
        addUndo(`Удаление карточки "${entityToDelete.name}"`, async () => {
          await api.saveEntity(entityToDelete);
          loadEntities();
        });
      }

      setEditingId(null);
      setViewingEntity(null);
      setDeleteConfirmId(null);
      loadEntities();
    } else {
      setDeleteConfirmId(id);
      setTimeout(() => setDeleteConfirmId(null), 3000);
    }
  };

  const handleCreateNew = () => {
    const newEntity = { id: 'new', name: '', type: 'npc', description: '', tags: '', image: '', data: {} };
    setEditForm(newEntity);
    setEditingId('new');
    setViewingEntity(newEntity);
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const url = await api.uploadImage(file);
      setEditForm({ ...editForm, image: url });
    } catch (err) {
      console.error('Failed to upload image', err);
      alert(t.wiki_upload_failed);
    }
  };

  const handleGenerateImage = async () => {
    if (!editForm.name) {
      alert(t.wiki_entity_name + " is required to generate an image.");
      return;
    }
    setIsGeneratingImage(true);
    try {
      const prompt = `A fantasy portrait of ${editForm.name}, ${editForm.type}. ${editForm.description || ''}`.substring(0, 500);
      const url = await api.generateImage(prompt);
      setEditForm({ ...editForm, image: url });
    } catch (err: any) {
      console.error('Failed to generate image', err);
      alert("Error: " + err.message);
    } finally {
      setIsGeneratingImage(false);
    }
  };

  const handleGenerateDescription = async () => {
    if (!editForm.name) {
      alert("Сначала введите имя сущности.");
      return;
    }
    setIsGeneratingDesc(true);
    try {
      const prompt = `Пожалуйста, сгенерируй детальное, атмосферное описание (backstory/lore) для сущности по имени "${editForm.name}" (Тип: ${t[`wiki_type_${editForm.type}` as keyof typeof t] || editForm.type}). 
Используй красивый литературный стиль, подходящий для настольной ролевой игры. 
Только текст описания, без системных JSON блоков. На русском языке.`;
      const reply = await api.chat([{ role: 'user', content: prompt }]);
      
      const oldDescription = editForm.description || '';
      const newDescription = (oldDescription ? oldDescription + '\n\n' : '') + reply;
      
      setEditForm({
        ...editForm, 
        description: newDescription
      });

      addUndo(`Генерация описания для "${editForm.name}"`, async () => {
        setEditForm((prev: any) => ({ ...prev, description: oldDescription }));
      });

    } catch (err: any) {
      console.error('Failed to generate description', err);
      alert("Error: " + err.message);
    } finally {
      setIsGeneratingDesc(false);
    }
  };

  if (viewingEntity) {
    return (
      <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col overflow-y-auto">
        <button onClick={() => setViewingEntity(null)} className="flex items-center text-stone-400 hover:text-emerald-400 mb-6 transition-colors w-fit">
          <ArrowLeft size={20} className="mr-2" /> {t.wiki_back}
        </button>
        
        {editingId === viewingEntity.id ? (
          <div className="bg-stone-900 border border-emerald-500 rounded-2xl p-8 space-y-4">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <input 
                type="text" 
                value={editForm.name} 
                onChange={e => setEditForm({...editForm, name: e.target.value})}
                className="bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-emerald-400 font-bold text-2xl w-full"
                placeholder={t.wiki_entity_name}
              />
              <select 
                value={editForm.type}
                onChange={e => setEditForm({...editForm, type: e.target.value})}
                className="bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-sm text-stone-400 uppercase w-full md:w-auto"
              >
                {entityTypes.map(type => <option key={type} value={type}>{t[`wiki_type_${type}` as keyof typeof t] || type}</option>)}
              </select>
            </div>
            
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 space-y-4">
                <div className="flex items-center gap-4">
                  <input 
                    type="text" 
                    value={editForm.image || ''} 
                    onChange={e => setEditForm({...editForm, image: e.target.value})}
                    className="flex-1 bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-sm text-stone-400"
                    placeholder={t.wiki_image_url}
                  />
                  <input 
                    type="file" 
                    accept="image/*" 
                    className="hidden" 
                    ref={fileInputRef}
                    onChange={handleImageUpload}
                  />
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-stone-800 hover:bg-stone-700 text-stone-300 p-2 rounded-lg flex items-center transition-colors shrink-0"
                    title={t.wiki_upload_image}
                  >
                    <ImageIcon size={20} />
                  </button>
                  <button 
                    onClick={handleGenerateImage}
                    disabled={isGeneratingImage}
                    className="bg-emerald-900/30 hover:bg-emerald-900/50 text-emerald-400 p-2 rounded-lg flex items-center transition-colors shrink-0 disabled:opacity-50"
                    title={t.wiki_generate_image}
                  >
                    {isGeneratingImage ? <Sparkles size={20} className="animate-pulse" /> : <Sparkles size={20} />}
                  </button>
                </div>
                
                <div className="flex items-center gap-4 bg-stone-950 border border-stone-800 rounded-lg px-4 py-2">
                  <label className="text-sm text-stone-400 flex-1">Цвет карточки (для фракций и т.д.)</label>
                  <input 
                    type="color" 
                    value={editForm.data?.color || '#10b981'} 
                    onChange={e => setEditForm({...editForm, data: {...(editForm.data || {}), color: e.target.value}})}
                    className="bg-transparent border-none w-8 h-8 cursor-pointer shrink-0"
                  />
                </div>
              </div>
              
              {editForm.image && (
                <div className="shrink-0">
                  <img src={editForm.image} alt="Preview" className="h-24 w-24 object-cover rounded-lg border border-stone-800" referrerPolicy="no-referrer" />
                </div>
              )}
            </div>

            <div className="relative">
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-medium text-stone-400">{t.wiki_description}</label>
                <button 
                  onClick={handleGenerateDescription}
                  disabled={isGeneratingDesc}
                  className="bg-emerald-900/30 hover:bg-emerald-900/50 text-emerald-400 px-3 py-1 text-sm rounded-lg flex items-center transition-colors disabled:opacity-50"
                  title="Сгенерировать ИИ описание"
                >
                  {isGeneratingDesc ? <Sparkles size={16} className="animate-pulse mr-2" /> : <Sparkles size={16} className="mr-2" />}
                  Авто-генерация лора
                </button>
              </div>
              <MarkdownEditor 
                value={editForm.description}
                onChange={(val) => setEditForm({...editForm, description: val})}
                placeholder={t.wiki_description}
                minHeight="250px"
              />
            </div>
            
            <div className="flex gap-2">
              <input 
                type="text" 
                value={editForm.tags || ''}  
                onChange={e => setEditForm({...editForm, tags: e.target.value})}
                placeholder={t.wiki_tags}
                className="flex-1 bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-sm text-stone-400"
              />
              <button
                onClick={() => setEditForm({...editForm, is_secret: !editForm.is_secret})}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors border ${editForm.is_secret ? 'bg-amber-500/20 text-amber-500 border-amber-500/30' : 'bg-stone-900 border-stone-800 text-stone-500 hover:text-stone-400'}`}
                title="Скрыть эту запись от игроков"
              >
                <EyeOff size={18} className="mr-2" />
                Секретно
              </button>
            </div>
            <div className="flex justify-between items-center mt-6">
              <button onClick={(e) => { e.stopPropagation(); handleDelete(viewingEntity.id, e); }} className="p-2 text-red-400 hover:text-red-300 bg-red-900/30 rounded-lg flex items-center">
                <Trash2 size={18} className="mr-2" /> {deleteConfirmId === viewingEntity.id ? t.wiki_delete_confirm : t.wiki_delete}
              </button>
              <div className="flex space-x-2">
                <button onClick={(e) => { e.stopPropagation(); handleCancel(e); }} className="px-4 py-2 text-stone-400 hover:text-stone-200 bg-stone-800 rounded-lg flex items-center">
                  <X size={18} className="mr-2" /> {t.wiki_cancel}
                </button>
                <button onClick={(e) => { e.stopPropagation(); handleSave(e); }} className="px-4 py-2 text-emerald-400 hover:text-emerald-300 bg-emerald-900/30 rounded-lg flex items-center">
                  <Save size={18} className="mr-2" /> {t.wiki_save}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div 
            className="bg-stone-900 border border-stone-800 rounded-2xl p-8 relative group overflow-hidden"
            style={viewingEntity.data?.color ? { borderTopColor: viewingEntity.data.color, borderTopWidth: '4px' } : {}}
          >
            {!isPlayerMode && (
              <button 
                onClick={(e) => handleEdit(viewingEntity, e)}
                className="absolute top-6 right-6 p-2 text-stone-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity bg-stone-800 rounded-lg"
              >
                <Edit2 size={20} />
              </button>
            )}
            <div className="flex flex-col md:flex-row justify-between items-start mb-8 gap-4 pr-12">
              <div className="flex items-center gap-4">
                {viewingEntity.image && (
                  <img src={viewingEntity.image} alt={viewingEntity.name} className="w-16 h-16 rounded-full object-cover border-2 border-stone-800" referrerPolicy="no-referrer" />
                )}
                <h2 className="text-4xl font-bold" style={{ color: viewingEntity.data?.color || '#34d399' }}>{viewingEntity.name}</h2>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono uppercase tracking-wider bg-stone-800 text-stone-400 px-3 py-1 rounded-md">
                  {t[`wiki_type_${viewingEntity.type}` as keyof typeof t] || viewingEntity.type}
                </span>
                {viewingEntity.is_secret && (
                  <span className="flex items-center text-xs font-bold bg-amber-500/20 text-amber-500 px-2 py-1 rounded uppercase">
                    <EyeOff size={12} className="mr-1" />
                    Секретно
                  </span>
                )}
              </div>
            </div>
            <div className="prose prose-invert prose-emerald max-w-none mb-8">
              {viewingEntity.description ? (
                <MarkdownRenderer>
                  {viewingEntity.description.replace(/\[\[(.*?)\]\]/g, (match: string, entityName: string) => `[${entityName}](#wiki:${encodeURIComponent(entityName)})`)}
                </MarkdownRenderer>
              ) : (
                <span className="text-stone-500 italic">{t.wiki_no_description}</span>
              )}
            </div>
            {viewingEntity.tags && (
              <div className="flex flex-wrap gap-2 pt-6 border-t border-stone-800">
                {viewingEntity.tags.split(',').map((tag: string, i: number) => (
                  <span key={i} className="flex items-center text-sm text-stone-500 bg-stone-950 px-3 py-1 rounded-full">
                    <Hash size={12} className="mr-1" />
                    {tag.trim()}
                  </span>
                ))}
              </div>
            )}
            
            {locationNode && (
              <div className="mt-6 pt-6 border-t border-stone-800">
                <h3 className="text-sm font-bold text-stone-500 uppercase mb-3">Расположение</h3>
                <button 
                  onClick={() => {
                    window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'map', mapNodeId: locationNode.id } }));
                  }}
                  className="flex items-center gap-3 bg-stone-950 hover:bg-stone-800 border border-stone-800 p-3 rounded-xl transition-colors text-left w-full sm:w-auto"
                >
                  <div className="w-10 h-10 rounded-full bg-emerald-900/30 flex items-center justify-center text-emerald-400 shrink-0">
                    <MapPin size={20} />
                  </div>
                  <div>
                    <div className="text-stone-200 font-medium">{locationNode.name}</div>
                    <div className="text-stone-500 text-xs uppercase">{locationNode.type}</div>
                  </div>
                </button>
              </div>
            )}

            <div className="mt-8 pt-6 border-t border-stone-800">
              <h3 className="text-sm font-bold text-stone-500 uppercase mb-4 flex items-center gap-2">
                <Book size={16} />
                {t.wiki_backlinks}
              </h3>
              
              {(() => {
                const visibleEntitiesBL = backlinks.entities.filter(e => e.id !== viewingEntity.id && !(isPlayerMode && e.is_secret));
                const visibleQuestsBL = backlinks.quests.filter(q => !(isPlayerMode && q.is_secret));
                const visibleJournalsBL = backlinks.journals.filter(j => !(isPlayerMode && j.is_secret));
                const hasAny = visibleEntitiesBL.length > 0 || visibleQuestsBL.length > 0 || visibleJournalsBL.length > 0;

                return !hasAny ? (
                  <div className="text-stone-500 italic text-sm">{t.wiki_backlinks_empty}</div>
                ) : (
                  <div className="space-y-4">
                    {visibleEntitiesBL.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-stone-500 uppercase font-semibold">Вики</div>
                        <div className="flex flex-wrap gap-2">
                          {visibleEntitiesBL.map(e => (
                            <button 
                              key={`ent-${e.id}`}
                              onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'wiki', entityId: e.id } }))}
                              className="bg-stone-950 border border-stone-800 hover:border-emerald-500 hover:text-emerald-400 px-3 py-1.5 rounded-lg text-sm text-stone-300 transition-colors flex items-center gap-2"
                            >
                              <span className="text-stone-600">[{t[`wiki_type_${e.type}` as keyof typeof t] || e.type}]</span>
                              {e.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {visibleQuestsBL.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-stone-500 uppercase font-semibold">Квесты</div>
                        <div className="flex flex-wrap gap-2">
                          {visibleQuestsBL.map(q => (
                            <button 
                              key={`qst-${q.id}`}
                              onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'quests', questId: q.id } }))}
                              className="bg-stone-950 border border-stone-800 hover:border-emerald-500 hover:text-emerald-400 px-3 py-1.5 rounded-lg text-sm text-stone-300 transition-colors flex items-center gap-2"
                            >
                              {q.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {visibleJournalsBL.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-stone-500 uppercase font-semibold">Журнал</div>
                        <div className="flex flex-wrap gap-2">
                          {visibleJournalsBL.map(j => (
                            <button 
                              key={`jrn-${j.id}`}
                              onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'journal', journalId: j.id } }))}
                              className="bg-stone-950 border border-stone-800 hover:border-emerald-500 hover:text-emerald-400 px-3 py-1.5 rounded-lg text-sm text-stone-300 transition-colors flex items-center gap-2"
                            >
                              <span className="text-stone-600">[{j.session_date}]</span>
                              {j.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
            
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div className="flex items-center space-x-4">
          <h2 className="text-3xl font-bold text-stone-100 flex items-center">
            {t.wiki_title}
            <SectionHelp content={
              <>
                <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Вики</h3>
                <p>Раздел <strong>Вики</strong> — это база знаний вашей игры или вселенной. Здесь хранятся карточки персонажей, локаций, фракций.</p>
                <ul className="list-disc list-inside space-y-2 mt-2">
                  <li><strong>Создание связей:</strong> Описывайте связи с помощью Markdown-ссылок в тексте: <code>[[Имя карточки]]</code></li>
                  <li><strong>Граф связей:</strong> Переключите вид списка на Граф, чтобы наглядно увидеть связи между сущностями.</li>
                  <li><strong>Обратные ссылки:</strong> При просмотре карточки внизу выводятся все другие карточки, ссылающиеся на неё.</li>
                </ul>
              </>
            } />
          </h2>
          <div className="flex bg-stone-900 rounded-lg p-1 border border-stone-800">
            <button 
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${viewMode === 'list' ? 'bg-stone-800 text-emerald-400' : 'text-stone-400 hover:text-stone-200'}`}
            >
              {t.wiki_list_view || 'List'}
            </button>
            <button 
              onClick={() => setViewMode('graph')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${viewMode === 'graph' ? 'bg-stone-800 text-emerald-400' : 'text-stone-400 hover:text-stone-200'}`}
            >
              {t.wiki_graph_view || 'Graph'}
            </button>
          </div>
        </div>
        
        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-4 w-full md:w-auto">
          <div className="relative flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-500" size={18} />
            <input 
              type="text"
              placeholder={t.wiki_search}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-stone-900 border border-stone-800 rounded-xl pl-10 pr-4 py-2 text-stone-200 focus:outline-none focus:border-emerald-500 w-full sm:w-64"
            />
          </div>
          
          <div className="flex space-x-2">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-stone-900 border border-stone-800 rounded-xl px-4 py-2 text-stone-200 focus:outline-none focus:border-emerald-500 flex-1 sm:flex-none"
            >
              {types.map(type => (
                <option key={type} value={type}>
                  {type === 'all' ? t.wiki_all_types : t[`wiki_type_${type}` as keyof typeof t]}
                </option>
              ))}
            </select>

            <select
              value={filterTag}
              onChange={(e) => setFilterTag(e.target.value)}
              className="bg-stone-900 border border-stone-800 rounded-xl px-4 py-2 text-stone-200 focus:outline-none focus:border-emerald-500 flex-1 sm:flex-none"
            >
              <option value="all">{t.wiki_all_tags}</option>
              {allTags.map(tag => (
                <option key={tag as string} value={tag as string}>{tag as string}</option>
              ))}
            </select>
            
            {!isPlayerMode && (
              <button 
                onClick={handleCreateNew} 
                className="bg-emerald-600 hover:bg-emerald-500 text-white p-2 rounded-xl flex items-center justify-center transition-colors px-4"
              >
                <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{t.wiki_add_new}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {viewMode === 'graph' ? (
        <div className="flex-1 min-h-[500px]">
          <GraphView 
            entities={filteredEntities} 
            onNodeClick={(entity) => setViewingEntity(entity)} 
          />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto pb-8 space-y-6">
          {filteredEntities.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-stone-500">
              <Book size={48} className="mb-4 opacity-20" />
              <p>{t.wiki_no_entities}</p>
            </div>
          ) : (
            Object.entries(
              filteredEntities.reduce((acc: any, entity: any) => {
                const group = entity.type || 'other';
                if (!acc[group]) acc[group] = [];
                acc[group].push(entity);
                return acc;
              }, {})
            ).sort(([a], [b]) => a.localeCompare(b)).map(([type, groupEntities]: [string, any]) => {
              const typeName = t[`wiki_type_${type}` as keyof typeof t] || type;
              const isCollapsed = collapsedGroups[type];
              
              return (
                <div key={type} className="bg-stone-900/50 rounded-2xl border border-stone-800 p-4">
                  <div 
                    className="flex justify-between items-center cursor-pointer pb-2 mb-4 border-b border-stone-800/50"
                    onClick={() => setCollapsedGroups(prev => ({ ...prev, [type]: !prev[type] }))}
                  >
                    <h3 className="text-xl font-bold text-stone-300 flex items-center gap-2">
                       {typeName} <span className="text-xs font-mono bg-stone-800 text-stone-500 px-2 py-0.5 rounded-full">{groupEntities.length}</span>
                    </h3>
                    <div className="text-stone-500">
                      {isCollapsed ? <Plus size={18} /> : <X size={18} className="rotate-45" />}
                    </div>
                  </div>
                  
                  {!isCollapsed && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {groupEntities.map((entity: any) => (
                        <div 
                          key={entity.id} 
                          className="bg-stone-900 border border-stone-800 rounded-2xl p-6 hover:border-emerald-500/50 transition-colors group relative cursor-pointer flex flex-col h-64 overflow-hidden shadow-sm"
                          style={entity.data?.color ? { borderTopColor: entity.data.color, borderTopWidth: '3px' } : {}}
                          onClick={() => {
                            setViewingEntity(entity);
                          }}
                        >
                          <div className="flex justify-between items-start mb-4 pr-2">
                            <div className="flex items-center gap-3">
                              {entity.image && (
                                <img src={entity.image} alt={entity.name} className="w-10 h-10 rounded-full object-cover border border-stone-800 shrink-0" referrerPolicy="no-referrer" />
                              )}
                              <h3 className="text-xl font-bold line-clamp-1" style={{ color: entity.data?.color || '#34d399' }}>{entity.name}</h3>
                            </div>
                            <span className="text-xs font-mono uppercase tracking-wider bg-stone-800 text-stone-400 px-2 py-1 rounded-md shrink-0 ml-2">
                              {typeName}
                            </span>
                          </div>
                          
                          <p className="text-stone-400 text-sm line-clamp-4 mb-auto">
                            {entity.description || t.wiki_no_description}
                          </p>
                          
                          {entity.tags && (
                            <div className="flex flex-wrap gap-2 mt-4">
                              {entity.tags.split(',').slice(0, 3).map((tag: string, i: number) => (
                                <span key={i} className="flex items-center text-xs text-stone-500 bg-stone-950 px-2 py-1 rounded-full">
                                  <Hash size={10} className="mr-1" />
                                  {tag.trim()}
                                </span>
                              ))}
                              {entity.tags.split(',').length > 3 && (
                                <span className="text-xs text-stone-600 px-1 py-1">+{entity.tags.split(',').length - 3}</span>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
