import React, { useState } from 'react';
import { HelpCircle, X } from 'lucide-react';

interface Props {
  content: React.ReactNode;
}

export const SectionHelp = ({ content }: Props) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button 
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className="ml-3 text-stone-500 hover:text-emerald-400 p-1 rounded-full hover:bg-stone-800 transition-colors inline-flex align-middle"
        title="Справка по разделу"
      >
        <HelpCircle size={22} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div 
            className="bg-stone-900 border border-emerald-500/50 rounded-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto relative shadow-2xl animate-in fade-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}
          >
            <button 
              onClick={() => setOpen(false)}
              className="absolute top-4 right-4 text-stone-500 hover:text-stone-300"
            >
              <X size={24} />
            </button>
            <div className="text-stone-300 space-y-4">
              {content}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
