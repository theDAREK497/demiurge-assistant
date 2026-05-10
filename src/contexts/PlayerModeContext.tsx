import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface PlayerModeContextType {
  isPlayerMode: boolean;
  setIsPlayerMode: (isPlayer: boolean) => void;
}

const PlayerModeContext = createContext<PlayerModeContextType | undefined>(undefined);

export const PlayerModeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isPlayerMode, setIsPlayerModeState] = useState<boolean>(false);

  useEffect(() => {
    const savedMode = localStorage.getItem('user_mode');
    if (savedMode === 'player') {
      setIsPlayerModeState(true);
    }
  }, []);

  const setIsPlayerMode = (isPlayer: boolean) => {
    setIsPlayerModeState(isPlayer);
    if (isPlayer) {
      localStorage.setItem('user_mode', 'player');
    } else {
      localStorage.setItem('user_mode', 'gm');
    }
  };

  return (
    <PlayerModeContext.Provider value={{ isPlayerMode, setIsPlayerMode }}>
      {children}
    </PlayerModeContext.Provider>
  );
};

export const usePlayerMode = () => {
  const context = useContext(PlayerModeContext);
  if (!context) throw new Error('usePlayerMode must be used within PlayerModeProvider');
  return context;
};
