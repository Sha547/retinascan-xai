import { useEffect, useRef, useState } from 'react';
import { drawHeatmap, HEATMAP_SIZE } from '../heatmap.js';
import { DocIcon, RefreshIcon } from './Icons.jsx';

const R = 46;
const CIRC = 2 * Math.PI * R;

function ConfidenceRing({ value }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setShown(value), 120);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <div className="ring-wrap">
      <div className="ring">
        <svg width="104" height="104" viewBox="0 0 104 104">
          <circle className="ring-track" cx="52" cy="52" r={R} fill="none" strokeWidth="8" />
          <circle
            className="ring-value"
            cx="52"
            cy="52"
            r={R}
            fill="none"
            strokeWidth="8"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC - (CIRC * shown) / 100}
          />
        </svg>
        <div className="ring-label">
          <span className="ring-num">{value}%</span>
        </div>
      </div>
      <span className="ring-cap">Model confidence</span>
    </div>
  );
}

function Heatmap({ map, visible, opacity, clip }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, HEATMAP_SIZE, HEATMAP_SIZE);
    drawHeatmap(ctx, map);
  }, [map]);

  return (
    <canvas
      ref={canvasRef}
      className="heatmap"
      width={HEATMAP_SIZE}
      height={HEATMAP_SIZE}
      style={{ opacity: visible ? opacity : 0, clipPath: `inset(0 0 0 ${clip}%)` }}
      aria-hidden="true"
    />
  );
}

const GRADES = ['No DR', 'Mild', 'Moderate', 'Severe', 'Proliferative'];

function SeverityScale({ severity, tone }) {
  return (
    <ol className="sev-scale" aria-label={`ICDR severity scale, grade ${severity} of 4`}>
      {GRADES.map((label, i) => (
        <li key={label} className={`sev-step ${i <= severity ? `reached ${tone}` : ''} ${i === severity ? 'current' : ''}`}>
          <span className="sev-bar" />
          <span className="sev-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

const VIEWS = [
  ['overlay', 'Overlay'],
  ['split', 'Split'],
  ['original', 'Original'],
];

export default function ResultsScreen({ scan, result, patientId, busy, onGenerate, onReset }) {
  const [view, setView] = useState('overlay');
  const [opacity, setOpacity] = useState(1);
  const [split, setSplit] = useState(50);
  const overlay = view !== 'original';

  return (
    <div className="screen">
      <div className="section-head">
        <span className="eyebrow">Step 3 · Grading &amp; explanation</span>
        <h1>Screening result</h1>
        <p>Model output with the saliency map that produced it, ready for clinician review.</p>
      </div>

      <div className="results-grid">
        <div>
          <section className="card scan-card">
            <div className="scan-head">
              <div>
                <h3>Grad-CAM saliency overlay</h3>
                <p>{scan.name}</p>
              </div>
              <div className="seg" role="group" aria-label="Scan view">
                {VIEWS.map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={`seg-btn ${view === id ? 'active' : ''}`}
                    aria-pressed={view === id}
                    onClick={() => setView(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="scan-frame">
              <img src={scan.image} alt="Retinal fundus scan" />
              <Heatmap map={result.heatmap} visible={overlay} opacity={opacity} clip={view === 'split' ? split : 0} />
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
                    aria-label="Split position between original and saliency overlay"
                  />
                </>
              )}
            </div>

            <label className="opacity-row">
              <span>Overlay strength</span>
              <input
                type="range"
                min="0.2"
                max="1"
                step="0.05"
                value={opacity}
                disabled={!overlay}
                onChange={(e) => setOpacity(Number(e.target.value))}
              />
              <span className="opacity-val">{Math.round(opacity * 100)}%</span>
            </label>

            <div className="scan-legend">
              <span className="legend-scale">
                Low
                <span className="legend-bar" />
                High
              </span>
              <span>Regions the model weighted most heavily when assigning the grade.</span>
            </div>
          </section>

          <div className="meta-strip">
            <div>
              <span>Patient ID</span>
              <span>{patientId}</span>
            </div>
            <div>
              <span>Quality check</span>
              <span>Gradable</span>
            </div>
            <div>
              <span>Model</span>
              <span>rs-xai-demo · v0.9</span>
            </div>
            <div>
              <span>Inference time</span>
              <span>1.48 s</span>
            </div>
          </div>
        </div>

        <section className="card grade-card">
          <div className="grade-top">
            <div>
              <div className="block-title" style={{ marginBottom: 12 }}>
                Severity grade
              </div>
              <span className={`badge ${result.tone}`}>
                <span className="pulse" />
                {result.gradeLabel}
              </span>
            </div>
            <ConfidenceRing value={result.confidence} />
          </div>

          <SeverityScale severity={result.severity} tone={result.tone} />

          <div className="block">
            <div className="block-title">AI explanation</div>
            <p className="explanation">{result.explanation}</p>
          </div>

          <div className="block">
            <div className="block-title">Detected features</div>
            <div className="findings">
              {result.findings.map(([label, value]) => (
                <div className="finding" key={label}>
                  <span>{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="block">
            <div className="block-title">Referral recommendation</div>
            <div className={`referral ${result.tone}`}>
              <div>
                <p className="referral-text">{result.referral}</p>
                <p className="referral-sub">
                  Based on ICDR severity scale · grade {result.severity} pathway
                </p>
              </div>
            </div>
          </div>

          <div className="grade-actions">
            <button type="button" className="btn btn-teal" onClick={() => onGenerate(overlay, opacity)} disabled={busy}>
              <DocIcon />
              {busy ? 'Generating…' : 'Generate Referral Report'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onReset} disabled={busy}>
              <RefreshIcon />
              New screening
            </button>
          </div>
        </section>
      </div>

      <p className="footnote">
        Demo build — no real model inference. Grades, confidence scores and saliency maps are pre-scripted for the
        presentation.
      </p>
    </div>
  );
}
