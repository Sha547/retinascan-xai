import healthFixture from './fixtures/health.json' with { type: 'json' };
import graded from './fixtures/analyse_graded.json' with { type: 'json' };
import abstained from './fixtures/analyse_abstained.json' with { type: 'json' };
import retake from './fixtures/analyse_retake.json' with { type: 'json' };
import reviewed from './fixtures/case_reviewed.json' with { type: 'json' };
import allFixture from './fixtures/cases_all.json' with { type: 'json' };
import pendingFixture from './fixtures/cases_pending.json' with { type: 'json' };
import curveFixture from './fixtures/operating_curve.json' with { type: 'json' };

export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}
class NetworkError extends Error {}

let demo = new URLSearchParams(window.location.search).get('demo') === '1';
const copy = (value) => structuredClone(value);
const details = new Map([graded, abstained, retake, reviewed].map((c) => [c.case_id, copy(c)]));
let summaries = copy(allFixture.cases);
const pendingOrder = pendingFixture.cases.map((c) => c.case_id);
let reviewedOrder = summaries
  .filter((c) => ['accepted', 'overridden'].includes(c.status))
  .map((c) => c.case_id);
let decisionId = Math.max(...reviewed.decisions.map((d) => d.decision_id));
export const isDemoMode = () => demo;
export const DISCLAIMER =
  'Research prototype, not clinically validated. Final decision must be made by a qualified ophthalmologist.';
