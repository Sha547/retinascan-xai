import { useRef, useState } from 'react';
import { SAMPLES } from '../demoModel.js';
import HistoryList from './HistoryList.jsx';
import { CheckIcon, ScanIcon, UploadIcon } from './Icons.jsx';

export default function UploadScreen({ scan, onPickFile, onPickSample, onAnalyse, onClear, history, onClearHistory }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file?.type.startsWith('image/')) onPickFile(file);
  }

  return (
    <div className="screen">
      <div className="section-head">
        <span className="eyebrow">Step 1 · Image acquisition</span>
        <h1>Upload a retinal fundus image</h1>
        <p>
          Drop a fundus photograph captured at the screening camera, or load one of the demo scans below to walk
          through the full pipeline.
        </p>
      </div>

      <div className="upload-grid">
        <div>
          <div
            className={`dropzone ${dragging ? 'dragging' : ''} ${scan ? 'has-image' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onPickFile(file);
                e.target.value = '';
              }}
            />

            {scan ? (
              <div className="preview">
                <img className="preview-thumb" src={scan.image} alt="Selected retinal scan" />
                <div className="preview-meta">
                  <p className="preview-name">{scan.name}</p>
                  <div className="preview-rows">
                    <div>
                      <span>Source</span>
                      <span>{scan.sampleId ? 'Demo sample' : 'Local upload'}</span>
                    </div>
                    <div>
                      <span>Eye / field</span>
                      <span>{scan.caption}</span>
                    </div>
                    <div>
                      <span>Status</span>
                      <span>Ready for analysis</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 14, marginTop: 16 }}>
                    <button type="button" className="link-btn" onClick={() => inputRef.current?.click()}>
                      Replace image
                    </button>
                    <button type="button" className="link-btn" onClick={onClear}>
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                <div className="dz-icon">
                  <UploadIcon />
                </div>
                <p className="dz-title">Drag and drop a fundus image</p>
                <p className="dz-sub">
                  or{' '}
                  <button type="button" className="link-btn" onClick={() => inputRef.current?.click()}>
                    browse your files
                  </button>
                </p>
                <p className="dz-hint">JPG, PNG or TIFF · up to 20 MB · 45–50° field recommended</p>
              </div>
            )}
          </div>

          <div className="action-row">
            <button type="button" className="btn btn-primary" disabled={!scan} onClick={onAnalyse}>
              <ScanIcon width={17} height={17} />
              Analyse Image
            </button>
            <span className="action-note">
              {scan ? 'Runs quality check, then grading and saliency mapping.' : 'Select an image to enable analysis.'}
            </span>
          </div>
        </div>

        <aside className="card samples">
          <h3>Demo scans</h3>
          <p>Pre-loaded cases for the presentation walkthrough.</p>
          <div className="sample-list">
            {SAMPLES.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`sample ${scan?.sampleId === s.id ? 'selected' : ''}`}
                onClick={() => onPickSample(s)}
              >
                <img src={s.image} alt="" />
                <span>
                  <span className="sample-label">{s.label}</span>
                  <br />
                  <span className="sample-caption">{s.caption}</span>
                </span>
                <span className="sample-check">
                  <CheckIcon width={16} height={16} />
                </span>
              </button>
            ))}
          </div>
          <p className="footnote" style={{ marginTop: 18, textAlign: 'left' }}>
            Demo build — grading is pre-scripted per sample. A real deployment calls the inference service with the
            uploaded image.
          </p>
        </aside>
      </div>

      <HistoryList entries={history} onClear={onClearHistory} />
    </div>
  );
}
