import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Plus, Trash2, Edit2, Save, X, Dices, Search, Filter } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { MarkdownEditor } from './MarkdownEditor';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionHelp } from './SectionHelp';

export const RandomTablesView = () => {
  const { t } = useLanguage();
  const [tables, setTables] = useState<any[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [rollResult, setRollResult] = useState<{tableId: string, result: string} | null>(null);
  const [wikiObjects, setWikiObjects] = useState<string[]>([]);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  const loadData = async () => {
    const [tablesData, entitiesData, mapNodesData] = await Promise.all([
      api.getRandomTables(),
      api.getEntities(),
      api.getMapNodes()
    ]);
    setTables(tablesData);
    
    const entityNames = entitiesData.map((e: any) => e.name);
    const nodeNames = mapNodesData.map((n: any) => n.name);
    setWikiObjects(Array.from(new Set([...entityNames, ...nodeNames])));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateNew = () => {
    setEditForm({ 
      name: '', 
      description: '', 
      type: 'general', 
      rollType: 'weight',
      entries: [{ weight: 1, roll: '1', result: '' }],
      conditions: [] 
    });
    setEditingId('new');
  };

  const handleEdit = (table: any) => {
    setEditingId(table.id);
    setEditForm({ ...table });
  };

  const handleSave = async () => {
    if (!editForm.name.trim()) {
      alert('Name is required');
      return;
    }
    await api.saveRandomTable(editForm);
    setEditingId(null);
    loadData();
  };

  const handleCancel = () => {
    setEditingId(null);
  };

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (deleteConfirmId === id) {
      await api.deleteRandomTable(id);
      setDeleteConfirmId(null);
      loadData();
    } else {
      setDeleteConfirmId(id);
      setTimeout(() => setDeleteConfirmId(null), 3000);
    }
  };

  const handleAddEntry = () => {
    setEditForm({
      ...editForm,
      entries: [...editForm.entries, { weight: 1, result: '' }]
    });
  };

  const handleUpdateEntry = (index: number, field: string, value: any) => {
    const newEntries = [...editForm.entries];
    newEntries[index] = { ...newEntries[index], [field]: value };
    setEditForm({ ...editForm, entries: newEntries });
  };

  const handleRemoveEntry = (index: number) => {
    const newEntries = editForm.entries.filter((_: any, i: number) => i !== index);
    setEditForm({ ...editForm, entries: newEntries });
  };

  const handleAddCondition = () => {
    setEditForm({
      ...editForm,
      conditions: [...(editForm.conditions || []), { type: 'location', value: '' }]
    });
  };

  const handleUpdateCondition = (index: number, field: string, value: any) => {
    const newConditions = [...editForm.conditions];
    newConditions[index] = { ...newConditions[index], [field]: value };
    setEditForm({ ...editForm, conditions: newConditions });
  };

  const handleRemoveCondition = (index: number) => {
    const newConditions = editForm.conditions.filter((_: any, i: number) => i !== index);
    setEditForm({ ...editForm, conditions: newConditions });
  };

  const rollTable = (table: any) => {
    if (!table.entries || table.entries.length === 0) return;
    
    if (table.rollType === 'dice') {
      const n = table.entries.length;
      const roll = Math.floor(Math.random() * n) + 1;
      const entry = table.entries[roll - 1];
      setRollResult({ tableId: table.id, result: `[Rolled ${roll}] ${entry.result}` });
    } else {
      const totalWeight = table.entries.reduce((sum: number, entry: any) => sum + (Number(entry.weight) || 1), 0);
      let roll = Math.random() * totalWeight;
      
      for (const entry of table.entries) {
        const weight = Number(entry.weight) || 1;
        if (roll < weight) {
          setRollResult({ tableId: table.id, result: entry.result });
          return;
        }
        roll -= weight;
      }
    }
  };

  const filteredTables = tables.filter(t => {
    const matchesSearch = t.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          (t.description && t.description.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesType = typeFilter === 'all' || t.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold text-stone-100 flex items-center">
          {t.tables_title}
          <SectionHelp content={
            <>
              <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Случайным таблицам</h3>
              <p>Раздел помогает генерировать случайные события, лут, НПС и другие элементы на лету.</p>
              <ul className="list-disc list-inside space-y-2 mt-2">
                <li><strong>Условия:</strong> При редактировании таблицы вы можете задать условия перевеса (например, "Ночь", "Дождь", "Уровень 5"). Если условие совпадает, может выпасть особый результат.</li>
                <li><strong>Бросок:</strong> Нажмите на иконку кубиков на карточке таблицы, чтобы сгенерировать случайную строку из списка её записей с учетом заданных условий (работает взвешенный шанс).</li>
              </ul>
            </>
          } />
        </h2>
        <button 
          onClick={handleCreateNew} 
          className="bg-emerald-600 hover:bg-emerald-500 text-white p-2 rounded-xl flex items-center transition-colors px-4"
        >
          <Plus size={20} className="mr-2" /> {t.tables_add}
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-500" size={18} />
          <input 
            type="text" 
            placeholder={t.tables_search || "Search tables..."}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-stone-900 border border-stone-800 rounded-xl pl-10 pr-4 py-2 text-stone-200 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-500" size={18} />
          <select 
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-stone-900 border border-stone-800 rounded-xl pl-10 pr-8 py-2 text-stone-200 focus:outline-none focus:border-emerald-500 appearance-none"
          >
            <option value="all">{t.tables_filter_all || "All Types"}</option>
            <option value="general">{t.tables_type_general}</option>
            <option value="weather">{t.tables_type_weather}</option>
            <option value="event">{t.tables_type_event}</option>
            <option value="loot">{t.tables_type_loot}</option>
            <option value="encounter">{t.tables_type_encounter}</option>
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 pb-8 auto-rows-[minmax(500px,1fr)]">
        {editingId === 'new' && (
          <TableEditor 
            editForm={editForm} 
            setEditForm={setEditForm} 
            onSave={handleSave} 
            onCancel={handleCancel}
            onAddEntry={handleAddEntry}
            onUpdateEntry={handleUpdateEntry}
            onRemoveEntry={handleRemoveEntry}
            onAddCondition={handleAddCondition}
            onUpdateCondition={handleUpdateCondition}
            onRemoveCondition={handleRemoveCondition}
            wikiObjects={wikiObjects}
            t={t}
          />
        )}

        {filteredTables.map(table => (
          editingId === table.id ? (
            <TableEditor 
              key={table.id}
              editForm={editForm} 
              setEditForm={setEditForm} 
              onSave={handleSave} 
              onCancel={handleCancel}
              onAddEntry={handleAddEntry}
              onUpdateEntry={handleUpdateEntry}
              onRemoveEntry={handleRemoveEntry}
              onAddCondition={handleAddCondition}
              onUpdateCondition={handleUpdateCondition}
              onRemoveCondition={handleRemoveCondition}
              wikiObjects={wikiObjects}
              t={t}
            />
          ) : (
            <div key={table.id} className="bg-stone-900 border border-stone-800 rounded-2xl p-6 flex flex-col h-full">
              <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-emerald-400">{table.name}</h3>
                    <span className="text-xs font-mono uppercase tracking-wider bg-stone-800 text-stone-400 px-2 py-1 rounded-md mt-2 inline-block">
                      {table.type === 'general' ? t.tables_type_general : 
                       table.type === 'weather' ? t.tables_type_weather : 
                       table.type === 'event' ? t.tables_type_event : 
                       table.type === 'loot' ? t.tables_type_loot : 
                       table.type === 'encounter' ? t.tables_type_encounter : table.type}
                    </span>
                  </div>
                  <div className="flex space-x-2 shrink-0">
                    <button onClick={() => rollTable(table)} className="p-2 text-indigo-400 hover:text-indigo-300 bg-indigo-900/30 rounded-lg" title={t.tables_roll_col}>
                      <Dices size={18} />
                    </button>
                    <button onClick={() => handleEdit(table)} className="p-2 text-stone-400 hover:text-emerald-400 bg-stone-800 rounded-lg">
                      <Edit2 size={18} />
                    </button>
                    <button onClick={(e) => handleDelete(table.id, e)} className="p-2 text-red-400 hover:text-red-300 bg-red-900/30 rounded-lg flex items-center">
                      <Trash2 size={18} />
                      {deleteConfirmId === table.id && <span className="ml-2 text-xs font-bold text-red-300">?</span>}
                    </button>
                  </div>
                </div>
                
                <div className="prose prose-invert prose-emerald prose-sm max-w-none mb-4">
                  {table.description ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {table.description}
                    </ReactMarkdown>
                  ) : (
                    <span className="text-stone-500 italic">{t.wiki_no_description}</span>
                  )}
                </div>
                
                {table.conditions && table.conditions.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-stone-500 uppercase mb-2">{t.tables_conditions}</h4>
                    <div className="flex flex-wrap gap-2">
                      {table.conditions.map((c: any, i: number) => (
                        <span key={i} className="text-xs bg-stone-800 text-stone-300 px-2 py-1 rounded">
                          {c.type === 'location' ? t.tables_cond_location : 
                           c.type === 'politics' ? t.tables_cond_politics : 
                           c.type === 'environment' ? t.tables_cond_environment : 
                           c.type === 'biome' ? t.tables_cond_biome : c.type}: {c.value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {rollResult?.tableId === table.id && (
                  <div className="bg-indigo-900/30 border border-indigo-500/50 rounded-lg p-4 mb-4 text-indigo-200">
                    <div className="text-xs text-indigo-400 uppercase mb-1">{t.tables_result_col}</div>
                    <div className="text-lg">{rollResult.result}</div>
                  </div>
                )}

                <div className="mt-auto bg-stone-950 rounded-lg p-4 flex-1 overflow-y-auto min-h-[200px]">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="text-stone-500 border-b border-stone-800">
                        <th className="pb-2 w-16">{table.rollType === 'dice' ? t.tables_roll_col : t.tables_weight}</th>
                        <th className="pb-2">{t.tables_result_col}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {table.entries?.map((entry: any, i: number) => (
                        <tr key={i} className="border-b border-stone-800/50 last:border-0">
                          <td className="py-2 text-stone-400">
                            {table.rollType === 'dice' ? i + 1 : entry.weight}
                          </td>
                          <td className="py-2 text-stone-300">{entry.result}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
            </div>
          )
        ))}
      </div>
    </div>
  );
};

const TableEditor = ({ 
  editForm, setEditForm, onSave, onCancel, 
  onAddEntry, onUpdateEntry, onRemoveEntry,
  onAddCondition, onUpdateCondition, onRemoveCondition,
  wikiObjects, t
}: any) => {
  return (
    <div className="bg-stone-900 border border-emerald-500 rounded-2xl p-6 col-span-full flex flex-col h-full">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <input 
          type="text" 
          value={editForm.name} 
          onChange={e => setEditForm({...editForm, name: e.target.value})}
          className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-emerald-400 font-bold w-full"
          placeholder={t.tables_name}
        />
        <select 
          value={editForm.type}
          onChange={e => setEditForm({...editForm, type: e.target.value})}
          className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-400 uppercase"
        >
          <option value="general">{t.tables_type_general}</option>
          <option value="weather">{t.tables_type_weather}</option>
          <option value="event">{t.tables_type_event}</option>
          <option value="loot">{t.tables_type_loot}</option>
          <option value="encounter">{t.tables_type_encounter}</option>
        </select>
        <select 
          value={editForm.rollType || 'weight'}
          onChange={e => setEditForm({...editForm, rollType: e.target.value})}
          className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-400 uppercase"
        >
          <option value="weight">{t.tables_roll_weight}</option>
          <option value="dice">{t.tables_roll_dice}</option>
        </select>
      </div>
      
      <MarkdownEditor 
        value={editForm.description}
        onChange={(val) => setEditForm({...editForm, description: val})}
        placeholder={t.tables_description}
        minHeight="100px"
      />

      <div className="mb-6 shrink-0 mt-4">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-sm font-bold text-stone-300">{t.tables_conditions}</h4>
          <button onClick={onAddCondition} className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center">
            <Plus size={14} className="mr-1" /> {t.tables_add_condition}
          </button>
        </div>
        <div className="space-y-2">
          {editForm.conditions?.map((c: any, i: number) => (
            <div key={i} className="flex gap-2 items-center">
              <select 
                value={c.type}
                onChange={e => onUpdateCondition(i, 'type', e.target.value)}
                className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-1 text-sm text-stone-400 w-1/3"
              >
                <option value="location">{t.tables_cond_location}</option>
                <option value="politics">{t.tables_cond_politics}</option>
                <option value="environment">{t.tables_cond_environment}</option>
                <option value="biome">{t.tables_cond_biome}</option>
              </select>
              <input 
                type="text" 
                value={c.value}
                onChange={e => onUpdateCondition(i, 'value', e.target.value)}
                className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-1 text-sm text-stone-300 flex-1"
                placeholder={t.tables_cond_value}
                list="wiki-objects"
              />
              <button onClick={() => onRemoveCondition(i)} className="text-red-400 hover:text-red-300 p-1">
                <X size={16} />
              </button>
            </div>
          ))}
          <datalist id="wiki-objects">
            {wikiObjects?.map((name: string, i: number) => (
              <option key={i} value={name} />
            ))}
          </datalist>
          {(!editForm.conditions || editForm.conditions.length === 0) && (
            <div className="text-xs text-stone-500 italic">{t.tables_no_conditions}</div>
          )}
        </div>
      </div>

      <div className="mb-6 flex-1 flex flex-col min-h-[200px]">
        <div className="flex justify-between items-center mb-2 shrink-0">
          <h4 className="text-sm font-bold text-stone-300">{t.tables_entries}</h4>
          <button onClick={onAddEntry} className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center">
            <Plus size={14} className="mr-1" /> {t.tables_add_entry}
          </button>
        </div>
        <div className="space-y-2 flex-1 overflow-y-auto pr-2">
          {editForm.entries?.map((entry: any, i: number) => (
            <div key={i} className="flex gap-2 items-start">
              {editForm.rollType === 'dice' ? (
                <div className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-2 text-sm text-stone-500 w-12 text-center flex items-center justify-center h-10 shrink-0">
                  {i + 1}
                </div>
              ) : (
                <input 
                  type="number" 
                  value={entry.weight}
                  onChange={e => onUpdateEntry(i, 'weight', Number(e.target.value))}
                  className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-2 text-sm text-stone-300 w-20 shrink-0"
                  placeholder={t.tables_weight}
                  min="1"
                />
              )}
              <textarea 
                value={entry.result}
                onChange={e => onUpdateEntry(i, 'result', e.target.value)}
                className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-2 text-sm text-stone-300 flex-1 h-10 resize-none"
                placeholder={t.tables_result}
              />
              <button onClick={() => onRemoveEntry(i)} className="text-red-400 hover:text-red-300 p-2 mt-1 shrink-0">
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end space-x-2 shrink-0 mt-auto">
        <button onClick={onCancel} className="px-4 py-2 text-stone-400 hover:text-stone-200 bg-stone-800 rounded-lg">
          {t.tables_cancel}
        </button>
        <button onClick={onSave} className="px-4 py-2 text-emerald-400 hover:text-emerald-300 bg-emerald-900/30 rounded-lg flex items-center">
          <Save size={18} className="mr-2" /> {t.tables_save}
        </button>
      </div>
    </div>
  );
};