export const GRADE_LABELS = [
  'No DR',
  'Mild NPDR',
  'Moderate NPDR',
  'Severe NPDR',
  'Proliferative DR',
];
export const percent = (value) => (value == null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`);

async function request(path, options = {}, binary = false) {
  const response = await fetch(`/api${path}`, {
    ...options,
    signal: options.signal ?? AbortSignal.timeout(30000),
  }).catch(() => {
    throw new NetworkError(
      'Cannot reach the API. Check the service and VITE_API_PROXY, then retry.',
    );
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    // A gateway failure without an API envelope means the dev proxy could not
    // reach its upstream. Keep actual backend error envelopes as API errors.
    if ([502, 504].includes(response.status) && !body?.error) {
      throw new NetworkError('The API proxy cannot reach the backend. Check VITE_API_PROXY.');
    }
    throw new ApiError(
      body?.error?.message ?? `Request failed (${response.status}).`,
      body?.error?.code,
      response.status,
    );
  }
  if (binary) return response.blob();
  return response.json().catch(() => {
    throw new ApiError('The API returned invalid JSON.', 'invalid_response', response.status);
  });
}
export async function getHealth() {
  return demo ? copy(healthFixture) : request('/health', { signal: AbortSignal.timeout(5000) });
}
export async function initialiseApi() {
  try {
    return { health: await getHealth(), demo, notice: '' };
  } catch (error) {
    if (!(error instanceof NetworkError)) throw error;
    demo = true;
    return {
      health: copy(healthFixture),
      demo: true,
      notice:
        'API health check unreachable. Switched to fixture demo mode; changes last only for this page session.',
    };
  }
}
function summaryOf(c) {
  return {
    case_id: c.case_id,
    patient_id: c.patient_id,
    eye: c.eye,
    created_at: c.created_at,
    status: c.status,
    image_url: c.image_url,
    quality_ok: c.quality.ok,
    grade: c.prediction?.grade ?? null,
    grade_label: c.prediction?.grade_label ?? null,
    confidence: c.prediction?.confidence ?? null,
    abstained: c.prediction?.abstained ?? null,
    referable: c.prediction?.referable ?? null,
    priority: c.priority,
    final_grade: c.final_grade,
    mock: c.model.mock,
  };
}
function remember(c) {
  details.set(c.case_id, c);
  const index = summaries.findIndex((s) => s.case_id === c.case_id);
  if (index < 0) summaries.unshift(summaryOf(c));
  else summaries[index] = summaryOf(c);
  return copy(c);
}
export async function analyse(image, { patient_id, eye = 'unknown', outcome = 'graded' } = {}) {
  if (demo) {
    const c = copy({ graded, abstained, retake }[outcome] ?? graded);
    c.case_id = `demo_${crypto.randomUUID()}`;
    c.created_at = new Date().toISOString();
    if (patient_id?.trim()) c.patient_id = patient_id.trim();
    c.eye = eye;
    c.image_url = `/api/cases/${c.case_id}/image`;
    if (c.status === 'pending') pendingOrder.push(c.case_id);
    return remember(c);
  }
  const body = new FormData();
  body.append('image', image);
  if (patient_id?.trim()) body.append('patient_id', patient_id.trim());
  body.append('eye', eye);
  return request('/analyse', { method: 'POST', body });
}
export async function getCases(status = 'pending', limit = 50) {
  if (!demo) return request(`/cases?${new URLSearchParams({ status, limit })}`);
  let cases = summaries;
  if (status === 'pending')
    cases = pendingOrder
      .map((id) => summaries.find((c) => c.case_id === id))
      .filter((c) => c?.status === 'pending');
  else if (status === 'reviewed')
    cases = reviewedOrder.map((id) => summaries.find((c) => c.case_id === id));
  else if (status === 'retake') cases = summaries.filter((c) => c.status === 'retake');
  return copy({ cases: cases.slice(0, limit), total: cases.length });
}
export async function getCase(id) {
  if (!demo) return request(`/cases/${encodeURIComponent(id)}`);
  if (details.has(id)) return copy(details.get(id));
  const s = summaries.find((c) => c.case_id === id);
  if (!s) throw new ApiError('Case not found.', 'not_found', 404);
  // These two supplied summaries have no full fixture. Preserve known fields,
  // explicitly mark unavailable evidence; never manufacture probabilities.
  const c = {
    ...s,
    quality: { ok: s.quality_ok, metrics: {}, reasons: [] },
    prediction:
      s.grade == null
        ? null
        : {
            grade: s.grade,
            grade_label: s.grade_label,
            confidence: s.confidence,
            abstained: s.abstained,
            referable: s.referable,
            probs: null,
          },
    evidence: null,
    recommendation: null,
    decisions: [],
    model: copy(healthFixture.model),
    disclaimer: DISCLAIMER,
    fixturePartial: true,
  };
  details.set(id, c);
  return copy(c);
}
export async function postDecision(id, decision) {
  if (!demo)
    return request(`/cases/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(decision),
    });
  const c = await getCase(id);
  if (c.status === 'retake')
    throw new ApiError('Retake cases cannot be reviewed.', 'bad_request', 409);
  if (!decision.reviewer?.trim())
    throw new ApiError('Reviewer name is required.', 'validation_error', 422);
  if (
    !['accept', 'override'].includes(decision.action) ||
    (decision.action === 'override' &&
      (!Number.isInteger(decision.final_grade) ||
        decision.final_grade < 0 ||
        decision.final_grade > 4))
  ) {
    throw new ApiError('Select a final grade from 0 to 4.', 'validation_error', 422);
  }
  c.final_grade = decision.action === 'accept' ? c.prediction.grade : decision.final_grade;
  c.status = decision.action === 'accept' ? 'accepted' : 'overridden';
  c.decisions.push({
    ...decision,
    reviewer: decision.reviewer.trim(),
    final_grade: c.final_grade,
    decision_id: ++decisionId,
    case_id: id,
    created_at: new Date().toISOString(),
  });
  reviewedOrder = [id, ...reviewedOrder.filter((caseId) => caseId !== id)];
  return remember(c);
}
export async function getCaseImage(id) {
  return demo ? null : request(`/cases/${encodeURIComponent(id)}/image`, {}, true);
}
export async function getSimilarImage(id) {
  return demo ? null : request(`/similar/${encodeURIComponent(id)}.jpg`, {}, true);
}
export async function getOperatingCurve() {
  return demo ? copy(curveFixture) : request('/operating-curve');
}
