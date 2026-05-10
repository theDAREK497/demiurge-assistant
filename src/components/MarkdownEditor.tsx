import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { MarkdownRenderer } from './MarkdownRenderer';
// @ts-ignore
import getCaretCoordinates from 'textarea-caret';

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: string;
}

const COMMANDS = [
  { id: 'h1', label: 'Заголовок 1', icon: 'H1', text: '# ' },
  { id: 'h2', label: 'Заголовок 2', icon: 'H2', text: '## ' },
  { id: 'h3', label: 'Заголовок 3', icon: 'H3', text: '### ' },
  { id: 'roll', label: 'Бросок кубиков', icon: '🎲', text: '1d20+0 ' },
  { id: 'npc', label: 'NPC / Персонаж', icon: '👤', text: '[[Имя NPC]]' },
  { id: 'loc', label: 'Локация', icon: '🗺️', text: '[[Локация]]' },
  { id: 'item', label: 'Предмет', icon: '💎', text: '[[Предмет]]' },
  { id: 'task', label: 'Задача', icon: '✅', text: '- [ ] ' },
  { id: 'quote', label: 'Цитата', icon: '💬', text: '> ' },
  { id: 'spoiler', label: 'Спойлер (Скрытый текст)', icon: '👀', text: '||скрытый текст||' },
  { id: 'table', label: 'Таблица', icon: '📊', text: '\n| Столбец 1 | Столбец 2 |\n|---|---|\n| Значение | Значение |\n' },
  { id: 'code', label: 'Код/Блок', icon: '💻', text: '\n```\nТекст\n```\n' },
];

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({ 
  value, 
  onChange, 
  placeholder,
  minHeight = '150px' 
}) => {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const [filter, setFilter] = useState('');
  const [slashIndex, setSlashIndex] = useState(-1);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredCommands = COMMANDS.filter(cmd => 
    cmd.id.includes(filter.toLowerCase()) || cmd.label.toLowerCase().includes(filter.toLowerCase())
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange(newValue);

    const cursor = e.target.selectionStart;
    const textBeforeCursor = newValue.substring(0, cursor);
    
    // Match the last occurrence of '/' that is preceded by space, newline, or is at string start
    const match = /(?:^|\s|\n)(\/)[^\s]*$/.exec(textBeforeCursor);

    if (match) {
      const matchIndex = match.index + (match[0].startsWith('/') ? 0 : 1);
      setSlashIndex(matchIndex);
      const query = textBeforeCursor.substring(matchIndex + 1);
      setFilter(query);
      
      const caret = getCaretCoordinates(e.target, cursor);
      // Let's add some offset for the textarea padding + roughly 20px down from text
      setMenuPosition({ top: caret.top + 24, left: caret.left });
      setMenuOpen(true);
      setSelectedIndex(0);
    } else {
      setMenuOpen(false);
    }
  };

  const executeCommand = (cmd: typeof COMMANDS[0]) => {
    if (!cmd || !textareaRef.current) return;
    const before = value.substring(0, slashIndex);
    const after = value.substring(textareaRef.current.selectionStart);
    
    const newValue = before + cmd.text + after;
    onChange(newValue);
    setMenuOpen(false);
    
    // Reset focus and cursor position after React completes the render
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        
        let newCursor = before.length + cmd.text.length;
        
        // If there is placeholder stuff like 'Имя NPC' or 'Локация', try to highlight it
        if (cmd.id === 'npc' || cmd.id === 'loc' || cmd.id === 'item') {
           const matchLen = cmd.text.length - 4; // '[[Имя NPC]]' -> length 11. Inside text is 7. 4 are brackets
           textareaRef.current.setSelectionRange(before.length + 2, before.length + 2 + matchLen);
        } else if (cmd.id === 'spoiler') {
           const matchLen = cmd.text.length - 4; // '||скрытый текст||' 
           textareaRef.current.setSelectionRange(before.length + 2, before.length + 2 + matchLen);
        } else if (cmd.id === 'task') {
           textareaRef.current.setSelectionRange(newCursor, newCursor);
        } else if (cmd.id === 'roll') {
           textareaRef.current.setSelectionRange(newCursor - 1, newCursor - 1);
        } else {
           textareaRef.current.setSelectionRange(newCursor, newCursor);
        }
      }
    }, 10);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!menuOpen) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % filteredCommands.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeCommand(filteredCommands[selectedIndex]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setMenuOpen(false);
    } else if (e.key === ' ' || e.key === 'Tab') {
      setMenuOpen(false);
    }
  };

  return (
    <div className="flex flex-col border border-stone-800 rounded-xl bg-stone-950 focus-within:border-emerald-500 transition-colors relative">
      <div className="flex bg-stone-900 border-b border-stone-800 rounded-t-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setActiveTab('edit')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'edit' 
              ? 'text-emerald-400 border-b-2 border-emerald-500' 
              : 'text-stone-400 hover:text-stone-200'
          }`}
        >
          {t.md_edit}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('preview')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'preview' 
              ? 'text-emerald-400 border-b-2 border-emerald-500' 
              : 'text-stone-400 hover:text-stone-200'
          }`}
        >
          {t.md_preview}
        </button>
      </div>
      
      <div className="p-0 relative" style={{ minHeight }}>
        {activeTab === 'edit' ? (
          <div className="w-full h-full relative" style={{ minHeight }}>
            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              onClick={() => setMenuOpen(false)}
              onBlur={() => {
                // Delay so click on menu item has time to fire
                setTimeout(() => setMenuOpen(false), 200);
              }}
              className="w-full h-full min-h-[150px] bg-transparent text-stone-200 p-4 focus:outline-none resize-y"
              placeholder={placeholder || 'Введите текст или нажмите / для списка команд...'}
              style={{ minHeight }}
            />
            {menuOpen && filteredCommands.length > 0 && (
              <div 
                className="absolute z-50 bg-stone-900 border border-stone-700 shadow-2xl rounded-xl w-64 overflow-hidden flex flex-col py-2"
                style={{
                  top: menuPosition.top,
                  left: menuPosition.left,
                }}
              >
                <div className="px-3 pb-2 text-xs font-bold text-stone-500 uppercase">
                  Commands
                </div>
                {filteredCommands.map((cmd, i) => (
                  <button
                    key={cmd.id}
                    className={`text-left px-4 py-2 flex items-center space-x-3 transition-colors ${
                      i === selectedIndex ? 'bg-emerald-600/20 text-emerald-400' : 'text-stone-200 hover:bg-stone-800'
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault(); // Prevent blur
                      executeCommand(cmd);
                    }}
                    onMouseEnter={() => setSelectedIndex(i)}
                  >
                    <span className="w-6 text-center text-lg">{cmd.icon}</span>
                    <span className="font-medium text-sm">{cmd.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div 
            className="w-full h-full min-h-[150px] p-4 prose prose-invert prose-emerald max-w-none overflow-auto"
            style={{ minHeight }}
          >
            {value ? (
              <MarkdownRenderer>{value}</MarkdownRenderer>
            ) : (
              <span className="text-stone-500 italic">{placeholder || '...'}</span>
            )}
          </div>
        )}
      </div>
      
      {activeTab === 'edit' && (
        <div className="bg-stone-900 px-4 py-2 text-xs text-stone-500 border-t border-stone-800 flex justify-between rounded-b-xl">
          <span>{t.md_help}</span>
          <span className="hidden sm:inline">Press <kbd className="bg-stone-800 px-1 rounded">/</kbd> for commands</span>
        </div>
      )}
    </div>
  );
};
