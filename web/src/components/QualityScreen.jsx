import { useEffect, useState } from 'react';
import { CheckIcon } from './Icons.jsx';

/*
 * DEMO: hardcoded for presentation, replace with real model inference API call.
 * The production quality module would score illumination, focus, field of view
 * and artefacts on the actual pixels; here the values are fixed and revealed on
 * a timer so the pipeline stage is visible during the demo.
 */
const CHECKS = [
  ['Illumination uniformity', 'Pass'],
  ['Focus / sharpness', 'Pass'],
  ['Field of view', '45° · Pass'],
  ['Artefacts & reflections', 'None'],
];

const DURATION = 1500;

export default function QualityScreen() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const start = performance.now();
    let frame;
    const tick = () => {
      const pct = Math.min(100, ((performance.now() - start) / DURATION) * 100);
      setProgress(pct);
      if (pct < 100) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  const cleared = Math.floor((progress / 100) * (CHECKS.length + 0.4));

  return (
    <div className="screen quality">
      <div className="card quality-card">
        <div className="spinner" />
        <h2>Checking image quality…</h2>
        <p>Validating the scan is gradable before it reaches the model.</p>

        <div className="progress" role="progressbar" aria-valuenow={Math.round(progress)}>
          <div className="progress-bar" style={{ width: `${progress}%` }} />
        </div>

        <div className="checks">
          {CHECKS.map(([label, value], i) => (
            <div key={label} className={`check ${i < cleared ? 'done' : ''}`}>
              <span className="check-mark">{i < cleared && <CheckIcon />}</span>
              {label}
              <span className="check-value">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
