// Screening history kept in the browser only. DEMO: a real deployment would
// read this from the PHC's patient record system instead.

const KEY = 'retinascan-xai:history';
const MAX_ENTRIES = 8;

export function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(entries) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // Storage blocked or full; history is a convenience, not required.
  }
}

export function addHistoryEntry({ patientId, scanName, result }) {
  const entry = {
    patientId,
    scanName,
    gradeLabel: result.gradeLabel,
    severity: result.severity,
    tone: result.tone,
    confidence: result.confidence,
    at: new Date().toISOString(),
  };
  const next = [entry, ...loadHistory().filter((e) => e.patientId !== patientId)].slice(0, MAX_ENTRIES);
  persist(next);
  return next;
}

export function clearHistory() {
  persist([]);
  return [];
}
