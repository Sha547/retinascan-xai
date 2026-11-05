import { eyeLabel, formatDateTime, statusLabel } from '../format.js';

/** EMR-style case header. All values come from the Case object. */
export default function RecordHeader({ result, onBack, backLabel = 'Back to queue', busy }) {
  return (
    <div className="record-header">
      <dl>
        <div>
          <dt>Patient ID</dt>
          <dd className="mono strong">{result.patient_id}</dd>
        </div>
        <div>
          <dt>Eye</dt>
          <dd>{eyeLabel(result.eye)}</dd>
        </div>
        <div>
          <dt>Case ID</dt>
          <dd className="mono">{result.case_id}</dd>
        </div>
        <div>
          <dt>Screened</dt>
          <dd className="num">{formatDateTime(result.created_at)}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd className="mono">{result.model?.version ?? '—'}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{statusLabel(result.status)}</dd>
        </div>
      </dl>
      {onBack && (
        <button type="button" className="btn btn-small" onClick={onBack} disabled={busy}>
          {backLabel}
        </button>
      )}
    </div>
  );
}
