import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { Clock, Edit2, Save, X, Plus, Trash2, ArrowLeft, GripVertical } from 'lucide-react';
import { MarkdownEditor } from './MarkdownEditor';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionHelp } from './SectionHelp';

export const TimelineView = () => {
  const { t } = useLanguage();
  const [events, setEvents] = useState<any[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [isCreating, setIsCreating] = useState(false);
  const [viewingEvent, setViewingEvent] = useState<any>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const loadEvents = async () => {
    const data = await api.getEvents();
    data.sort((a: any, b: any) => (a.order_index || 0) - (b.order_index || 0));
    setEvents(data);
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleEdit = (event: any, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingId(event.id);
    setEditForm({ ...event });
  };

  const handleSave = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    await api.saveEvent(editForm);
    setEditingId(null);
    setIsCreating(false);
    loadEvents();
    if (viewingEvent) {
      setViewingEvent({ ...editForm });
    }
  };

  const handleCancel = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingId(null);
    setIsCreating(false);
  };

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (deleteConfirmId === id) {
      await api.deleteEvent(id);
      setEditingId(null);
      setViewingEvent(null);
      setDeleteConfirmId(null);
      loadEvents();
    } else {
      setDeleteConfirmId(id);
      setTimeout(() => setDeleteConfirmId(null), 3000);
    }
  };

  const handleCreateNew = () => {
    const maxOrder = events.length > 0 ? Math.max(...events.map(e => e.order_index || 0)) : 0;
    setEditForm({ title: '', description: '', event_date: '', order_index: maxOrder + 10 });
    setIsCreating(true);
    setEditingId('new');
    setViewingEvent(null);
  };

  const handleDragStart = (e: React.DragEvent, id: string) => {
    if (editingId) {
      e.preventDefault();
      return;
    }
    setDraggedId(id);
    e.dataTransfer.effectAllowed = 'move';
    // Small delay to allow the drag image to be captured before adding opacity
    setTimeout(() => {
      const el = document.getElementById(`event-${id}`);
      if (el) el.classList.add('opacity-50');
    }, 0);
  };

  const handleDragEnd = (e: React.DragEvent, id: string) => {
    setDraggedId(null);
    const el = document.getElementById(`event-${id}`);
    if (el) el.classList.remove('opacity-50');
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = async (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    if (!draggedId || draggedId === targetId) return;

    const draggedIdx = events.findIndex(ev => ev.id === draggedId);
    const targetIdx = events.findIndex(ev => ev.id === targetId);
    
    if (draggedIdx === -1 || targetIdx === -1) return;

    const newEvents = [...events];
    const [dragged] = newEvents.splice(draggedIdx, 1);
    newEvents.splice(targetIdx, 0, dragged);

    // Re-assign order_index to maintain sequence
    const updatedEvents = newEvents.map((ev, idx) => ({ ...ev, order_index: idx * 10 }));
    setEvents(updatedEvents);
    
    // Save all updated events
    await Promise.all(updatedEvents.map(ev => api.saveEvent(ev)));
  };

  if (viewingEvent) {
    return (
      <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col overflow-y-auto">
        <button onClick={() => setViewingEvent(null)} className="flex items-center text-stone-400 hover:text-emerald-400 mb-6 transition-colors w-fit">
          <ArrowLeft size={20} className="mr-2" /> Back to Timeline
        </button>
        
        {editingId === viewingEvent.id ? (
          <div className="bg-stone-900 border border-emerald-500 rounded-2xl p-8 space-y-4">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <input 
                type="text" 
                value={editForm.title} 
                onChange={e => setEditForm({...editForm, title: e.target.value})}
                className="bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-emerald-400 font-bold text-2xl w-full"
                placeholder="Event Title"
              />
              <input 
                type="text" 
                value={editForm.event_date} 
                onChange={e => setEditForm({...editForm, event_date: e.target.value})}
                className="bg-stone-950 border border-stone-800 rounded-lg px-4 py-2 text-sm font-mono text-stone-400 w-full md:w-48"
                placeholder="Date (e.g. 1482 DR)"
              />
            </div>
            <MarkdownEditor 
              value={editForm.description}
              onChange={(val) => setEditForm({...editForm, description: val})}
              placeholder="Detailed description..."
              minHeight="250px"
            />
            <div className="flex justify-between items-center mt-6">
              <div className="flex items-center space-x-2">
                <span className="text-sm text-stone-500">Order Index:</span>
                <input 
                  type="number" 
                  value={editForm.order_index} 
                  onChange={e => setEditForm({...editForm, order_index: parseInt(e.target.value) || 0})}
                  className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-400 w-24"
                />
              </div>
              <div className="flex space-x-2">
                <button onClick={(e) => handleDelete(viewingEvent.id, e)} className="px-4 py-2 text-red-400 hover:text-red-300 bg-red-900/30 rounded-lg flex items-center">
                  <Trash2 size={18} className="mr-2" /> {deleteConfirmId === viewingEvent.id ? 'Are you sure?' : 'Delete'}
                </button>
                <button onClick={handleCancel} className="px-4 py-2 text-stone-400 hover:text-stone-200 bg-stone-800 rounded-lg flex items-center">
                  <X size={18} className="mr-2" /> Cancel
                </button>
                <button onClick={handleSave} className="px-4 py-2 text-emerald-400 hover:text-emerald-300 bg-emerald-900/30 rounded-lg flex items-center">
                  <Save size={18} className="mr-2" /> Save
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-stone-900 border border-stone-800 rounded-2xl p-8 relative group">
            <button 
              onClick={(e) => handleEdit(viewingEvent, e)}
              className="absolute top-6 right-6 p-2 text-stone-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity bg-stone-800 rounded-lg"
            >
              <Edit2 size={20} />
            </button>
            <div className="flex flex-col md:flex-row justify-between items-start mb-8 gap-4 pr-12">
              <h2 className="text-4xl font-bold text-emerald-400">{viewingEvent.title}</h2>
              <span className="text-sm font-mono text-stone-400 bg-stone-800 px-3 py-1 rounded-md">
                {viewingEvent.event_date}
              </span>
            </div>
            <div className="prose prose-invert prose-emerald max-w-none">
              {viewingEvent.description ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {viewingEvent.description}
                </ReactMarkdown>
              ) : (
                <p className="text-stone-500 italic">No description provided.</p>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-stone-100 flex items-center">
          {t.nav_timeline}
          <SectionHelp content={
            <>
              <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Хронологии</h3>
              <p>Здесь вы можете создать ленту событий, происходящих в вашей вселенной.</p>
              <ul className="list-disc list-inside space-y-2 mt-2">
                <li><strong>Индекс сортировки:</strong> При добавлении или редактировании карточки используйте "Order Index", чтобы расставить события по порядку. Обычно это год или эпоха.</li>
                <li><strong>Даты:</strong> Поле "Дата / Эра" является текстовым. Впишите туда любой удобный формат даты (например, "41 Месяц, 30 Эра", или "2077 год").</li>
                <li><strong>Скрытые события:</strong> Как и везде, в Хронологии могут быть секреты, не показываемые игрокам. (По умолчанию они показываются все, если не используется Режим Игрока). Установите галочку "secret", чтобы скрыть от игроков.</li>
                <li><strong>Быстрая смена порядка:</strong> Если список длинный, вы можете перетащить (drag-and-drop) событие, схватив за иконку с точками слева, чтобы автоматически обновить "Order Index".</li>
              </ul>
            </>
          } />
        </h2>
        <button 
          onClick={handleCreateNew} 
          className="bg-emerald-600 hover:bg-emerald-500 text-white p-2 rounded-xl flex items-center transition-colors px-4"
        >
          <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">Add Event</span>
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto relative pb-8">
        <div className="absolute left-4 md:left-8 top-0 bottom-0 w-px bg-stone-800"></div>
        
        <div className="space-y-8 relative">
          {isCreating && (
            <div className="flex items-start group">
              <div className="w-8 md:w-16 flex-shrink-0 flex justify-center mt-1 relative z-10">
                <div className="w-4 h-4 rounded-full bg-stone-900 border-2 border-emerald-500"></div>
              </div>
              <div className="flex-1 bg-stone-900 border border-emerald-500 rounded-2xl p-4 md:p-6 ml-2 md:ml-4">
                <div className="space-y-4">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
                    <input 
                      type="text" 
                      value={editForm.title} 
                      onChange={e => setEditForm({...editForm, title: e.target.value})}
                      className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-1 text-emerald-400 font-bold w-full"
                      placeholder="Event Title"
                    />
                    <input 
                      type="text" 
                      value={editForm.event_date} 
                      onChange={e => setEditForm({...editForm, event_date: e.target.value})}
                      className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-1 text-sm font-mono text-stone-400 w-full md:w-32 md:text-right"
                      placeholder="Date"
                    />
                  </div>
                  <textarea 
                    value={editForm.description}
                    onChange={e => setEditForm({...editForm, description: e.target.value})}
                    className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-300 h-24 resize-none"
                    placeholder="Event Description"
                  />
                  <div className="flex justify-between items-center mt-4">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-stone-500">Order Index:</span>
                      <input 
                        type="number" 
                        value={editForm.order_index} 
                        onChange={e => setEditForm({...editForm, order_index: parseInt(e.target.value) || 0})}
                        className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-1 text-xs text-stone-400 w-20"
                      />
                    </div>
                    <div className="flex space-x-2">
                      <button onClick={handleCancel} className="p-2 text-stone-400 hover:text-stone-200 bg-stone-800 rounded-lg">
                        <X size={16} />
                      </button>
                      <button onClick={handleSave} className="p-2 text-emerald-400 hover:text-emerald-300 bg-emerald-900/30 rounded-lg">
                        <Save size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {events.map((event, idx) => (
            <div 
              id={`event-${event.id}`}
              key={event.id} 
              draggable={!editingId}
              onDragStart={(e) => handleDragStart(e, event.id)}
              onDragEnd={(e) => handleDragEnd(e, event.id)}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, event.id)}
              className={`flex items-start group cursor-pointer transition-transform ${draggedId === event.id ? 'scale-95' : ''}`}
              onClick={() => {
                if (editingId !== event.id) {
                  setViewingEvent(event);
                }
              }}
            >
              <div className="w-8 md:w-16 flex-shrink-0 flex justify-center mt-1 relative z-10">
                <div className="w-4 h-4 rounded-full bg-stone-900 border-2 border-emerald-500 group-hover:bg-emerald-500 transition-colors"></div>
              </div>
              <div className="flex-1 bg-stone-900 border border-stone-800 rounded-2xl p-4 md:p-6 ml-2 md:ml-4 group-hover:border-emerald-500/50 transition-colors relative flex">
                {!editingId && (
                  <div className="mr-4 mt-1 text-stone-600 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing">
                    <GripVertical size={20} />
                  </div>
                )}
                <div className="flex-1">
                  {editingId === event.id ? (
                    <div className="space-y-4" onClick={e => e.stopPropagation()}>
                      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
                        <input 
                          type="text" 
                          value={editForm.title} 
                          onChange={e => setEditForm({...editForm, title: e.target.value})}
                          className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-1 text-emerald-400 font-bold w-full"
                          placeholder="Event Title"
                        />
                        <input 
                          type="text" 
                          value={editForm.event_date} 
                          onChange={e => setEditForm({...editForm, event_date: e.target.value})}
                          className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-1 text-sm font-mono text-stone-400 w-full md:w-32 md:text-right"
                          placeholder="Date"
                        />
                      </div>
                      <MarkdownEditor 
                        value={editForm.description}
                        onChange={(val) => setEditForm({...editForm, description: val})}
                        placeholder="Event Description"
                        minHeight="150px"
                      />
                      <div className="flex justify-between items-center mt-4">
                        <div className="flex items-center space-x-2">
                          <span className="text-xs text-stone-500">Order Index:</span>
                          <input 
                            type="number" 
                            value={editForm.order_index} 
                            onChange={e => setEditForm({...editForm, order_index: parseInt(e.target.value) || 0})}
                            className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-1 text-xs text-stone-400 w-20"
                          />
                        </div>
                        <div className="flex space-x-2">
                          <button onClick={(e) => handleDelete(event.id, e)} className="p-2 text-red-400 hover:text-red-300 bg-red-900/30 rounded-lg flex items-center">
                            <Trash2 size={16} />
                            {deleteConfirmId === event.id && <span className="ml-2 text-xs font-bold text-red-300">?</span>}
                          </button>
                          <button onClick={handleCancel} className="p-2 text-stone-400 hover:text-stone-200 bg-stone-800 rounded-lg">
                            <X size={16} />
                          </button>
                          <button onClick={handleSave} className="p-2 text-emerald-400 hover:text-emerald-300 bg-emerald-900/30 rounded-lg">
                            <Save size={16} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <button 
                        onClick={(e) => handleEdit(event, e)}
                        className="absolute top-4 right-4 p-2 text-stone-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity bg-stone-800 rounded-lg z-10"
                      >
                        <Edit2 size={16} />
                      </button>
                      <div className="flex justify-between items-baseline mb-2 pr-8">
                        <h3 className="text-xl font-bold text-emerald-400 line-clamp-1">{event.title}</h3>
                        <span className="text-sm font-mono text-stone-500 shrink-0 ml-2">{event.event_date}</span>
                      </div>
                      <div className="prose prose-invert prose-emerald prose-sm max-w-none line-clamp-3">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {event.description || ''}
                        </ReactMarkdown>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
          
          {!isCreating && events.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-stone-500">
              <Clock size={48} className="mb-4 opacity-20" />
              <p>No events found.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
