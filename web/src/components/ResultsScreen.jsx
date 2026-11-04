import { useState } from 'react';
import { DocIcon, RefreshIcon } from './Icons.jsx';
import { GRADE_LABELS, isDemoMode, percent } from '../api.js';
import CaseImage from './CaseImage.jsx';
import DecisionPanel from './DecisionPanel.jsx';

const R = 46;
const CIRC = 2 * Math.PI * R;
function ConfidenceRing({ value }) {
  return <div className="ring-wrap"><div className="ring">
    <svg width="104" height="104" viewBox="0 0 104 104" aria-hidden="true">
      <circle className="ring-track" cx="52" cy="52" r={R} fill="none" strokeWidth="8" />
      <circle className="ring-value" cx="52" cy="52" r={R} fill="none" strokeWidth="8" strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - value)} />
    </svg><div className="ring-label"><span className="ring-num">{percent(value)}</span></div>
  </div><span className="ring-cap">Calibrated confidence</span></div>;
}

export default function ResultsScreen({ scan, result, busy, onGenerate, onReset, review, onUpdated, onBack, onBusy }) {
  const [view, setView] = useState('overlay');
  const [opacity, setOpacity] = useState(1);
  const [split, setSplit] = useState(50);
  const [imageReady, setImageReady] = useState(false);
  const [ratio, setRatio] = useState(scan?.ratio ?? 1);
  const p = result.prediction;
  const evidence = result.evidence;
  const tone = p.abstained ? 'orange' : p.referable ? 'red' : 'green';
  const synthetic = isDemoMode() && scan?.sampleId;
  const showOverlay = view !== 'original' && (synthetic || imageReady);
  return <div className="screen">
    <div className="section-head"><h1>Screening result</h1><p>Model output and supporting evidence for ophthalmologist review.</p></div>
    {onBack && <button className="btn btn-ghost back-button" onClick={onBack} disabled={busy}>Back to doctor queue</button>}
    {p.abstained && <p className="notice abstention" role="status">Not confident: routed to doctor for review</p>}
    {result.fixturePartial && <p className="notice">This queue fixture supplies a summary only. Probabilities, recommendation, quality metrics and full evidence are unavailable.</p>}
    <div className="results-grid">
      <div>
        <section className="card scan-card">
          <div className="scan-head"><div><h3>Grad-CAM saliency overlay</h3><p>{synthetic ? 'Synthetic illustration · fixture output' : result.case_id}</p></div>
            <div className="seg" role="group" aria-label="Scan view">{[['overlay','Overlay'],['split','Split'],['original','Original']].map(([id,label]) =>
              <button key={id} type="button" className={`seg-btn ${view === id ? 'active' : ''}`} aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}</div>
          </div>
          <div className="scan-frame" style={{ aspectRatio: ratio }}>
            {synthetic ? <img src={scan.image} alt="Synthetic fundus illustration" /> : <CaseImage id={result.case_id} alt="Uploaded retinal fundus scan" onSize={setRatio} onReady={setImageReady} />}
            {evidence?.heatmap_png && showOverlay && <img src={evidence.heatmap_png} className="heatmap" alt="" aria-hidden="true"
              style={{ opacity, clipPath: `inset(0 0 0 ${view === 'split' ? split : 0}%)` }} />}
            {view === 'split' && <><span className="split-line" style={{ left: `${split}%` }} aria-hidden="true" />
              <input className="split-input" type="range" min="0" max="100" value={split} onChange={e => setSplit(Number(e.target.value))} aria-label="Split position between original and saliency overlay" /></>}
          </div>
          <label className="opacity-row"><span>Overlay strength</span><input type="range" min="0" max="1" step="0.05" value={opacity} disabled={!showOverlay || !evidence} onChange={e => setOpacity(Number(e.target.value))} /><span className="opacity-val">{Math.round(opacity * 100)}%</span></label>
          <p className="heatmap-caption">{evidence?.heatmap_note ?? 'Heatmap unavailable in this fixture.'}</p>
          {isDemoMode() && !synthetic && <p className="footnote">Comparison unavailable: fixture case images are not included.</p>}
        </section>
        <div className="meta-strip"><div><span>Patient ID</span><span>{result.patient_id}</span></div><div><span>Quality check</span><span>Gradable</span></div>
          <div><span>Model</span><span>{result.model.version}</span></div><div><span>Eye</span><span>{result.eye}</span></div></div>
        <section className="card similar-cases"><h2>Similar cases from the training set</h2>
          {evidence?.similar ? <div className="similar-strip">{evidence.similar.map(item => <figure key={item.id_code}>
            <CaseImage id={item.id_code} similar alt={`Training case ${item.id_code}`} />
            <figcaption><strong>{item.grade_label}</strong><span>Known grade {item.grade}</span><span>Distance: {item.distance}</span></figcaption>
          </figure>)}</div> : <p>Similar-case evidence unavailable in this fixture.</p>}
        </section>
      </div>
      <section className="card grade-card">
        <div className="grade-top"><div><div className="block-title">{p.abstained ? 'Model’s tentative grade' : 'Severity grade'}</div>
          <span className={p.abstained ? 'tentative-grade' : `badge ${tone}`}>Grade {p.grade} · {p.grade_label}</span></div><ConfidenceRing value={p.confidence} /></div>
        <ol className="sev-scale" aria-label={`ICDR scale, ${p.abstained ? 'tentative ' : ''}grade ${p.grade}`}>{GRADE_LABELS.map((label,i) => <li key={label} className={`sev-step ${i <= p.grade ? `reached ${tone}` : ''} ${i === p.grade ? 'current' : ''}`}><span className="sev-bar" /><span className="sev-label">{label}</span></li>)}</ol>
        <div className="block"><h2 className="block-title">Calibrated grade probabilities</h2>
          {p.probs ? <div className="probabilities">{p.probs.map((value,i) => <div key={GRADE_LABELS[i]}><span>{i} · {GRADE_LABELS[i]}</span><span>{percent(value)}</span><meter min="0" max="1" value={value} aria-label={`Probability of ${GRADE_LABELS[i]}`} /></div>)}</div> : <p>Probabilities unavailable in this fixture.</p>}
        </div>
        <div className="block"><h2 className="block-title">Referable decision</h2><p className={`badge ${tone}`}>{p.referable ? 'Referable' : 'Not referable'}</p>
          {p.referable_prob != null && <p>Referable probability: {percent(p.referable_prob)}</p>}</div>
        <div className="block"><h2 className="block-title">Recommendation</h2><div className={`referral ${tone}`}><p className="referral-text">{result.recommendation ?? 'Recommendation unavailable in this fixture.'}</p></div></div>
        <details className="block"><summary>Image quality metrics</summary><dl className="quality-metrics">{Object.entries(result.quality.metrics).map(([name,value]) => <div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{value}</dd></div>)}</dl></details>
        <div className="grade-actions"><button type="button" className="btn btn-teal" onClick={onGenerate} disabled={busy}><DocIcon />{busy ? 'Generating…' : 'Generate Referral Report'}</button>
          <button type="button" className="btn btn-ghost" onClick={onReset} disabled={busy}><RefreshIcon />New screening</button></div>
      </section>
    </div>
    {review && <DecisionPanel result={result} onUpdated={onUpdated} onBusy={onBusy} />}
    <p className="footnote">{result.disclaimer}</p>
  </div>;
}
