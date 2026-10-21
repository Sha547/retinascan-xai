import { useRef, useState } from 'react';
import TopBar from './components/TopBar.jsx';
import Stepper from './components/Stepper.jsx';
import UploadScreen from './components/UploadScreen.jsx';
import QualityScreen from './components/QualityScreen.jsx';
import ResultsScreen from './components/ResultsScreen.jsx';
import SuccessScreen from './components/SuccessScreen.jsx';
import { analyse, makePatientId } from './demoModel.js';
import { rasterise } from './fundus.js';
import { composeScan, generateReport } from './report.js';
import { addHistoryEntry, clearHistory, loadHistory } from './history.js';

const STEP_INDEX = { upload: 0, quality: 1, results: 2, success: 3 };

// DEMO: simulated server round-trip so the "generating" state is visible.
const RENDER_DELAY_MS = 1200;

export default function App() {
  const [screen, setScreen] = useState('upload');
  const [scan, setScan] = useState(null);
  const [result, setResult] = useState(null);
  const [patientId, setPatientId] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState(loadHistory);

  // Cached composite so "Download again" works after the results view has
  // unmounted.
  const captureRef = useRef(null);

  async function pickFile(file) {
    const raw = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });
    const image = await rasterise(raw);
    setScan({ image, name: file.name, caption: 'Uploaded scan · single field', sampleId: null });
  }

  function pickSample(sample) {
    // Samples are already square SVGs; rasterise so the PDF capture is reliable.
    rasterise(sample.image).then((image) =>
      setScan({
        image,
        name: `${sample.label.replace('Sample: ', '')} — demo scan`,
        caption: sample.caption,
        sampleId: sample.id,
      }),
    );
  }

  function startAnalysis() {
    if (!scan) return;
    setScreen('quality');
    captureRef.current = null;
    // DEMO: hardcoded for presentation, replace with real model inference API call.
    analyse(scan.sampleId).then((res) => {
      setResult(res);
      const id = makePatientId();
      setPatientId(id);
      setHistory(addHistoryEntry({ patientId: id, scanName: scan.name, result: res }));
      setScreen('results');
    });
  }

  async function generate(overlay = true, opacity = 1) {
    setBusy(true);
    const started = performance.now();
    try {
      captureRef.current = await composeScan({ image: scan.image, map: result.heatmap, overlay, opacity });
      // DEMO: hardcoded for presentation, replace with real model inference API
      // call — a production build would spend this time fetching the saliency
      // map and report template from the server. Drop this to make it instant.
      await new Promise((r) => setTimeout(r, RENDER_DELAY_MS));
      await generateReport({
        result,
        patientId,
        scanImage: captureRef.current,
        fileName: scan.sampleId ? null : scan.name,
      });
      setElapsed((performance.now() - started) / 1000);
      setScreen('success');
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setScan(null);
    setResult(null);
    setPatientId('');
    captureRef.current = null;
    setScreen('upload');
  }

  return (
    <div className="app">
      <TopBar />
      <main className="main">
        <Stepper current={STEP_INDEX[screen]} />

        {screen === 'upload' && (
          <UploadScreen
            scan={scan}
            onPickFile={pickFile}
            onPickSample={pickSample}
            onAnalyse={startAnalysis}
            onClear={() => setScan(null)}
            history={history}
            onClearHistory={() => setHistory(clearHistory())}
          />
        )}

        {screen === 'quality' && <QualityScreen />}

        {screen === 'results' && result && (
          <ResultsScreen
            scan={scan}
            result={result}
            patientId={patientId}
            busy={busy}
            onGenerate={generate}
            onReset={reset}
          />
        )}

        {screen === 'success' && result && (
          <SuccessScreen
            result={result}
            patientId={patientId}
            elapsed={elapsed}
            onReset={reset}
            onRegenerate={() =>
              generateReport({
                result,
                patientId,
                scanImage: captureRef.current,
                fileName: scan?.sampleId ? null : scan?.name,
              })
            }
          />
        )}
      </main>
    </div>
  );
}
