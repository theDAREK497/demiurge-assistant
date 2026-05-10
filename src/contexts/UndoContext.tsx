import React, { createContext, useContext, useState, ReactNode, useCallback } from 'react';

type UndoAction = {
  id: string;
  label: string;
  undo: () => Promise<void>;
};

interface UndoContextType {
  addUndo: (label: string, undoFn: () => Promise<void>) => void;
  popUndo: () => Promise<void>;
  hasUndo: boolean;
  clearUndo: () => void;
  undoStack: UndoAction[];
}

const UndoContext = createContext<UndoContextType | undefined>(undefined);

export const UndoProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [undoStack, setUndoStack] = useState<UndoAction[]>([]);

  const addUndo = useCallback((label: string, undoFn: () => Promise<void>) => {
    setUndoStack(prev => [...prev, { id: Date.now().toString() + Math.random().toString(), label, undo: undoFn }]);
  }, []);

  const popUndo = useCallback(async () => {
    if (undoStack.length === 0) return;
    const lastAction = undoStack[undoStack.length - 1];
    
    setUndoStack(prev => prev.slice(0, -1));
    
    try {
      await lastAction.undo();
      window.dispatchEvent(new CustomEvent('data-refresh'));
    } catch (e) {
      console.error("Undo failed", e);
      setUndoStack(prev => [...prev, lastAction]);
      alert("Не удалось отменить действие.");
    }
  }, [undoStack]);

  const clearUndo = useCallback(() => {
    setUndoStack([]);
  }, []);

  return (
    <UndoContext.Provider value={{ addUndo, popUndo, hasUndo: undoStack.length > 0, clearUndo, undoStack }}>
      {children}
    </UndoContext.Provider>
  );
};

export const useUndo = () => {
  const context = useContext(UndoContext);
  if (!context) throw new Error('useUndo must be used within UndoProvider');
  return context;
};
