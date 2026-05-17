import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { Send, Bot, User, Plus, MessageSquare, Trash2, Menu, X } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  updated_at: string;
}

export const ChatView = () => {
  const { t } = useLanguage();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadSessions = async () => {
    try {
      const data = await api.getChatSessions();
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        loadSession(data[0].id);
      } else if (data.length === 0) {
        startNewChat();
      }
    } catch (error) {
      console.error('Failed to load chat sessions', error);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [api.getUniverseId()]);

  const loadSession = async (id: string) => {
    try {
      const session = await api.getChatSession(id);
      if (session) {
        setCurrentSessionId(session.id);
        setMessages(session.messages);
        if (window.innerWidth < 768) setShowSidebar(false);
      }
    } catch (error) {
      console.error('Failed to load chat session', error);
    }
  };

  const startNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    if (window.innerWidth < 768) setShowSidebar(false);
  };

  const deleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('Вы уверены, что хотите удалить этот чат?')) return;
    
    try {
      await api.deleteChatSession(id);
      if (currentSessionId === id) {
        startNewChat();
      }
      loadSessions();
    } catch (error) {
      console.error('Failed to delete chat session', error);
    }
  };

  const saveCurrentSession = async (msgs: Message[], overrideId?: string | null) => {
    const activeId = overrideId !== undefined ? overrideId : currentSessionId;
    const title = msgs.length > 0 ? (msgs[0].content.substring(0, 30) + (msgs[0].content.length > 30 ? '...' : '')) : 'Новый чат';
    const payload = {
      id: activeId,
      title,
      messages: msgs
    };
    
    try {
      const saved = await api.saveChatSession(payload);
      if (!activeId && saved.id) {
        setCurrentSessionId(saved.id);
        loadSessions();
        return saved.id;
      }
      loadSessions();
      return activeId;
    } catch (error) {
      console.error('Failed to save chat session', error);
      return activeId;
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (msgText: string) => {
    if (!msgText.trim() || isLoading) return;

    const newMessages: Message[] = [...messages, { role: 'user', content: msgText }];
    setMessages(newMessages);
    setIsLoading(true);

    let activeSessionId = currentSessionId;

    try {
      activeSessionId = await saveCurrentSession(newMessages, activeSessionId);
      
      const reply = await api.chat(newMessages);
      const updatedMessages: Message[] = [...newMessages, { role: 'assistant', content: reply }];
      setMessages(updatedMessages);
      activeSessionId = await saveCurrentSession(updatedMessages, activeSessionId);
    } catch (error: any) {
      const updatedMessages: Message[] = [...newMessages, { role: 'assistant', content: `Error: ${error.message}` }];
      setMessages(updatedMessages);
      activeSessionId = await saveCurrentSession(updatedMessages, activeSessionId);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput('');
    handleSendMessage(userMsg);
  };

  const quickPrompts = [
    { label: "👤 Сгенерируй NPC", prompt: "Пожалуйста, придумай случайного уникального NPC для этого мира. Дай ему имя, краткую историю и секрет. Выведи JSON блок для добавления его в entities." },
    { label: "🗺️ Новая локация", prompt: "Придумай интересную локацию, которую могли бы посетить игроки. Опиши её атмосферу и выведи JSON блок для добавления в entities." },
    { label: "⚔️ Идея квеста", prompt: "Сгенерируй завязку для нового квеста. В чем проблема, кто заказчик и какая награда? Выведи JSON блок для добавления квеста, используя существующую схему квестов." },
  ];

  return (
    <div className="flex h-full bg-stone-900 overflow-hidden relative">
      {/* Mobile Sidebar Overlay */}
      {showSidebar && (
        <div 
          className="md:hidden fixed inset-0 bg-black/50 z-20" 
          onClick={() => setShowSidebar(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`${showSidebar ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-300 absolute md:static inset-y-0 left-0 w-64 bg-stone-950 border-r border-stone-800 flex flex-col z-30`}>
        <div className="p-4 border-b border-stone-800 flex justify-between items-center bg-stone-950">
          <h2 className="text-stone-200 font-bold">История чатов</h2>
          <button 
            onClick={() => setShowSidebar(false)}
            className="md:hidden text-stone-400 hover:text-stone-200"
          >
            <X size={20} />
          </button>
        </div>
        
        <div className="p-4 border-b border-stone-800">
          <button 
            onClick={startNewChat}
            className="w-full flex justify-center items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white py-2 rounded-xl transition-colors"
          >
            <Plus size={18} />
            <span>Новый чат</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map(session => (
            <div 
              key={session.id}
              onClick={() => loadSession(session.id)}
              className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors ${currentSessionId === session.id ? 'bg-stone-800 text-stone-200' : 'text-stone-400 hover:bg-stone-800/50 hover:text-stone-300'}`}
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <MessageSquare size={16} className="shrink-0" />
                <span className="truncate text-sm font-medium">{session.title}</span>
              </div>
              <button 
                onClick={(e) => deleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 text-stone-500 hover:text-red-400 p-1 rounded transition-all shrink-0"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        <div className="md:hidden p-4 bg-stone-950 border-b border-stone-800 flex items-center gap-3">
          <button 
            onClick={() => setShowSidebar(true)}
            className="text-stone-400 hover:text-stone-200"
          >
            <Menu size={24} />
          </button>
          <h2 className="text-stone-200 font-bold truncate">
            {sessions.find(s => s.id === currentSessionId)?.title || 'Новый чат'}
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-stone-500">
              <p>{t.chat_placeholder}</p>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] md:max-w-[80%] flex gap-3 md:gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                  msg.role === 'user' ? 'bg-emerald-600' : 'bg-stone-700'
                }`}>
                  {msg.role === 'user' ? <User size={16} className="text-white md:w-5 md:h-5" /> : <Bot size={16} className="text-emerald-400 md:w-5 md:h-5" />}
                </div>
                <div className={`p-3 md:p-4 rounded-2xl flex flex-col gap-2 ${
                  msg.role === 'user' 
                    ? 'bg-emerald-600/20 text-emerald-100 rounded-tr-none' 
                    : 'bg-stone-800 text-stone-200 rounded-tl-none'
                }`}>
                  <div className="whitespace-pre-wrap font-sans text-sm overflow-x-auto">
                    <MarkdownRenderer>{msg.content}</MarkdownRenderer>
                  </div>
                  {msg.role === 'assistant' && (
                    <div className="flex gap-2 justify-end mt-1">
                      <button
                        onClick={async () => {
                          setIsLoading(true);
                          try {
                            const res = await api.extractEntities(msg.content);
                            alert(`Извлечено:\nEntities: ${res.counts.entities}\nEvents: ${res.counts.events}\nMap Nodes: ${res.counts.map_nodes}\nQuests: ${res.counts.quests}\nTables: ${res.counts.random_tables}\nBoards: ${res.counts.boards}`);
                          } catch (e: any) {
                            alert('Ошибка извлечения: ' + e.message);
                          }
                          setIsLoading(false);
                        }}
                        className="text-xs text-stone-400 hover:text-emerald-400 transition-colors bg-stone-900/50 px-2 py-1 rounded"
                        title="Извлечь информацию в Базу/Вики"
                      >
                        Заполнить Вики
                      </button>
                      <button
                        onClick={async () => {
                          if (isLoading) return;
                          
                          // Find the previous user message
                          let lastUserMsgIdx = -1;
                          for (let i = idx - 1; i >= 0; i--) {
                            if (messages[i].role === 'user') {
                              lastUserMsgIdx = i;
                              break;
                            }
                          }
                          
                          if (lastUserMsgIdx === -1) return;
                          
                          // Remove this assistant message and any subsequent messages
                          const newMessages = messages.slice(0, idx);
                          setMessages(newMessages);
                          setIsLoading(true);
                          
                          let activeSessionId = currentSessionId;
                          try {
                            activeSessionId = await saveCurrentSession(newMessages, activeSessionId);
                            const reply = await api.chat(newMessages);
                            const updatedMessages: Message[] = [...newMessages, { role: 'assistant', content: reply }];
                            setMessages(updatedMessages);
                            await saveCurrentSession(updatedMessages, activeSessionId);
                          } catch (error: any) {
                            const updatedMessages: Message[] = [...newMessages, { role: 'assistant', content: `Error: ${error.message}` }];
                            setMessages(updatedMessages);
                            await saveCurrentSession(updatedMessages, activeSessionId);
                          } finally {
                            setIsLoading(false);
                          }
                        }}
                        className="text-xs text-stone-400 hover:text-amber-400 transition-colors bg-stone-900/50 px-2 py-1 rounded"
                        title="Перегенерировать ответ"
                      >
                        Перегенерировать
                      </button>
                      <button
                        onClick={() => {
                          const newMsgs = [...messages];
                          newMsgs.splice(idx, 1);
                          setMessages(newMsgs);
                          saveCurrentSession(newMsgs, currentSessionId);
                        }}
                        className="text-xs text-stone-400 hover:text-red-400 transition-colors bg-stone-900/50 px-2 py-1 rounded"
                        title="Удалить сообщение"
                      >
                        Удалить
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-[85%] md:max-w-[80%] flex gap-3 md:gap-4 flex-row">
                <div className="w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-stone-700">
                  <Bot size={16} className="text-emerald-400 animate-pulse md:w-5 md:h-5" />
                </div>
                <div className="p-3 md:p-4 rounded-2xl bg-stone-800 text-stone-200 rounded-tl-none">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-stone-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-stone-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 bg-stone-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-stone-950 border-t border-stone-800">
          <div className="max-w-4xl mx-auto relative space-y-2">
            {/* Quick Prompts */}
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
              {quickPrompts.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(q.prompt)}
                  className="whitespace-nowrap bg-stone-800 hover:bg-stone-700 text-stone-300 text-sm px-3 py-1.5 rounded-full border border-stone-700 transition-colors shrink-0"
                >
                  {q.label}
                </button>
              ))}
            </div>

            <div className="relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={t.chat_placeholder}
                className="w-full bg-stone-900 border border-stone-700 rounded-2xl pl-4 pr-14 py-4 text-stone-200 focus:outline-none focus:border-emerald-500 resize-none h-16"
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="absolute right-2 top-2 bottom-2 w-12 flex items-center justify-center bg-emerald-600 hover:bg-emerald-500 disabled:bg-stone-800 disabled:text-stone-500 text-white rounded-xl transition-colors"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

