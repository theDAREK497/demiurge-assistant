import { api } from '../api';

export const analyzeJournalLog = async (text: string) => {
  const res = await fetch('/api/analyze-journal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, universe_id: api.getUniverseId() }),
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.error || 'Failed to analyze journal');
  }

  return res.json();
};
