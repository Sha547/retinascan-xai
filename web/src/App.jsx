import { useCallback, useEffect, useRef, useState } from 'react';
import TopBar from './components/TopBar.jsx';
import Stepper from './components/Stepper.jsx';
import UploadScreen from './components/UploadScreen.jsx';
import QualityScreen from './components/QualityScreen.jsx';
import ResultsScreen from './components/ResultsScreen.jsx';
import SuccessScreen from './components/SuccessScreen.jsx';
import DoctorQueue from './components/DoctorQueue.jsx';
import { analyse } from './demoModel.js';
import { rasterise } from './fundus.js';
import { composeScan, generateReport } from './report.js';
import { getCase, getCaseImage, getSimilarImage, initialiseApi, isDemoMode } from './api.js';

const STEP_INDEX = { upload: 0, quality: 1, results: 2, success: 3 };
const readFile = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not read the selected image.'));
    reader.readAsDataURL(file);
  });
export default function App() {
  const [screen, setScreen] = useState('upload');
  const [scan, setScan] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [mock, setMock] = useState(false);
  const [modelVersion, setModelVersion] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [review, setReview] = useState(false);
  const reportRef = useRef(null);
  const markMock = useCallback(() => setMock(true), []);
  useEffect(() => {
    let active = true;
    initialiseApi()
      .then((connection) => {
        if (!active) return;
        setMock(connection.demo || connection.health.model.mock);
        setModelVersion(connection.health.model?.version ?? '');
        setNotice(connection.notice);
        setReady(true);
        setError('');
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  async function pickFile(file) {
    setError('');
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      setError('Upload a JPEG or PNG image.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError('Image exceeds the 15 MB upload limit.');
      return;
    }
    setBusy(true);
    try {
      const image = await readFile(file);
      setScan({ image, file, name: file.name, caption: 'Uploaded scan', sampleId: null });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function pickSample(sample) {
    setError('');
    setBusy(true);
    try {
      // Preserve SVG only in fixture mode. Live requests always send a PNG File.
      const image = isDemoMode() ? sample.image : await rasterise(sample.image);
      setScan({ image, name: 'Synthetic sample', caption: sample.caption, sampleId: sample.id });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function startAnalysis(options) {
    if (!scan || busy) return;
    setError('');
    setResult(null);
    setBusy(true);
    setScreen('quality');
    setReview(false);
    reportRef.current = null;
    try {
      const c = await analyse(scan, options);
      setResult(c);
      if (c.model.mock) markMock();
    } catch (e) {
      setError(e.message);
      setScreen('upload');
    } finally {
      setBusy(false);
    }
  }
  async function openCase(id) {
    setError('');
    setBusy(true);
    setScreen('quality');
    setResult(null);
    setScan(null);
    reportRef.current = null;
    try {
      const c = await getCase(id);
      setResult(c);
      setReview(true);
      if (c.model.mock) markMock();
      setScreen(c.quality.ok ? 'results' : 'quality');
    } catch (e) {
      setError(e.message);
      setScreen('queue');
    } finally {
      setBusy(false);
    }
  }
  async function prepareImage(blob) {
    if (!blob) return null;
    const url = URL.createObjectURL(blob);
    try {
      return await composeScan({ image: url });
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  async function generate() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      let image;
      let url;
      try {
        if (isDemoMode() && scan?.sampleId) image = scan.image;
        else {
          const blob = await getCaseImage(result.case_id);
          if (blob) {
            url = URL.createObjectURL(blob);
            image = url;
          }
        }
        const scanImage = image
          ? await composeScan({ image, heatmap: result.evidence?.heatmap_png, overlay: true })
          : null;
        const originalImage = image ? await composeScan({ image }) : null;
        const similarImages = await Promise.all(
          (result.evidence?.similar ?? []).map(async (item) =>
            prepareImage(await getSimilarImage(item.id_code)),
          ),
        );
        const report = {
          result,
          scanImage,
          originalImage,
          similarImages,
          mock: mock || isDemoMode() || result.model.mock,
        };
        await generateReport(report);
        reportRef.current = report;
        setScreen('success');
      } finally {
        if (url) URL.revokeObjectURL(url);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function regenerate() {
    setBusy(true);
    setError('');
    try {
      await generateReport(reportRef.current);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    setScan(null);
    setResult(null);
    setReview(false);
    reportRef.current = null;
    setError('');
    setScreen('upload');
  }
  function navigate(page) {
    if (page === 'queue') {
      setScreen('queue');
      setError('');
    } else reset();
  }
  const queuePage = screen === 'queue' || review;
  return (
    <div className="app">
      <TopBar
        page={queuePage ? 'queue' : 'screening'}
        onNavigate={navigate}
        disabled={busy || !ready}
        modelVersion={modelVersion}
      />
      {(mock || isDemoMode()) && (
        <div className="mock-banner" role="status">
          Mock model: outputs are not real predictions.
        </div>
      )}
      <main className="main" aria-busy={busy}>
        {notice && (
          <p className="callout tone-amber" role="status">
            {notice}
          </p>
        )}
        {error && (
          <div className="callout tone-red" role="alert">
            {error}
            {!ready && (
              <div className="action-row">
                <button type="button" className="btn" onClick={() => setRetry((n) => n + 1)}>
                  Retry API connection
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    const url = new URL(window.location.href);
                    url.searchParams.set('demo', '1');
                    window.location.assign(url.href);
                  }}
                >
                  Open fixture demo
                </button>
              </div>
            )}
          </div>
        )}
        {!ready ? (
          <p className="muted" role="status">
            {error ? 'Unable to connect to the API.' : 'Connecting to the screening service…'}
          </p>
        ) : (
          <>
            {screen !== 'queue' && !review && <Stepper current={STEP_INDEX[screen]} />}
            {screen === 'upload' && (
              <>
                <UploadScreen
                  scan={scan}
                  onPickFile={pickFile}
                  onPickSample={pickSample}
                  onAnalyse={startAnalysis}
                  onClear={() => setScan(null)}
                  demo={isDemoMode()}
                  busy={busy}
                />
                <DoctorQueue key="history" history onOpen={openCase} onMock={markMock} />
              </>
            )}
            {screen === 'quality' && (
              <QualityScreen
                result={result}
                onRetake={reset}
                onContinue={() => setScreen('results')}
                onBack={review ? () => setScreen('queue') : undefined}
              />
            )}
            {screen === 'results' && result && (
              <ResultsScreen
                key={result.case_id}
                scan={scan}
                result={result}
                busy={busy}
                onGenerate={generate}
                onReset={reset}
                review={review}
                onBusy={setBusy}
                onUpdated={(updated) => {
                  setResult(updated);
                  reportRef.current = null;
                }}
                onBack={review ? () => setScreen('queue') : undefined}
              />
            )}
            {screen === 'queue' && <DoctorQueue key="queue" onOpen={openCase} onMock={markMock} />}
            {screen === 'success' && result && (
              <SuccessScreen
                result={result}
                busy={busy}
                onReset={reset}
                onRegenerate={regenerate}
                onBack={review ? () => setScreen('queue') : undefined}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
