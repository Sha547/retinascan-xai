import { percent } from '../api.js';
import RecordHeader from './RecordHeader.jsx';

export default function SuccessScreen({ result, busy, onReset, onRegenerate, onBack }) {
  const p = result.prediction;
  return (
    <div className="screen">
      <RecordHeader result={result} onBack={onBack} busy={busy} />
      <section className="panel">
        <div className="status-block tone-green">
          <h1>Screening report downloaded</h1>
          <p>The report was saved to this device’s downloads folder.</p>
        </div>
        <div className="panel-body">
          <table className="table metrics-table">
            <tbody>
              <tr>
                <th scope="row">{p.abstained ? 'Tentative grade' : 'Grade'}</th>
                <td>
                  <span className="num">{p.grade}</span> {p.grade_label}
                </td>
              </tr>
              <tr>
                <th scope="row">Calibrated confidence</th>
                <td className="num">{percent(p.confidence)}</td>
              </tr>
              <tr>
                <th scope="row">Recommendation</th>
                <td>{result.recommendation ?? 'Unavailable in this fixture.'}</td>
              </tr>
            </tbody>
          </table>
          <div className="action-row">
            <button type="button" className="btn btn-primary" onClick={onReset} disabled={busy}>
              Start new screening
            </button>
            <button type="button" className="btn" onClick={onRegenerate} disabled={busy}>
              Download again
            </button>
          </div>
        </div>
      </section>
      <p className="disclaimer">{result.disclaimer}</p>
    </div>
  );
}
