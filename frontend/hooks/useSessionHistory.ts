import { useEffect, useState, useCallback } from 'react';

export interface SessionRecord {
  id: string;
  query: string;
  completedAt: number;
  wordCount: number;
  sourceCount: number;
  confidence: number;
  synthesisPreview: string;
}

const STORAGE_KEY = 'nexora_session_history';
const MAX_HISTORY = 20;

export function useSessionHistory() {
  const [history, setHistory] = useState<SessionRecord[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHistory(JSON.parse(raw));
    } catch {}
  }, []);

  const addSession = useCallback((record: SessionRecord) => {
    setHistory((prev) => {
      const filtered = prev.filter((r) => r.id !== record.id);
      const updated = [record, ...filtered].slice(0, MAX_HISTORY);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(updated)); } catch {}
      return updated;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  return { history, addSession, clearHistory };
}
