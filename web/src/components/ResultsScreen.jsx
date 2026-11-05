import { useState } from 'react';
import { DocIcon } from './Icons.jsx';
import { GRADE_LABELS, percent } from '../api.js';
import CaseImage from './CaseImage.jsx';
import DecisionPanel from './DecisionPanel.jsx';
import RecordHeader from './RecordHeader.jsx';
import { MetricsTable } from './QualityScreen.jsx';

function ProbabilityTable({ probs, grade }) {
  if (!probs) return <p className="muted">Probabilities unavailable in this fixture.</p>;
  return (
    <table className="table prob-table">
      <caption className="sr-only">Calibrated probability for each ICDR grade</caption>
      <thead>
        <tr>
          <th scope="col">Grade</th>
          <th scope="col" className="bar-col">
            <span className="sr-only">Bar</span>
          </th>
          <th scope="col" className="num">
            Probability
          </th>
        </tr>
      </thead>
      <tbody>
        {probs.map((value, i) => (
          <tr key={GRADE_LABELS[i]} className={i === grade ? 'current' : ''}>
            <th scope="row">
              <span className="num">{i}</span> {GRADE_LABELS[i]}
            </th>
            <td className="bar-col" aria-hidden="true">
              <span className="bar">
                <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
              </span>
            </td>
            <td className="num">{percent(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ReferableDecision({ p }) {
  const prob =
    p.referable_prob != null ? ` (referable probability ${percent(p.referable_prob)})` : '';
  if (p.abstained)
    return (
      <p className="status-line tone-amber">
        <span className="dot" aria-hidden="true" />
        <span>
          <strong>Pending doctor review.</strong> Model’s tentative call:{' '}
          {p.referable ? 'referable' : 'not referable'}
          {prob}.
        </span>
      </p>
    );
  return (
    <p className={`status-line ${p.referable ? 'tone-red' : 'tone-green'}`}>
      <span className="dot" aria-hidden="true" />
      <span>
        <strong>{p.referable ? 'Referable' : 'Not referable'}</strong>
        {prob}
      </span>
    </p>
  );
}

export default function ResultsScreen({
  scan,
  result,
  busy,
  onGenerate,
  onReset,
  review,
  onUpdated,
  onBack,
  onBusy,
}) {
  const [view, setView] = useState('overlay');
  const [opacity, setOpacity] = useState(1);
  const [split, setSplit] = useState(50);
  const [imageReady, setImageReady] = useState(false);
  const [ratio, setRatio] = useState(scan?.ratio ?? 1);
  const p = result.prediction;
  const evidence = result.evidence;
  const tone = p.abstained ? 'tone-amber' : p.referable ? 'tone-red' : 'tone-green';
  const showOverlay = view !== 'original' && imageReady;
  return (
    <div className="screen">
      <RecordHeader result={result} onBack={onBack} busy={busy} />
      {p.abstained && (
        <div className="callout tone-amber" role="status">
          <strong>
            {p.abstain_reason === 'grade_referral_conflict'
              ? 'Grade and referral signals disagree: routed to doctor for review.'
              : 'Not confident: routed to doctor for review.'}
          </strong>{' '}
          The grade shown is the model’s tentative grade; the referable decision is left to the
          reviewing doctor.
        </div>
      )}
      {result.fixturePartial && (
        <div className="callout">
          This queue fixture supplies a summary only. Probabilities, recommendation, quality metrics
          and image evidence are unavailable.
        </div>
      )}
      <div className="results-grid">
        <div className="results-left">
          <section className="panel" aria-labelledby="image-title">
            <div className="panel-head">
              <h2 id="image-title">Fundus image</h2>
              <div className="seg" role="group" aria-label="Image view">
                {[
                  ['overlay', 'Overlay'],
                  ['split', 'Split'],
                  ['original', 'Original'],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={view === id ? 'active' : ''}
                    aria-pressed={view === id}
                    onClick={() => setView(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="panel-body">
              <div className="scan-frame" style={{ aspectRatio: ratio }}>
                <CaseImage
                  id={result.case_id}
                  alt="Fundus photograph"
                  onSize={setRatio}
                  onReady={setImageReady}
                />
                {evidence?.heatmap_png && showOverlay && (
                  <img
                    src={evidence.heatmap_png}
                    className="heatmap"
                    alt=""
                    aria-hidden="true"
                    style={{ opacity, clipPath: `inset(0 0 0 ${view === 'split' ? split : 0}%)` }}
                  />
                )}
                {view === 'split' && (
                  <>
                    <span className="split-line" style={{ left: `${split}%` }} aria-hidden="true" />
                    <input
                      className="split-input"
                      type="range"
                      min="0"
                      max="100"
                      value={split}
                      onChange={(e) => setSplit(Number(e.target.value))}
                      aria-label="Split position between original and heatmap overlay"
                    />
                  </>
                )}
              </div>
              <label className="opacity-row">
                <span>Overlay strength</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={opacity}
                  disabled={!showOverlay || !evidence}
                  onChange={(e) => setOpacity(Number(e.target.value))}
                />
                <span className="num">{Math.round(opacity * 100)}%</span>
              </label>
              <p className="caption">
                {evidence?.heatmap_note ?? 'Heatmap unavailable in this fixture.'}
              </p>
              {evidence && p.grade === 0 && (
                <p className="caption">
                  For a No DR result, highlighted regions are not findings: they show what the model
                  weighed, not abnormalities.
                </p>
              )}
            </div>
          </section>
          <section className="panel" aria-labelledby="similar-title">
            <div className="panel-head">
              <h2 id="similar-title">Similar training images</h2>
            </div>
            <div className="panel-body">
              {evidence?.similar ? (
                <div className="similar-strip">
                  {evidence.similar.map((item) => (
                    <figure key={item.id_code}>
                      <CaseImage id={item.id_code} similar alt={`Training image ${item.id_code}`} />
                      <figcaption>
                        <span>
                          <span className="num">{item.grade}</span> {item.grade_label}
                        </span>
                        <span className="muted num">
                          Distance {Number(item.distance).toFixed(2)}
                        </span>
                      </figcaption>
                    </figure>
                  ))}
                </div>
              ) : (
                <p className="muted">Similar-image evidence unavailable in this fixture.</p>
              )}
            </div>
          </section>
        </div>

        <div className="results-right">
          <section className="panel findings" aria-labelledby="findings-title">
            <div className="panel-head">
              <h2 id="findings-title">Findings</h2>
            </div>
            <div className="panel-body">
              <div className="figures">
                <div className={`figure ${p.abstained ? 'tentative' : ''}`}>
                  <span className="figure-label">
                    {p.abstained ? 'Tentative grade (ICDR)' : 'Grade (ICDR)'}
                  </span>
                  <span className="figure-value">
                    <span className="num">{p.grade}</span>
                    <span className="figure-unit">{p.grade_label}</span>
                  </span>
                </div>
                <div className="figure">
                  <span className="figure-label">Calibrated confidence</span>
                  <span className="figure-value num">{percent(p.confidence)}</span>
                </div>
              </div>

              {scan?.officialGrade != null && (
                <p className="reference-grade">
                  Reference: IDRiD official grade{' '}
                  <strong>
                    <span className="num">{scan.officialGrade}</span>{' '}
                    {GRADE_LABELS[scan.officialGrade]}
                  </strong>
                  {scan.officialGrade === p.grade
                    ? ' (model agrees)'
                    : ' (model differs; shown for comparison, not used by the model)'}
                </p>
              )}

              <h3 className="subhead">Grade probabilities (calibrated)</h3>
              <ProbabilityTable probs={p.probs} grade={p.grade} />

              <h3 className="subhead">Referable decision</h3>
              <ReferableDecision p={p} />

              <h3 className="subhead">Recommendation</h3>
              <p className={`recommendation ${tone}`}>
                {result.recommendation ?? 'Recommendation unavailable in this fixture.'}
              </p>

              <details className="metrics-details">
                <summary>Image quality values</summary>
                <MetricsTable metrics={result.quality.metrics} />
              </details>

              <div className="action-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={onGenerate}
                  disabled={busy}
                >
                  <DocIcon />
                  {busy ? 'Preparing PDF…' : 'Download screening report (PDF)'}
                </button>
                <button type="button" className="btn" onClick={onReset} disabled={busy}>
                  New screening
                </button>
              </div>
              <p className="disclaimer">{result.disclaimer}</p>
            </div>
          </section>
          {review && <DecisionPanel result={result} onUpdated={onUpdated} onBusy={onBusy} />}
        </div>
      </div>
    </div>
  );
}
