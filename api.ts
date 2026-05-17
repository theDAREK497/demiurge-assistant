import React, { useState, useEffect } from 'react';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';
import { UndoProvider, useUndo } from './contexts/UndoContext';
import { PlayerModeProvider, usePlayerMode } from './contexts/PlayerModeContext';
import { Book, Map as MapIcon, Clock, MessageSquare, Settings as SettingsIcon, Menu, X, Dices, ScrollText, Network, HelpCircle, Undo2, Eye, EyeOff, Database } from 'lucide-react';
import { ChatView } from './components/ChatView';
import { WikiView } from './components/WikiView';
import { TimelineView } from './components/TimelineView';
import { MapView } from './components/MapView';
import { SettingsView } from './components/SettingsView';
import { RandomTablesView } from './components/RandomTablesView';
import { JournalView } from './components/JournalView';
import { QuestBoardView } from './components/QuestBoardView';
import { DetectiveBoardView } from './components/DetectiveBoardView';
import { HelpView } from './components/HelpView';
import { api } from './api';

import { DatabaseView } from './components/DatabaseView';

const GlobalUndoButton = () => {
  const { hasUndo, popUndo, undoStack } = useUndo();
  
  if (!hasUndo) return null;
  const lastAction = undoStack[undoStack.length - 1];

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <button
        onClick={popUndo}
        className="bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-600 shadow-xl px-4 py-3 rounded-full flex items-center space-x-2 transition-all hover:scale-105"
        title="Отменить последнее действие"
      >
        <Undo2 size={20} className="text-emerald-400" />
        <span className="font-medium text-sm">Отменить: {lastAction.label}</span>
      </button>
    </div>
  );
};

const PlayerModeToggle = () => {
  const { isPlayerMode, setIsPlayerMode } = usePlayerMode();
  
  return (
    <button
      onClick={() => setIsPlayerMode(!isPlayerMode)}
      className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition-colors border ${
        isPlayerMode 
          ? 'bg-amber-500/10 text-amber-500 border-amber-500/30' 
          : 'bg-stone-800 text-stone-400 border-stone-700 hover:text-stone-200'
      }`}
    >
      <div className="flex items-center space-x-3">
        {isPlayerMode ? <Eye size={20} /> : <EyeOff size={20} />}
        <span className="font-medium truncate">{isPlayerMode ? 'Режим Игрока' : 'Режим Мастера'}</span>
      </div>
      <div className={`w-8 h-4 rounded-full flex items-center px-1 transition-colors ${isPlayerMode ? 'bg-amber-500/30' : 'bg-stone-700'}`}>
        <div className={`w-2 h-2 rounded-full bg-current transition-transform ${isPlayerMode ? 'translate-x-4' : 'translate-x-0'}`} />
      </div>
    </button>
  );
};

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
      (window as any).__lastNavigateDetail = e.detail;
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
    { id: 'journal', icon: ScrollText, label: t.nav_journal },
    { id: 'quests', icon: Book, label: t.nav_quests },
    { id: 'boards', icon: Network, label: t.boards_title || 'Boards' },
    { id: 'database', icon: Database, label: 'Режим Разработчика' },
    { id: 'settings', icon: SettingsIcon, label: t.nav_settings },
    { id: 'help', icon: HelpCircle, label: t.help_title || 'Help' },
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
      <div className={`${mobileMenuOpen ? 'flex' : 'hidden'} md:flex w-full md:w-72 bg-stone-950 border-r border-stone-800 flex-col absolute md:relative z-40 h-[calc(100vh-60px)] md:h-full top-[60px] md:top-0`}>
        <div className="hidden md:block p-6">
          <h1 className="text-xl font-bold text-emerald-500 tracking-tight">{t.app_name}</h1>
        </div>
        <nav className="flex-1 px-4 py-4 md:py-0 space-y-2 overflow-y-auto w-full">
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
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors text-left text-sm lg:text-base ${
                  isActive 
                    ? 'bg-emerald-500/10 text-emerald-400' 
                    : 'text-stone-400 hover:bg-stone-800 hover:text-stone-200'
                }`}
              >
                <Icon size={20} className="shrink-0" />
                <span className="font-medium leading-tight whitespace-normal text-left">{tab.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="p-4 border-t border-stone-800">
          <PlayerModeToggle />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-0">
        <main className="flex-1 overflow-y-auto">
          {activeTab === 'chat' && <ChatView />}
          {activeTab === 'wiki' && <WikiView />}
          {activeTab === 'timeline' && <TimelineView />}
          {activeTab === 'map' && <MapView />}
          {activeTab === 'tables' && <RandomTablesView />}
          {activeTab === 'journal' && <JournalView />}
          {activeTab === 'quests' && <QuestBoardView />}
          {activeTab === 'boards' && <DetectiveBoardView />}
          {activeTab === 'database' && <DatabaseView />}
          {activeTab === 'settings' && <SettingsView />}
          {activeTab === 'help' && <HelpView />}
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <LanguageProvider>
      <PlayerModeProvider>
        <UndoProvider>
          <MainLayout />
          <GlobalUndoButton />
        </UndoProvider>
      </PlayerModeProvider>
    </LanguageProvider>
  );
}
