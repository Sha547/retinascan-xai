import { percent, GRADE_LABELS } from '../api.js';
import { formatDateTime, statusLabel } from '../format.js';
import CaseImage from './CaseImage.jsx';

function Flags({ c }) {
  const flags = [];
  if (c.abstained) flags.push(['Abstained', 'tone-amber']);
  if (c.referable && !c.abstained) flags.push(['Referable', 'tone-red']); // abstained: the doctor decides
  if (c.status === 'retake') flags.push(['Retake', 'tone-amber']);
  if (!flags.length) return <span className="muted">—</span>;
  return (
    <span className="flags">
      {flags.map(([label, tone]) => (
        <span key={label} className={`flag ${tone}`}>
          <span className="dot" aria-hidden="true" />
          {label}
        </span>
      ))}
    </span>
  );
}

/** Rows are rendered in the order the API returns them; never re-sorted here. */
export default function HistoryList({ entries, onOpen, numbered = true }) {
  return (
    <div className="table-scroll">
      <table className="table case-table">
        <thead>
          <tr>
            {numbered && (
              <th scope="col" className="num">
                #
              </th>
            )}
            <th scope="col">
              <span className="sr-only">Image</span>
            </th>
            <th scope="col">Patient ID</th>
            <th scope="col">Screened</th>
            <th scope="col">Model grade</th>
            <th scope="col" className="num">
              Confidence
            </th>
            <th scope="col">Flags</th>
            <th scope="col">Status</th>
            <th scope="col">Final grade</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((c, index) => (
            <tr key={c.case_id} onClick={() => onOpen(c.case_id)}>
              {numbered && <td className="num muted">{index + 1}</td>}
              <td className="thumb-cell">
                <CaseImage id={c.case_id} className="case-thumb" alt="" />
              </td>
              <td>
                <button
                  type="button"
                  className="row-link mono"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen(c.case_id);
                  }}
                  aria-label={`Open case ${c.case_id} for patient ${c.patient_id}`}
                >
                  {c.patient_id}
                </button>
              </td>
              <td className="nowrap">{formatDateTime(c.created_at)}</td>
              <td>
                {c.quality_ok && c.grade != null ? (
                  <span className={c.abstained ? 'tentative-text' : ''}>
                    <span className="num">{c.grade}</span> {c.grade_label}
                    {c.abstained && <span className="muted"> (tentative)</span>}
                  </span>
                ) : (
                  <span className="muted">No grade</span>
                )}
              </td>
              <td className="num">{c.quality_ok ? percent(c.confidence) : '—'}</td>
              <td>
                <Flags c={c} />
              </td>
              <td>{statusLabel(c.status)}</td>
              <td>
                {c.final_grade != null ? (
                  <>
                    <span className="num">{c.final_grade}</span> {GRADE_LABELS[c.final_grade]}
                  </>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
