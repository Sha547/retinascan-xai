import { useState } from 'react';
import { GRADE_LABELS, postDecision } from '../api.js';

function lastReviewer() { try { return localStorage.getItem('retinascan-reviewer') || ''; } catch { return ''; } }

export default function DecisionPanel({ result, onUpdated, onBusy }) {
  const [reviewer, setReviewer] = useState(lastReviewer);
  const [grade, setGrade] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  async function submit(event) {
    event.preventDefault();
    const action = event.nativeEvent.submitter?.value;
    if (!action || busy) return;
    if (action === 'override' && grade === '') { setError('Select a final grade to override.'); return; }
    setBusy(true); onBusy(true); setError(''); setSaved(false);
    try {
      const updated = await postDecision(result.case_id, { action, reviewer: reviewer.trim(), note,
        ...(action === 'override' ? { final_grade: Number(grade) } : {}) });
      try { localStorage.setItem('retinascan-reviewer', reviewer.trim()); } catch { /* optional convenience */ }
      onUpdated(updated); setNote(''); setSaved(true);
    } catch (e) { setError(e.message); } finally { setBusy(false); onBusy(false); }
  }
  return <section className="card decision-panel"><h2>Doctor review</h2>
    <p>Current status: {result.status}{result.final_grade != null && ` · Final grade: ${result.final_grade} · ${GRADE_LABELS[result.final_grade]}`}</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy} className="review-fields"><legend>Reviewer decision</legend>
        <label>Reviewer name<input required value={reviewer} onChange={e => setReviewer(e.target.value)} autoComplete="name" /></label>
        <label>Final grade for override<select value={grade} onChange={e => setGrade(e.target.value)}><option value="">Choose a grade</option>
          {GRADE_LABELS.map((label, i) => <option value={i} key={label}>{i} · {label}</option>)}</select></label>
        <label className="wide-field">Note (optional)<textarea value={note} onChange={e => setNote(e.target.value)} rows={3} /></label>
        <div className="review-actions wide-field"><button className="btn btn-primary" type="submit" value="accept">Accept model grade</button>
          <button className="btn btn-ghost" type="submit" value="override">Override grade</button>{busy && <span role="status">Saving decision…</span>}</div>
      </fieldset>
      {error && <p className="notice error" role="alert">{error}</p>}
    </form>
    {saved && <p className="notice" role="status">Decision saved.</p>}
    <h3>Decision history</h3>
    {result.decisions.length ? <ol className="decision-history">{result.decisions.map(d => <li key={d.decision_id}>
      <strong>{d.reviewer} · {d.action} · Final grade {d.final_grade} ({GRADE_LABELS[d.final_grade]})</strong>
      <time dateTime={d.created_at}>{new Date(d.created_at).toLocaleString()}</time>{d.note && <p>{d.note}</p>}
    </li>)}</ol> : <p>No decisions yet.</p>}
  </section>;
}
