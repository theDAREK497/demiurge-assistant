import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Utility to parse custom syntax like dice rolls and spoilers
export const processMarkdown = (text: string) => {
  // Matches 1d20, 2d6+3, 1d100-5, etc.
  const diceRegex = /\b(\d+d\d+(?:[+-]\d+)?)\b/gi;
  let processed = text.replace(diceRegex, '[$1](#roll:$1)');
  
  // Matches ||spoiler text||
  const spoilerRegex = /\|\|([\s\S]*?)\|\|/g;
  processed = processed.replace(spoilerRegex, '[$1](#spoiler)');
  
  // Matches [[Wiki Page]]
  const wikiLinkRegex = /\[\[(.*?)\]\]/g;
  processed = processed.replace(wikiLinkRegex, (match, p1) => `[${p1}](#wiki:${encodeURIComponent(p1)})`);

  return processed;
};

export const rollDice = (formula: string) => {
  const match = formula.match(/^(\d+)d(\d+)(?:([+-])(\d+))?$/i);
  if (!match) return null;
  const count = parseInt(match[1]);
  const sides = parseInt(match[2]);
  const sign = match[3];
  const mod = parseInt(match[4] || '0');

  let rolls = [];
  let sum = 0;
  for (let i = 0; i < count; i++) {
    const r = Math.floor(Math.random() * sides) + 1;
    rolls.push(r);
    sum += r;
  }
  if (sign === '+') sum += mod;
  if (sign === '-') sum -= mod;

  return { formula, rolls, sum, mod: sign ? parseInt(sign + mod) : 0 };
};

const SpoilerText: React.FC<{children: React.ReactNode}> = ({children}) => {
  const [revealed, setRevealed] = useState(false);
  return (
    <span 
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setRevealed(!revealed); }}
      className={`cursor-pointer inline-block rounded px-1 transition-all duration-300 ${revealed ? 'bg-stone-800 text-stone-200' : 'bg-stone-700 text-transparent select-none hover:bg-stone-600'}`}
      title={revealed ? "Скрыть спойлер" : "Показать спойлер"}
    >
      <span className={revealed ? '' : 'opacity-0'}>{children}</span>
    </span>
  );
};

export const MarkdownRenderer: React.FC<{ children: string }> = ({ children }) => {
  const [lastRoll, setLastRoll] = useState<any>(null);

  const processedText = processMarkdown(children || '');

  const handleRoll = (formula: string) => {
    const result = rollDice(formula);
    if (result) {
      setLastRoll(result);
      setTimeout(() => setLastRoll(null), 3000);
    }
  };

  return (
    <div className="relative">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, href, children, ...props }) => {
            if (href === '#spoiler') {
              return <SpoilerText>{children}</SpoilerText>;
            }
            if (href?.startsWith('#roll:')) {
              const formula = href.replace('#roll:', '');
              return (
                <button 
                  onClick={(e) => { e.preventDefault(); handleRoll(formula); }} 
                  className="inline-flex items-center bg-stone-800 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-900/50 hover:bg-stone-700 transition-colors font-mono text-sm mx-1"
                  title="Бросить кубики"
                >
                  🎲 {children}
                </button>
              );
            }
            if (href?.startsWith('#wiki:')) {
              const name = decodeURIComponent(href.replace('#wiki:', ''));
              return (
                <button 
                  onClick={(e) => {
                    e.preventDefault();
                    window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'wiki', search: name } }));
                  }}
                  className="text-emerald-400 hover:text-emerald-300 underline decoration-emerald-500/30 hover:decoration-emerald-400 transition-colors"
                >
                  {children}
                </button>
              );
            }
            return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer" {...props}>{children}</a>;
          }
        }}
      >
        {processedText}
      </ReactMarkdown>

      {lastRoll && (
        <div className="fixed bottom-4 right-4 bg-stone-900 border border-emerald-500 rounded-xl p-4 shadow-2xl shadow-emerald-900/20 z-50 animate-in slide-in-from-bottom-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-stone-400 text-sm">Бросок: <span className="text-stone-200 font-mono">{lastRoll.formula}</span></span>
            <button onClick={() => setLastRoll(null)} className="text-stone-500 hover:text-stone-300">×</button>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-3xl font-bold text-emerald-400">{lastRoll.sum}</div>
            <div className="text-stone-500 text-sm">
              [{lastRoll.rolls.join(', ')}] {lastRoll.mod !== 0 ? (lastRoll.mod > 0 ? `+${lastRoll.mod}` : lastRoll.mod) : ''}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
