export default function QualityScreen({ result, onRetake, onContinue, onBack }) {
  if (!result)
    return (
      <div className="screen quality">
        <div className="card quality-card" role="status">
          <div className="spinner" />
          <h1>Checking the scan…</h1>
          <p>Waiting for image quality and model output from the service.</p>
        </div>
      </div>
    );
  const { quality } = result;
  return (
    <div className="screen quality">
      <section className="card quality-card">
        <h1>{quality.ok ? 'Image quality passed' : 'Retake needed'}</h1>
        <p>{result.recommendation}</p>
        <ul className="reason-list">
          {quality.reasons.map((reason) => (
            <li key={reason.code}>{reason.message}</li>
          ))}
        </ul>
        <dl className="quality-metrics">
          {Object.entries(quality.metrics).map(([name, value]) => (
            <div key={name}>
              <dt>{name.replaceAll('_', ' ')}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <p className="footnote">
          {result.patient_id} · {result.case_id}
        </p>
        <div className="success-actions">
          {quality.ok ? (
            <button className="btn btn-primary" onClick={onContinue}>
              View screening result
            </button>
          ) : (
            <button className="btn btn-primary" onClick={onRetake}>
              Retake / choose another image
            </button>
          )}
          {onBack && (
            <button className="btn btn-ghost" onClick={onBack}>
              Back to doctor queue
            </button>
          )}
        </div>
        <p className="footnote">{result.disclaimer}</p>
      </section>
    </div>
  );
}
