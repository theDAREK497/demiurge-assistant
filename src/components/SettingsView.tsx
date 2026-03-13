import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';

export const SettingsView = () => {
  const { t, lang, setLang } = useLanguage();
  const [endpoint, setEndpoint] = useState('http://localhost:1234/v1');
  const [model, setModel] = useState('local-model');
  const [saved, setSaved] = useState(false);
  
  const [universes, setUniverses] = useState<any[]>([]);
  const [currentUniverseId, setCurrentUniverseId] = useState<string>('');
  const [newUniverseName, setNewUniverseName] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      const savedEndpoint = await api.getSettings('llm_endpoint');
      if (savedEndpoint) setEndpoint(savedEndpoint);
      
      const savedModel = await api.getSettings('llm_model');
      if (savedModel) setModel(savedModel);
      
      const data = await api.getUniverses();
      setUniverses(data);
      
      const savedUniverseId = api.getUniverseId();
      if (savedUniverseId) {
        setCurrentUniverseId(savedUniverseId);
      } else if (data.length > 0) {
        setCurrentUniverseId(data[0].id);
        api.setUniverseId(data[0].id);
      }
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    await api.saveSettings('llm_endpoint', endpoint);
    await api.saveSettings('llm_model', model);
    if (currentUniverseId) {
      await api.saveSettings('current_universe_id', currentUniverseId);
      api.setUniverseId(currentUniverseId);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleCreateUniverse = async () => {
    if (!newUniverseName.trim()) return;
    const res = await api.createUniverse(newUniverseName, '');
    const data = await api.getUniverses();
    setUniverses(data);
    setCurrentUniverseId(res.id);
    setNewUniverseName('');
    
    await api.saveSettings('current_universe_id', res.id);
    api.setUniverseId(res.id);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleSeedUniverse = async () => {
    const res = await api.seedUniverse();
    const data = await api.getUniverses();
    setUniverses(data);
    setCurrentUniverseId(res.id);
    
    await api.saveSettings('current_universe_id', res.id);
    api.setUniverseId(res.id);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleDeleteUniverse = async (id: string) => {
    if (deleteConfirmId === id) {
      await api.deleteUniverse(id);
      const data = await api.getUniverses();
      setUniverses(data);
      if (currentUniverseId === id) {
        const nextId = data.length > 0 ? data[0].id : '';
        setCurrentUniverseId(nextId);
        await api.saveSettings('current_universe_id', nextId);
        api.setUniverseId(nextId);
      }
      setDeleteConfirmId(null);
    } else {
      setDeleteConfirmId(id);
      setTimeout(() => setDeleteConfirmId(null), 3000);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h2 className="text-3xl font-bold mb-8 text-stone-100">{t.settings_title}</h2>
      
      <div className="space-y-6 bg-stone-900 p-6 rounded-2xl border border-stone-800 mb-8">
        <h3 className="text-xl font-bold text-emerald-400">{t.settings_universe_settings}</h3>
        
        <div>
          <label className="block text-sm font-medium text-stone-400 mb-2">
            {t.settings_current_universe}
          </label>
          <div className="flex gap-2">
            <select 
              value={currentUniverseId}
              onChange={async (e) => {
                const newId = e.target.value;
                setCurrentUniverseId(newId);
                if (newId) {
                  await api.saveSettings('current_universe_id', newId);
                  api.setUniverseId(newId);
                  setSaved(true);
                  setTimeout(() => setSaved(false), 3000);
                }
              }}
              className="flex-1 bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
            >
              <option value="">{t.settings_select_universe}</option>
              {universes.map(u => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            {currentUniverseId && (
              <button
                onClick={() => handleDeleteUniverse(currentUniverseId)}
                className="bg-red-900/30 hover:bg-red-900/50 text-red-400 font-medium py-3 px-4 rounded-xl transition-colors border border-red-900/50 flex items-center justify-center"
                title="Удалить вселенную"
              >
                {deleteConfirmId === currentUniverseId ? 'Удалить?' : 'Удалить'}
              </button>
            )}
          </div>
        </div>

        <div className="flex space-x-2">
          <input 
            type="text"
            value={newUniverseName}
            onChange={(e) => setNewUniverseName(e.target.value)}
            className="flex-1 bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
            placeholder={t.settings_new_universe_name}
          />
          <button 
            onClick={handleCreateUniverse}
            className="bg-stone-800 hover:bg-stone-700 text-white font-medium py-3 px-4 rounded-xl transition-colors"
          >
            {t.settings_create}
          </button>
        </div>

        <button 
          onClick={handleSeedUniverse}
          className="w-full bg-stone-800 hover:bg-stone-700 text-emerald-400 font-medium py-3 px-4 rounded-xl transition-colors border border-emerald-500/30"
        >
          {t.settings_generate_demo}
        </button>
      </div>

      <div className="space-y-6 bg-stone-900 p-6 rounded-2xl border border-stone-800 mb-8">
        <h3 className="text-xl font-bold text-emerald-400">{t.settings_app_settings}</h3>
        <div>
          <label className="block text-sm font-medium text-stone-400 mb-2">
            {t.settings_language}
          </label>
          <select 
            value={lang}
            onChange={(e) => setLang(e.target.value as 'ru' | 'en')}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
          >
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-stone-400 mb-2">
            {t.settings_llm_endpoint}
          </label>
          <input 
            type="text"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
            placeholder="http://localhost:1234/v1"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-stone-400 mb-2">
            {t.settings_llm_model}
          </label>
          <input 
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
            placeholder="local-model"
          />
        </div>

        <button 
          onClick={handleSave}
          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 px-4 rounded-xl transition-colors flex justify-center items-center"
        >
          {saved ? t.settings_saved : t.settings_save}
        </button>
      </div>

      <div className="space-y-6 bg-stone-900 p-6 rounded-2xl border border-stone-800">
        <h3 className="text-xl font-bold text-emerald-400">{t.settings_help_title}</h3>
        <div className="text-stone-300 space-y-4 text-sm leading-relaxed">
          <p>{t.settings_help_intro}</p>
          
          <h4 className="text-lg font-semibold text-stone-200 mt-4">{t.settings_help_step1_title}</h4>
          <ol className="list-decimal list-inside space-y-2 ml-2">
            <li>{t.settings_help_step1_1}</li>
            <li>{t.settings_help_step1_2}</li>
            <li>{t.settings_help_step1_3}</li>
            <li>{t.settings_help_step1_4}</li>
            <li>{t.settings_help_step1_5}</li>
            {t.settings_help_step1_6 && <li>{t.settings_help_step1_6}</li>}
          </ol>

          <h4 className="text-lg font-semibold text-stone-200 mt-4">{t.settings_help_step2_title}</h4>
          <ol className="list-decimal list-inside space-y-2 ml-2">
            <li>{t.settings_help_step2_1}</li>
            <li>{t.settings_help_step2_2}</li>
            <li>{t.settings_help_step2_3}</li>
            <li>{t.settings_help_step2_4}</li>
            <li>{t.settings_help_step2_5}</li>
            <li>{t.settings_help_step2_6}</li>
            <li>{t.settings_help_step2_7}</li>
          </ol>

          <h4 className="text-lg font-semibold text-stone-200 mt-4">{t.settings_help_step3_title}</h4>
          <ol className="list-decimal list-inside space-y-2 ml-2">
            <li>{t.settings_help_step3_1}</li>
            <li>{t.settings_help_step3_2}</li>
            <li>{t.settings_help_step3_3}</li>
            <li>{t.settings_help_step3_4}</li>
            <li>{t.settings_help_step3_5}</li>
          </ol>
        </div>
      </div>
    </div>
  );
};
