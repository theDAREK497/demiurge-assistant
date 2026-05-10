import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { Download, Upload } from 'lucide-react';

export const SettingsView = () => {
  const { t, lang, setLang } = useLanguage();
  
  // Text AI Settings
  const [llmProvider, setLlmProvider] = useState('openai');
  const [llmEndpoint, setLlmEndpoint] = useState('http://localhost:1234/v1');
  const [llmModel, setLlmModel] = useState('local-model');
  const [llmApiKey, setLlmApiKey] = useState('');
  
  // Image AI Settings
  const [imageProvider, setImageProvider] = useState('sd');
  const [imageEndpoint, setImageEndpoint] = useState('http://127.0.0.1:7860');
  const [imageApiKey, setImageApiKey] = useState('');

  const [saved, setSaved] = useState(false);
  
  const [universes, setUniverses] = useState<any[]>([]);
  const [currentUniverseId, setCurrentUniverseId] = useState<string>('');
  const [newUniverseName, setNewUniverseName] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      const savedLlmProvider = await api.getSettings('llm_provider');
      if (savedLlmProvider) setLlmProvider(savedLlmProvider);

      const savedLlmEndpoint = await api.getSettings('llm_endpoint');
      if (savedLlmEndpoint) setLlmEndpoint(savedLlmEndpoint);
      
      const savedLlmModel = await api.getSettings('llm_model');
      if (savedLlmModel) setLlmModel(savedLlmModel);

      const savedLlmApiKey = await api.getSettings('llm_api_key');
      if (savedLlmApiKey) setLlmApiKey(savedLlmApiKey);

      const savedImageProvider = await api.getSettings('image_provider');
      if (savedImageProvider) setImageProvider(savedImageProvider);

      const savedImageEndpoint = await api.getSettings('image_endpoint');
      if (savedImageEndpoint) setImageEndpoint(savedImageEndpoint);

      const savedImageApiKey = await api.getSettings('image_api_key');
      if (savedImageApiKey) setImageApiKey(savedImageApiKey);
      
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
    await api.saveSettings('llm_provider', llmProvider);
    await api.saveSettings('llm_endpoint', llmEndpoint);
    await api.saveSettings('llm_model', llmModel);
    await api.saveSettings('llm_api_key', llmApiKey);
    
    await api.saveSettings('image_provider', imageProvider);
    await api.saveSettings('image_endpoint', imageEndpoint);
    await api.saveSettings('image_api_key', imageApiKey);

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

  const handleExport = async () => {
    try {
      const response = await fetch('/api/export');
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `demiurge-backup-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed', e);
      alert(t.settings_export_error);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!confirm(t.settings_import_warning)) {
      e.target.value = '';
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/import', {
        method: 'POST',
        body: formData
      });
      
      if (response.ok) {
        alert(t.settings_import_success);
        window.location.reload();
      } else {
        const err = await response.json();
        alert(`${t.settings_import_error}: ${err.error}`);
      }
    } catch (e) {
      console.error('Import failed', e);
      alert(t.settings_import_error);
    }
    e.target.value = '';
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

        <div className="pt-4 border-t border-stone-800">
          <h4 className="text-lg font-bold text-stone-200 mb-4">{t.settings_ai_text}</h4>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_provider}
              </label>
              <select 
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                <option value="openai">{t.settings_provider_openai}</option>
                <option value="gemini">{t.settings_provider_gemini}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_llm_endpoint}
              </label>
              <input 
                type="text"
                value={llmEndpoint}
                onChange={(e) => setLlmEndpoint(e.target.value)}
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
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
                placeholder="local-model"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_api_key}
              </label>
              <input 
                type="password"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
                placeholder="sk-..."
              />
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-stone-800">
          <h4 className="text-lg font-bold text-stone-200 mb-4">{t.settings_ai_image}</h4>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_provider}
              </label>
              <select 
                value={imageProvider}
                onChange={(e) => setImageProvider(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                <option value="sd">{t.settings_provider_sd}</option>
                <option value="openai">{t.settings_provider_dalle}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_image_endpoint}
              </label>
              <input 
                type="text"
                value={imageEndpoint}
                onChange={(e) => setImageEndpoint(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
                placeholder="http://127.0.0.1:7860"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-400 mb-2">
                {t.settings_api_key}
              </label>
              <input 
                type="password"
                value={imageApiKey}
                onChange={(e) => setImageApiKey(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-3 text-stone-200 focus:outline-none focus:border-emerald-500 transition-colors"
                placeholder="sk-..."
              />
            </div>
          </div>
        </div>

        <button 
          onClick={handleSave}
          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 px-4 rounded-xl transition-colors flex justify-center items-center mt-6"
        >
          {saved ? t.settings_saved : t.settings_save}
        </button>
      </div>

      <div className="space-y-6 bg-stone-900 p-6 rounded-2xl border border-stone-800 mb-8">
        <h3 className="text-xl font-bold text-emerald-400">{t.settings_export_import_title}</h3>
        <div className="flex flex-col sm:flex-row gap-4">
          <button 
            onClick={handleExport}
            className="flex-1 bg-stone-800 hover:bg-stone-700 text-stone-200 font-medium py-3 px-4 rounded-xl transition-colors flex justify-center items-center gap-2"
          >
            <Download size={18} />
            {t.settings_export_btn}
          </button>
          
          <label className="flex-1 bg-stone-800 hover:bg-stone-700 text-stone-200 font-medium py-3 px-4 rounded-xl transition-colors flex justify-center items-center gap-2 cursor-pointer">
            <Upload size={18} />
            {t.settings_import_btn}
            <input 
              type="file" 
              accept=".json" 
              className="hidden" 
              onChange={handleImport}
            />
          </label>
        </div>
        <p className="text-stone-500 text-sm">
          {t.settings_export_import_desc}
        </p>
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
