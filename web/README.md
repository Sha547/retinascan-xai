# RetinaScan XAI frontend

React 19 + Vite screening and doctor-review prototype. API shapes follow
`../docs/CONTRACT.md` v1.1. The existing visual system, overlay/split viewer and
client-side jsPDF report are retained.

## Run against the API

```bash
cd web
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` by default. This is the default
for the Linux demo machine, where FastAPI and Vite run together.

On the Mac, use the backend laptop's Wi-Fi IP from Lane B's `PROGRESS.md` entry:

```bash
VITE_API_PROXY=http://<3050-LAN-IP>:8000 npm run dev
```

You can also set `VITE_API_PROXY` in an uncommitted `web/.env.local` and restart
Vite. No Mac address or host is embedded in the app. Live uploads send the
original JPEG/PNG as multipart `image`, optional `patient_id`, and `eye`.
Synthetic samples are labelled illustrations and rasterised to PNG before live
upload. Their live outcomes come entirely from the API.

```bash
npm run build
npm run lint
node --test tests/*.test.js
```

`npm run preview` serves the built static app, but does not provide the dev
proxy. For a production build, serve `/api` on the same origin through the
backend/reverse proxy; configure that on the hosting machine.

## Fixture demo

Open `http://localhost:5173/?demo=1`. If the initial `/api/health` request cannot
connect or times out, the app displays a notice and switches to fixtures. A proxy 502/504 without an API error envelope also triggers this fallback. Use
**Open fixture demo** on the connection error screen to switch explicitly. HTTP
errors from a reachable service are shown with the API's message; they do not
silently switch modes. Reload without `?demo=1` to retry the live connection.

The persistent banner reads: **Mock model: outputs are not real predictions.**
It appears in fixture mode and whenever the service or cases report mock output.
The PDF includes it on every page when its case is mock or demo mode is active.

The fixtures in `src/fixtures/` are exact copies of `../docs/fixtures/*.json`.
There are no frontend-generated model scores. Choose the graded, abstained or
retake sample, or upload a file and select its fixture outcome. Fixture outputs
do not describe the selected image. Case images and similar-case images are
missing in fixture mode and use neutral placeholders. Only the explicitly
synthetic sample illustrations can be displayed with a fixture heatmap. Live
heatmaps use the API's aligned PNG overlay; the old simulated blob renderer is
unused.

Demo analyses and decisions are kept in memory for this page session. Reloading
resets them. The queue uses the supplied fixture ordering and never sorts rows
in the UI. Two queue summaries (`a10004`, `a10005`) have no full Case fixture:
their detail view explicitly marks unavailable evidence, probabilities, quality
metrics and recommendation. Their supplied summary grades can still be accepted
or overridden. A request for complete fixtures is recorded in `PROGRESS.md`.

## Walkthrough and checks

- **Graded:** choose the graded fixture, analyse, inspect quality metrics, then
  continue to results. Check all five probabilities, the referable decision,
  verbatim recommendation, heatmap caption and similar-case grades/distances.
- **Abstained:** choose the abstained fixture. The review-routing notice leads;
  the grade is labelled tentative and displayed smaller.
- **Retake:** choose the retake fixture. Reasons and measured quality values
  appear; no grade is displayed. Choose another image to continue.
- **PDF:** download from a graded or abstained result. It includes case/patient
  identifiers, screening date, model output, abstention, referable decision,
  recommendation, scan with heatmap, similar cases, model version and reviewer
  history. Missing fixture images remain placeholders. The report always uses
  the full heatmap; the screen's opacity and split controls are viewing aids.
- **Doctor queue:** switch Pending / Reviewed / Retake / All. Open a case, enter
  a reviewer name, Accept, then Override with a final grade. Check the decision
  history, return to the queue and check its refreshed status/final grade.
  Retake cases cannot be accepted or overridden. Clear all pending cases to see
  the empty state. Recent screenings use `/api/cases?status=all` as well.
- **Errors:** verify a live API 4xx message is shown as returned. Image endpoint
  errors appear in their image slots. A failed decision leaves the form available
  for retry; a failed report leaves its result visible.
- Check the upload, results, queue and review form at about 400px and desktop
  width, using keyboard focus as well as a pointer.

Only the reviewer-name convenience uses localStorage. Patient images, screening
history and decisions are not written to browser storage. The operating-point
slider is deferred to Phase 2; an API function exists but no slider is exposed.

Every result and PDF carries:

> Research prototype, not clinically validated. Final decision must be made by a qualified ophthalmologist.
