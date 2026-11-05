import { useRef, useState } from 'react';
import { SAMPLES } from '../demoModel.js';
import { UploadIcon } from './Icons.jsx';

function fileSize(bytes) {
  if (bytes == null) return null;
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function CaptureGuidance() {
  return (
    <aside className="panel guidance" aria-labelledby="guidance-title">
      <div className="panel-head">
        <h2 id="guidance-title">Capture guidance</h2>
      </div>
      <div className="panel-body">
        <p>Every image is checked for quality before grading. To avoid a retake:</p>
        <ul>
          <li>Even illumination: not too dark, not overexposed.</li>
          <li>In focus: blood vessels look sharp, no motion blur.</li>
          <li>Whole retina in frame, roughly centred.</li>
          <li>No glare or flash reflections on the retina.</li>
          <li>Upload the original JPEG or PNG from the camera (up to 15 MB).</li>
        </ul>
        <p className="muted">
          If the check fails, the reasons are listed and the photo should be retaken.
        </p>
      </div>
    </aside>
  );
}

function FixtureSamples({ scan, busy, onPickSample }) {
  return (
    <aside className="panel samples" aria-labelledby="samples-title">
      <div className="panel-head">
        <h2 id="samples-title">Fixture samples (demo)</h2>
      </div>
      <div className="panel-body">
        <p className="muted">
          Synthetic illustrations, not patient photographs. Each loads a fixed fixture outcome that
          does not describe the image.
        </p>
        <div className="sample-list">
          {SAMPLES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`sample ${scan?.sampleId === s.id ? 'selected' : ''}`}
              aria-pressed={scan?.sampleId === s.id}
              disabled={busy}
              onClick={() => onPickSample(s)}
            >
              <img src={s.image} alt="" />
              <span>
                <span className="sample-label">{s.label}</span>
                <span className="sample-caption">{s.caption}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}

export default function UploadScreen({
  scan,
  onPickFile,
  onPickSample,
  onAnalyse,
  onClear,
  demo,
  busy,
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const [patientId, setPatientId] = useState('');
  const [eye, setEye] = useState('unknown');
  const [outcome, setOutcome] = useState('graded');

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onPickFile(file);
  }
  const choose = () => inputRef.current?.click();

  return (
    <div className="screen">
      <div className="page-head">
        <h1>New screening</h1>
      </div>
      <div className="upload-grid">
        <section className="panel" aria-labelledby="upload-title">
          <div className="panel-head">
            <h2 id="upload-title">Fundus photograph</h2>
          </div>
          <div className="panel-body">
            <input
              ref={inputRef}
              type="file"
              disabled={busy}
              accept="image/jpeg,image/png"
              aria-label="Choose a retinal JPEG or PNG image"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onPickFile(file);
                e.target.value = '';
              }}
            />
            {scan ? (
              <div className="preview">
                <img className="preview-thumb" src={scan.image} alt="Selected fundus image" />
                <dl className="kv">
                  <div>
                    <dt>File</dt>
                    <dd className="break">{scan.name}</dd>
                  </div>
                  {scan.file && (
                    <div>
                      <dt>Size</dt>
                      <dd className="num">{fileSize(scan.file.size)}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Source</dt>
                    <dd>{scan.sampleId ? 'Synthetic fixture sample' : 'Local file'}</dd>
                  </div>
                  <div className="preview-actions">
                    <button type="button" className="btn btn-small" onClick={choose}>
                      Change image
                    </button>
                    <button type="button" className="btn btn-small" onClick={onClear}>
                      Remove
                    </button>
                  </div>
                </dl>
              </div>
            ) : (
              <div
                className={`dropzone ${dragging ? 'dragging' : ''}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
              >
                <UploadIcon />
                <p>
                  Drag a fundus image here or{' '}
                  <button type="button" className="link-btn" onClick={choose}>
                    choose a file
                  </button>
                </p>
                <p className="muted">JPEG or PNG, up to 15 MB</p>
              </div>
            )}

            <div className="form-row">
              <label className="field">
                <span>Patient ID</span>
                <input
                  className="mono"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  placeholder="Optional; generated if blank"
                />
              </label>
              <label className="field field-narrow">
                <span>Eye</span>
                <select value={eye} onChange={(e) => setEye(e.target.value)}>
                  <option value="unknown">Unknown</option>
                  <option value="left">Left</option>
                  <option value="right">Right</option>
                </select>
              </label>
              {demo && (
                <label className="field">
                  <span>Fixture outcome for uploaded files</span>
                  <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                    <option value="graded">Graded fixture</option>
                    <option value="abstained">Abstained fixture</option>
                    <option value="retake">Retake fixture</option>
                  </select>
                </label>
              )}
            </div>
            <div className="action-row">
              <button
                type="button"
                className="btn btn-primary"
                disabled={!scan || busy}
                onClick={() => onAnalyse({ patient_id: patientId, eye, outcome })}
              >
                Analyse image
              </button>
              <span className="muted">
                {busy
                  ? 'Preparing image…'
                  : scan
                    ? 'Runs the quality check, then grading.'
                    : 'Select an image to continue.'}
              </span>
            </div>
          </div>
        </section>
        {demo ? (
          <FixtureSamples scan={scan} busy={busy} onPickSample={onPickSample} />
        ) : (
          <CaptureGuidance />
        )}
      </div>
    </div>
  );
}
