import { CheckCircleIcon, DocIcon, RefreshIcon } from './Icons.jsx';
import { formatDate } from '../report.js';

export default function SuccessScreen({ result, busy, onReset, onRegenerate, onBack }) {
  return (
    <div className="screen success">
      <div className="card success-card">
        <div className="success-icon">
          <CheckCircleIcon />
        </div>
        <h1>Report generated</h1>
        <p>The referral PDF has been downloaded to this device.</p>
        <div className="success-rows">
          <div>
            <span>Patient ID</span>
            <span>{result.patient_id}</span>
          </div>
          <div>
            <span>Case ID</span>
            <span>{result.case_id}</span>
          </div>
          <div>
            <span>
              {result.prediction.abstained ? 'Model’s tentative grade' : 'Severity grade'}
            </span>
            <span>{result.prediction.grade_label}</span>
          </div>
          <div>
            <span>Recommendation</span>
            <span>{result.recommendation ?? 'Unavailable in fixture'}</span>
          </div>
          <div>
            <span>Screening date</span>
            <span>{formatDate(result.created_at)}</span>
          </div>
        </div>
        <div className="success-actions">
          <button className="btn btn-primary" onClick={onReset} disabled={busy}>
            <RefreshIcon />
            Start New Screening
          </button>
          <button className="btn btn-ghost" onClick={onRegenerate} disabled={busy}>
            <DocIcon />
            Download again
          </button>
          {onBack && (
            <button className="btn btn-ghost" onClick={onBack} disabled={busy}>
              Back to doctor queue
            </button>
          )}
        </div>
      </div>
      <p className="footnote">{result.disclaimer}</p>
    </div>
  );
}
