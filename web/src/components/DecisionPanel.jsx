import { useState } from 'react';
import { GRADE_LABELS, postDecision } from '../api.js';
import { capitalise, formatDateTime, statusLabel } from '../format.js';

function lastReviewer() {
  try {
    return localStorage.getItem('retinascan-reviewer') || '';
  } catch {
    return '';
  }
}

const gradeText = (g) => (g == null ? '—' : `${g} ${GRADE_LABELS[g]}`);

export default function DecisionPanel({ result, onUpdated, onBusy }) {
  const [reviewer, setReviewer] = useState(lastReviewer);
  const [action, setAction] = useState('accept');
  const [grade, setGrade] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const p = result.prediction;
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (action === 'override' && grade === '') {
      setError('Select a final grade to override.');
      return;
    }
    setBusy(true);
    onBusy(true);
    setError('');
    setSaved(false);
    try {
      const updated = await postDecision(result.case_id, {
        action,
        reviewer: reviewer.trim(),
        note,
        ...(action === 'override' ? { final_grade: Number(grade) } : {}),
      });
      try {
        localStorage.setItem('retinascan-reviewer', reviewer.trim());
      } catch {
        /* optional convenience */
      }
      onUpdated(updated);
      setNote('');
      setSaved(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <section className="panel decision-panel" aria-labelledby="review-title">
      <div className="panel-head">
        <h2 id="review-title">Doctor review</h2>
        <span className="muted">
          {statusLabel(result.status)}
          {result.final_grade != null && ` · final grade ${gradeText(result.final_grade)}`}
        </span>
      </div>
      <div className="panel-body decision-grid">
        <form onSubmit={submit} className="review-form">
          <fieldset disabled={busy}>
            <legend className="sr-only">Reviewer decision</legend>
            <label className="field">
              <span>Reviewer name</span>
              <input
                required
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                autoComplete="name"
              />
            </label>
            <div className="radio-group" role="radiogroup" aria-label="Decision">
              <label className="radio">
                <input
                  type="radio"
                  name="action"
                  value="accept"
                  checked={action === 'accept'}
                  onChange={() => setAction('accept')}
                />
                <span>
                  Accept model grade <span className="muted">({gradeText(p?.grade)})</span>
                </span>
              </label>
              <label className="radio">
                <input
                  type="radio"
                  name="action"
                  value="override"
                  checked={action === 'override'}
                  onChange={() => setAction('override')}
                />
                <span>Override with grade</span>
                <select
                  aria-label="Final grade for override"
                  value={grade}
                  onChange={(e) => {
                    setGrade(e.target.value);
                    setAction('override');
                  }}
                >
                  <option value="">Select…</option>
                  {GRADE_LABELS.map((label, i) => (
                    <option value={i} key={label}>
                      {i} {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Note (optional)</span>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
            </label>
            <div className="action-row">
              <button className="btn btn-primary" type="submit">
                Save decision
              </button>
              {busy && <span role="status">Saving…</span>}
              {saved && !busy && (
                <span role="status" className="tone-green-text">
                  Decision saved.
                </span>
              )}
            </div>
          </fieldset>
          {error && (
            <p className="callout tone-red" role="alert">
              {error}
            </p>
          )}
        </form>
        <div>
          <h3 className="subhead">Decision history</h3>
          {result.decisions.length ? (
            <div className="table-scroll">
              <table className="table history-table">
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Reviewer</th>
                    <th scope="col">Action</th>
                    <th scope="col">Final grade</th>
                    <th scope="col">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {result.decisions.map((d) => (
                    <tr key={d.decision_id}>
                      <td className="nowrap">{formatDateTime(d.created_at)}</td>
                      <td>{d.reviewer}</td>
                      <td>{capitalise(d.action)}</td>
                      <td className="nowrap">{gradeText(d.final_grade)}</td>
                      <td>{d.note || <span className="muted">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No decisions recorded.</p>
          )}
        </div>
      </div>
    </section>
  );
}
