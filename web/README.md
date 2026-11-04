# RetinaScan XAI — demo prototype

Explainable-AI diabetic retinopathy screening, built for the Smart India Hackathon
internal round.

> **This is a demo, not a clinical product.** There is no machine learning model.
> Grades, confidence scores, saliency maps and quality checks are pre-scripted
> per sample. Every place a real model would plug in is marked in the source with
> `// DEMO: hardcoded for presentation, replace with real model inference API call`.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production bundle in dist/
```

Everything runs client-side — no backend, no database, no API keys.

## Demo script (4 screens)

1. **Upload** — drag in a fundus image, or click one of the three demo scans.
2. **Quality check** — 1.5 s illumination / focus / field / artefact pass.
3. **Results** — scan with the Grad-CAM overlay, severity badge, confidence ring,
   explanation, detected features and referral recommendation. The *Heatmap*
   switch toggles the overlay.
4. **Report** — generates and downloads an A4 PDF referral, then shows the
   success screen with *Start New Screening*.

## Scripted outcomes

| Selection            | Grade                        | Confidence | Referral                                 |
| -------------------- | ---------------------------- | ---------- | ---------------------------------------- |
| Sample: Healthy      | Grade 0 — No DR              | 96%        | Routine follow-up in 12 months.          |
| Sample: Moderate DR  | Grade 2 — Moderate DR        | 92%        | Refer to ophthalmologist within 30 days. |
| Sample: Severe DR    | Grade 4 — Proliferative DR   | 94%        | Urgent referral required.                |
| Any uploaded file    | Grade 2 — Moderate DR        | 92%        | Refer to ophthalmologist within 30 days. |

## Where the seams are

| File                 | Role                                                                      |
| -------------------- | ------------------------------------------------------------------------- |
| `src/demoModel.js`   | The only "model": samples, scripted grades, `analyse()`, patient IDs.     |
| `src/heatmap.js`     | Draws the simulated Grad-CAM map — shared by the screen and the PDF.      |
| `src/fundus.js`      | Synthetic fundus images (SVG) and image normalisation.                    |
| `src/report.js`      | jsPDF referral report and the scan/overlay composite it embeds.           |
| `src/App.jsx`        | Four-screen flow and timings (`RENDER_DELAY_MS`).                         |

Swapping in a real backend means changing `analyse()` in `src/demoModel.js` to
call the inference service and return the same result shape; nothing else in the
app knows how the result was produced.

## Project structure

```
src/
  App.jsx          screen flow (upload → quality → results → report)
  demoModel.js     scripted per-sample grades, confidence and findings
  fundus.js        procedural fundus images for the demo scans
  heatmap.js       Grad-CAM style overlay rendering
  report.js        A4 PDF referral generation
  components/      one component per screen, plus stepper and top bar
```
