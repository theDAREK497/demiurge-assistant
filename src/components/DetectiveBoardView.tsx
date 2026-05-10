import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { useUndo } from '../contexts/UndoContext';
import { api } from '../api';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, addEdge, Node, Edge, Connection } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Plus, Trash2, ArrowLeft, Save, Sparkles } from 'lucide-react';
import { SectionHelp } from './SectionHelp';

export const DetectiveBoardView = () => {
  const { t } = useLanguage();
  const { addUndo } = useUndo();
  const [boards, setBoards] = useState<any[]>([]);
  const [currentBoard, setCurrentBoard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isGeneratingClue, setIsGeneratingClue] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    loadBoards();
  }, []);

  const loadBoards = async () => {
    setLoading(true);
    try {
      const data = await api.getBoards();
      setBoards(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBoard = async () => {
    const newBoard = { name: t.boards_new_name || 'New Board', data: { nodes: [], edges: [] } };
    const res = await api.saveBoard(newBoard);
    await loadBoards();
    const created = (await api.getBoards()).find((b: any) => b.id === res.id);
    if (created) openBoard(created);
  };

  const openBoard = (board: any) => {
    setCurrentBoard(board);
    setNodes(board.data?.nodes || []);
    setEdges(board.data?.edges || []);
  };

  const saveCurrentBoard = async () => {
    if (!currentBoard) return;
    const updated = { ...currentBoard, data: { nodes, edges } };
    await api.saveBoard(updated);
    loadBoards();
  };

  const onConnect = useCallback((params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const addNoteNode = () => {
    const newNode: Node = {
      id: `note-${Date.now()}`,
      type: 'default',
      position: { x: Math.random() * 200, y: Math.random() * 200 },
      data: { label: 'New Note' },
      style: { background: '#fef08a', color: '#000', border: '1px solid #ca8a04', borderRadius: '8px', padding: '10px', width: 150 }
    };
    setNodes((nds) => nds.concat(newNode));
  };

  const handleSuggestClue = async () => {
    setIsGeneratingClue(true);
    try {
      const prompt = `На основе текущего расследования (доски "${currentBoard.name}"), придумай одну интригующую зацепку, улику или секрет. 
Только текст секрета (1-2 коротких предложения), без системных сообщений, на русском языке.`;
      const reply = await api.chat([{ role: 'user', content: prompt }]);
      
      const newNode: Node = {
        id: `clue-${Date.now()}`,
        type: 'default',
        position: { x: Math.random() * 300 + 100, y: Math.random() * 300 + 100 },
        data: { label: reply },
        style: { background: '#fecaca', color: '#7f1d1d', border: '1px solid #ef4444', borderRadius: '8px', padding: '10px', width: 200 }
      };
      setNodes((nds) => nds.concat(newNode));
      
      addUndo("Генерация зацепки", async () => {
        setNodes((nds) => nds.filter(n => n.id !== newNode.id));
      });
      
    } catch (e: any) {
      console.error(e);
      alert('Ошибка при генерации улики: ' + e.message);
    } finally {
      setIsGeneratingClue(false);
    }
  };

  const handleDeleteBoard = async (id: string, name: string) => {
    if (confirm(t.boards_delete_confirm || 'Delete this board?')) {
      const boardToDelete = boards.find(b => b.id === id);
      await api.deleteBoard(id);
      
      if (boardToDelete) {
        addUndo(`Удаление доски "${name}"`, async () => {
          await api.saveBoard(boardToDelete);
          loadBoards();
        });
      }
      loadBoards();
    }
  };

  if (loading) return <div className="p-8 text-stone-400">{t.loading}</div>;

  if (currentBoard) {
    return (
      <div className="h-full flex flex-col relative">
        <div className="absolute top-4 left-4 z-10 flex gap-2 bg-stone-900/80 p-2 rounded-xl backdrop-blur-sm border border-stone-800">
          <button onClick={() => { saveCurrentBoard(); setCurrentBoard(null); }} className="text-stone-400 hover:text-stone-200 flex items-center px-3 py-2">
            <ArrowLeft size={20} className="mr-2" /> {t.boards_back || 'Back'}
          </button>
          <input 
            type="text" 
            value={currentBoard.name} 
            onChange={(e) => setCurrentBoard({...currentBoard, name: e.target.value})}
            className="bg-stone-950 border border-stone-700 rounded-lg px-3 py-1 text-stone-200 focus:outline-none focus:border-emerald-500"
          />
          <button onClick={saveCurrentBoard} className="text-emerald-400 hover:text-emerald-300 flex items-center px-3 py-2 bg-emerald-900/30 rounded-lg">
            <Save size={20} className="mr-2" /> {t.boards_save || 'Save'}
          </button>
          <button onClick={addNoteNode} className="text-stone-300 hover:text-white flex items-center px-3 py-2 bg-stone-800 rounded-lg">
            <Plus size={20} className="mr-2" /> {t.boards_add_note || 'Add Note'}
          </button>
          <button 
            onClick={handleSuggestClue} 
            disabled={isGeneratingClue}
            className="text-amber-400 hover:text-amber-300 flex items-center px-3 py-2 bg-amber-900/30 rounded-lg disabled:opacity-50 transition-colors"
          >
            <Sparkles size={20} className={`mr-2 ${isGeneratingClue ? 'animate-pulse' : ''}`} /> ИИ: Зацепка
          </button>
        </div>
        
        <div className="flex-1 w-full h-full bg-stone-950">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            colorMode="dark"
          >
            <Controls />
            <MiniMap nodeStrokeWidth={3} zoomable pannable />
            <Background color="#333" gap={16} />
          </ReactFlow>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto h-full flex flex-col">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-stone-100 flex items-center">
          {t.boards_title || 'Detective Boards'}
          <SectionHelp content={
            <>
              <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Доскам</h3>
              <p>Раздел <strong>Доски детектива</strong> позволяет создавать свободные схемы (mind-maps) для расследований, связей между бандами или планирования.</p>
              <ul className="list-disc list-inside space-y-2 mt-2">
                <li><strong>Узлы:</strong> Открыв доску, нажмите "Add Note", чтобы добавить текстовую карточку улики или события.</li>
                <li><strong>Связи:</strong> Перетащите линию от точки на границе одного узла к другому, чтобы соединить их.</li>
                <li><strong>Генерация улик:</strong> AI может помочь сгенерировать новую идею для зацепки на основе того, как называется текущая доска и существующие узлы.</li>
                <li><strong>Сохранение:</strong> Не забывайте сохранять изменения нажатием на кнопку Save!</li>
              </ul>
            </>
          } />
        </h2>
        <button onClick={handleCreateBoard} className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl flex items-center transition-colors">
          <Plus size={20} className="mr-2" /> {t.boards_create || 'Create Board'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {boards.map(board => (
          <div key={board.id} className="bg-stone-900 border border-stone-800 rounded-2xl p-6 hover:border-emerald-500/50 transition-colors cursor-pointer group" onClick={() => openBoard(board)}>
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-xl font-bold text-stone-200 group-hover:text-emerald-400 transition-colors">{board.name}</h3>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteBoard(board.id, board.name);
                }}
                className="text-stone-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Trash2 size={18} />
              </button>
            </div>
            <div className="text-stone-500 text-sm">
              {board.data?.nodes?.length || 0} nodes, {board.data?.edges?.length || 0} connections
            </div>
          </div>
        ))}
        {boards.length === 0 && (
          <div className="col-span-full text-center py-12 text-stone-500 border-2 border-dashed border-stone-800 rounded-2xl">
            {t.boards_empty || 'No boards yet. Create one to start investigating!'}
          </div>
        )}
      </div>
    </div>
  );
};
