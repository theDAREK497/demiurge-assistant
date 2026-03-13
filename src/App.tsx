import React, { useState, useEffect } from 'react';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';
import { Book, Map as MapIcon, Clock, MessageSquare, Settings as SettingsIcon, Menu, X, Dices } from 'lucide-react';
import { ChatView } from './components/ChatView';
import { WikiView } from './components/WikiView';
import { TimelineView } from './components/TimelineView';
import { MapView } from './components/MapView';
import { SettingsView } from './components/SettingsView';
import { RandomTablesView } from './components/RandomTablesView';
import { api } from './api';

const MainLayout = () => {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState('chat');
  const [isReady, setIsReady] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const init = async () => {
      let savedUniverseId = await api.getSettings('current_universe_id');
      
      const universes = await api.getUniverses();
      if (universes.length === 0) {
        const res = await api.createUniverse('Default Universe', 'My first universe');
        savedUniverseId = res.id;
        await api.saveSettings('current_universe_id', savedUniverseId);
      } else if (!savedUniverseId || !universes.find((u: any) => u.id === savedUniverseId)) {
        savedUniverseId = universes[0].id;
        await api.saveSettings('current_universe_id', savedUniverseId);
      }
      
      if (savedUniverseId) {
        api.setUniverseId(savedUniverseId);
      }
      setIsReady(true);
    };
    init();

    const handleNavigate = (e: CustomEvent) => {
      if (e.detail?.tab) {
        setActiveTab(e.detail.tab);
      }
    };
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  const tabs = [
    { id: 'chat', icon: MessageSquare, label: t.nav_chat },
    { id: 'wiki', icon: Book, label: t.nav_wiki },
    { id: 'timeline', icon: Clock, label: t.nav_timeline },
    { id: 'map', icon: MapIcon, label: t.nav_map },
    { id: 'tables', icon: Dices, label: t.nav_tables },
    { id: 'settings', icon: SettingsIcon, label: t.nav_settings },
  ];

  if (!isReady) {
    return <div className="flex h-screen bg-stone-900 items-center justify-center text-stone-400">{t.loading}</div>;
  }

  return (
    <div className="flex h-screen bg-stone-900 text-stone-100 font-sans flex-col md:flex-row">
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-stone-950 border-b border-stone-800 z-50">
        <h1 className="text-xl font-bold text-emerald-500 tracking-tight">{t.app_name}</h1>
        <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="text-stone-400 hover:text-stone-200">
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar */}
      <div className={`${mobileMenuOpen ? 'flex' : 'hidden'} md:flex w-full md:w-64 bg-stone-950 border-r border-stone-800 flex-col absolute md:relative z-40 h-[calc(100vh-60px)] md:h-full top-[60px] md:top-0`}>
        <div className="hidden md:block p-6">
          <h1 className="text-xl font-bold text-emerald-500 tracking-tight">{t.app_name}</h1>
        </div>
        <nav className="flex-1 px-4 py-4 md:py-0 space-y-2 overflow-y-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${
                  isActive 
                    ? 'bg-emerald-500/10 text-emerald-400' 
                    : 'text-stone-400 hover:bg-stone-800 hover:text-stone-200'
                }`}
              >
                <Icon size={20} />
                <span className="font-medium">{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-0">
        <main className="flex-1 overflow-y-auto">
          {activeTab === 'chat' && <ChatView />}
          {activeTab === 'wiki' && <WikiView />}
          {activeTab === 'timeline' && <TimelineView />}
          {activeTab === 'map' && <MapView />}
          {activeTab === 'tables' && <RandomTablesView />}
          {activeTab === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <LanguageProvider>
      <MainLayout />
    </LanguageProvider>
  );
}
