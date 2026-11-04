import { percent, GRADE_LABELS } from '../api.js';
import CaseImage from './CaseImage.jsx';

export default function HistoryList({ entries, onOpen }) {
  return (
    <ul className="case-list">
      {entries.map((c) => (
        <li key={c.case_id}>
          <button
            className="case-row"
            onClick={() => onOpen(c.case_id)}
            aria-label={`Open case for ${c.patient_id}`}
          >
            <CaseImage id={c.case_id} className="case-thumb" alt={`Scan for ${c.patient_id}`} />
            <span className="case-identity">
              <strong>{c.patient_id}</strong>
              <time dateTime={c.created_at}>{new Date(c.created_at).toLocaleString()}</time>
            </span>
            <span>
              {c.quality_ok ? (
                <>
                  {c.abstained && <small>Model’s tentative grade: </small>}
                  {c.grade_label}
                  <small>Calibrated confidence: {percent(c.confidence)}</small>
                </>
              ) : (
                'No grade — quality failed'
              )}
            </span>
            <span className="case-badges">
              {c.abstained && <span className="badge orange">Abstained</span>}
              {c.referable && <span className="badge orange">Referable</span>}
              {c.status === 'retake' && <span className="badge red">Retake</span>}
            </span>
            <span>
              {c.status}
              <small>
                {c.final_grade != null &&
                  `Final: ${c.final_grade} · ${GRADE_LABELS[c.final_grade]}`}
              </small>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
