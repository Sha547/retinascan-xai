import { useRef, useState } from 'react';
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

function SamplePhotos({ samples, scan, busy, onPickSample, demo }) {
  if (!samples.length) return null;
  return (
    <aside className="panel samples" aria-labelledby="samples-title">
      <div className="panel-head">
        <h2 id="samples-title">Sample photos</h2>
      </div>
      <div className="panel-body">
        <p className="muted">
          Real fundus photographs from the IDRiD test set (CC BY 4.0), not used in training. The
          official grade is shown so you can compare it with the model.{' '}
          {demo
            ? 'Here they replay outputs recorded from the real model.'
            : 'They are graded live by the model.'}
        </p>
        <div className="sample-list">
          {samples.map((s) => (
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
  samples = [],
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
                    <dd>{scan.sampleId ? 'IDRiD sample photo (CC BY 4.0)' : 'Local file'}</dd>
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
            </div>
            <div className="action-row">
              <button
                type="button"
                className="btn btn-primary"
                disabled={!scan || busy}
                onClick={() => onAnalyse({ patient_id: patientId, eye })}
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
        <div className="side-stack">
          <SamplePhotos
            samples={samples}
            scan={scan}
            busy={busy}
            onPickSample={onPickSample}
            demo={demo}
          />
          <CaptureGuidance />
        </div>
      </div>
    </div>
  );
}
