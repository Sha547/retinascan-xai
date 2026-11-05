import { formatMetrics } from '../format.js';
import RecordHeader from './RecordHeader.jsx';

export function MetricsTable({ metrics }) {
  const rows = formatMetrics(metrics);
  if (!rows.length) return <p className="muted">Quality metrics unavailable in this fixture.</p>;
  return (
    <table className="table metrics-table">
      <tbody>
        {rows.map(([name, label, value]) => (
          <tr key={name}>
            <th scope="row">{label}</th>
            <td className="num">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function QualityScreen({ result, onRetake, onContinue, onBack }) {
  if (!result)
    return (
      <div className="screen">
        <div className="panel panel-body loading" role="status">
          <span className="spinner" aria-hidden="true" />
          Checking image quality and grading…
        </div>
      </div>
    );
  const { quality } = result;
  return (
    <div className="screen">
      <RecordHeader result={result} onBack={onBack} />
      <section className="panel quality-panel">
        <div className={`status-block ${quality.ok ? 'tone-green' : 'tone-amber'}`}>
          <h1>{quality.ok ? 'Image passed the quality check' : 'Retake needed'}</h1>
          {quality.ok ? (
            <p>The image is gradable. Open the result to see the grade and evidence.</p>
          ) : (
            <>
              <p>{result.recommendation}</p>
              {quality.reasons.length > 0 && (
                <ul className="reason-list">
                  {quality.reasons.map((reason) => (
                    <li key={reason.code}>{reason.message}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <div className="panel-body">
          <h2 className="subhead">Measured quality values</h2>
          <MetricsTable metrics={quality.metrics} />
          <div className="action-row">
            {quality.ok ? (
              <button type="button" className="btn btn-primary" onClick={onContinue}>
                View result
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={onRetake}>
                Choose another image
              </button>
            )}
          </div>
        </div>
      </section>
      <p className="disclaimer">{result.disclaimer}</p>
    </div>
  );
}
