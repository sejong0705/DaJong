import { useState, useCallback } from 'react';

const KEY = 'dawnair_listened';

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; }
  catch { return []; }
}

export function useListened() {
  const [listened, setListened] = useState(load);

  const markListened = useCallback((date) => {
    setListened(prev => {
      if (prev.includes(date)) return prev;
      const next = [...prev, date];
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  return { listened, markListened };
}