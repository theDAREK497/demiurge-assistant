import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { Search, Filter, Hash, Book, Edit2, Save, X, Plus, Trash2, ArrowLeft, Image as ImageIcon } from 'lucide-react';

export const WikiView = () => {
  const { t } = useLanguage();
  const [entities, setEntities] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterTag, setFilterTag] = useState<string>('all');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [viewingEntity, setViewingEntity] = useState<any>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const loadEntities = async () => {
    const data = await api.getEntities();
    setEntities(data);
  };

  useEffect(() => {
    loadEntities();
  }, []);

  // Effect to handle opening specific entity by ID from event
  useEffect(() => {
    const handleNavigate = async (e: CustomEvent) => {
      if (e.detail?.entityId) {
        try {
          const freshEntities = await api.getEntities();
          setEntities(freshEntities);
          const entity = freshEntities.find((ent: any) => ent.id === e.detail.entityId);
          if (entity) {
            setViewingEntity(entity);
          }
        } catch (err) {
          console.error("Failed to load entity", err);
        }
      }
    };
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  const renderDescription = (text: string) => {
    if (!text) return <p className="text-stone-500 italic">{t.wiki_no_description}</p>;
    
    const paragraphs = text.split('\n');
    return paragraphs.map((para, i) => {
      const parts = para.split(/(\[\[.*?\]\])/g);
      return (
        <p key={i} className="text-stone-300 leading-relaxed mb-4 whitespace-pre-wrap">
          {parts.map((part, j) => {
            if (part.startsWith('[[') && part.endsWith(']]')) {
              const entityName = part.slice(2, -2).trim();
              const linkedEntity = entities.find(e => e.name.toLowerCase() === entityName.toLowerCase());
              if (linkedEntity) {
                return (
                  <button 
                    key={j}
                    onClick={(e) => { e.stopPropagation(); setViewingEntity(linkedEntity); }}
                    className="text-emerald-400 hover:text-emerald-300 underline decoration-emerald-500/30 underline-offset-2 transition-colors font-medium"
                  >
                    {entityName}
                  </button>
                );
              }
              return <span key={j} className="text-stone-400 border-b border-dashed border-stone-600 cursor-help" title="Entity not found">{entityName}</span>;
            }
            return <span key={j}>{part}</span>;
          })}
        </p>
      );
    });
  };

  const types = ['all', 'npc', 'enemy', 'item', 'location', 'country', 'faction', 'settlement', 'pc'];
  const entityTypes = ['npc', 'enemy', 'item', 'location', 'country', 'faction', 'settlement', 'pc'];

  const allTags = Array.from(new Set(
    entities.flatMap(e => (e.tags || '').split(',').map((t: string) => t.trim()).filter(Boolean))
  )).sort();

  const filteredEntities = entities.filter(e => {
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
      await api.deleteEntity(id);
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

            <textarea 
              value={editForm.description}
              onChange={e => setEditForm({...editForm, description: e.target.value})}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-4 py-3 text-stone-300 h-64 resize-none"
              placeholder={t.wiki_description}
            />
            <input 
              type="text" 
              value={editForm.tags || ''} 
              onChange={e => setEditForm({...editForm, tags: e.target.value})}
              placeholder={t.wiki_tags}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-sm text-stone-400"
            />
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
            <button 
              onClick={(e) => handleEdit(viewingEntity, e)}
              className="absolute top-6 right-6 p-2 text-stone-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity bg-stone-800 rounded-lg"
            >
              <Edit2 size={20} />
            </button>
            <div className="flex flex-col md:flex-row justify-between items-start mb-8 gap-4 pr-12">
              <div className="flex items-center gap-4">
                {viewingEntity.image && (
                  <img src={viewingEntity.image} alt={viewingEntity.name} className="w-16 h-16 rounded-full object-cover border-2 border-stone-800" referrerPolicy="no-referrer" />
                )}
                <h2 className="text-4xl font-bold" style={{ color: viewingEntity.data?.color || '#34d399' }}>{viewingEntity.name}</h2>
              </div>
              <span className="text-sm font-mono uppercase tracking-wider bg-stone-800 text-stone-400 px-3 py-1 rounded-md">
                {t[`wiki_type_${viewingEntity.type}` as keyof typeof t] || viewingEntity.type}
              </span>
            </div>
            <div className="prose prose-invert prose-emerald max-w-none mb-8">
              {renderDescription(viewingEntity.description)}
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
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <h2 className="text-3xl font-bold text-stone-100">{t.wiki_title}</h2>
        
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
            
            <button 
              onClick={handleCreateNew} 
              className="bg-emerald-600 hover:bg-emerald-500 text-white p-2 rounded-xl flex items-center justify-center transition-colors px-4"
            >
              <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{t.wiki_add_new}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-8">
        {filteredEntities.map(entity => (
          <div 
            key={entity.id} 
            className="bg-stone-900 border border-stone-800 rounded-2xl p-6 hover:border-emerald-500/50 transition-colors group relative cursor-pointer flex flex-col h-64 overflow-hidden"
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
                {t[`wiki_type_${entity.type}` as keyof typeof t] || entity.type}
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
        
        {filteredEntities.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center py-20 text-stone-500">
            <Book size={48} className="mb-4 opacity-20" />
            <p>{t.wiki_no_entities}</p>
          </div>
        )}
      </div>
    </div>
  );
};
