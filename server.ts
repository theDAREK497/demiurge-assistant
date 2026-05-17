import React, { useState, useEffect } from 'react';
import { Database, Play, AlertCircle, RefreshCw } from 'lucide-react';

export const DatabaseView = () => {
  const [query, setQuery] = useState('SELECT * FROM entities LIMIT 10;');
  const [results, setResults] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tables, setTables] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchTables = async () => {
    try {
      const res = await fetch('/api/db/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'" })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setTables(data.results.map((r: any) => r.name));
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    fetchTables();
  }, []);

  const runQuery = async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await fetch('/api/db/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResults(data.results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-stone-900 text-stone-200">
      <div className="p-4 md:p-6 border-b border-stone-800 flex justify-between items-center bg-stone-950">
        <h2 className="text-2xl font-bold text-amber-500 flex items-center space-x-2">
          <Database className="w-6 h-6" />
          <span>Режим Разработчика (База Данных)</span>
        </h2>
      </div>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Sidebar */}
        <div className="w-full md:w-64 border-r border-stone-800 bg-stone-950/50 p-4 flex flex-col overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-semibold text-stone-400 text-sm uppercase tracking-wider">Таблицы</h3>
            <button onClick={fetchTables} className="text-stone-500 hover:text-emerald-400 transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="space-y-1">
            {tables.map(table => (
              <button
                key={table}
                onClick={() => setQuery(`SELECT * FROM ${table} LIMIT 50;`)}
                className="w-full text-left px-3 py-2 rounded bg-stone-900 hover:bg-stone-800 text-sm text-stone-300 font-mono transition-colors"
              >
                {table}
              </button>
            ))}
          </div>
        </div>

        {/* Editor & Results */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="p-4 border-b border-stone-800 bg-stone-900 flex flex-col h-1/3 min-h-[200px]">
            <label className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">SQL Запрос</label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 w-full bg-stone-950 border border-stone-800 rounded-lg p-3 font-mono text-sm text-emerald-400 resize-none focus:outline-none focus:border-emerald-500/50"
              placeholder="SELECT * FROM entities"
              spellCheck={false}
            />
            <div className="mt-3 flex justify-end">
              <button
                onClick={runQuery}
                disabled={isLoading}
                className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors"
              >
                <Play size={16} />
                <span>Выполнить</span>
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto bg-stone-950 p-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-lg flex items-start space-x-3">
                <AlertCircle size={20} className="shrink-0 mt-0.5" />
                <div className="text-sm font-mono whitespace-pre-wrap">{error}</div>
              </div>
            )}
            
            {results && !error && (
              <div className="overflow-x-auto">
                <div className="text-xs text-stone-500 mb-2">Найдено строк: {results.length}</div>
                {results.length > 0 ? (
                  <table className="min-w-full text-left text-sm border-collapse">
                    <thead>
                      <tr>
                        {Object.keys(results[0]).map(key => (
                          <th key={key} className="border border-stone-800 bg-stone-900 px-3 py-2 font-semibold text-stone-400 whitespace-nowrap">
                            {key}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((row, i) => (
                        <tr key={i} className="hover:bg-stone-900/50 transition-colors">
                          {Object.keys(row).map(key => (
                            <td key={key} className="border border-stone-800 px-3 py-2 font-mono text-stone-300 max-w-xs truncate" title={String(row[key])}>
                              {row[key] === null ? <span className="text-stone-600 italic">null</span> : String(row[key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-stone-500 italic text-sm">Нет данных</div>
                )}
              </div>
            )}
            
            {!results && !error && !isLoading && (
              <div className="text-stone-600 text-center mt-10 flex flex-col items-center">
                <Database size={48} className="mb-4 opacity-20" />
                <p>Нажмите «Выполнить» чтобы получить данные из БД</p>
                <p className="text-sm mt-2">Только чтение! (Хотя можно и удалять, если вы храбрец)</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
