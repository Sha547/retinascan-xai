/*
 * DEMO: hardcoded for presentation, replace with real model inference API call.
 *
 * This module is the single seam between the UI and "the model". In production
 * `analyse()` would POST the image to the inference service and return the same
 * shape: { gradeLabel, severity, confidence, explanation, referral, heatmap }.
 * Nothing else in the app knows how the result was produced.
 */

import { fundusSvg } from './fundus.js';

const HEALTHY_LESIONS = [];
const MODERATE_LESIONS = [
  [300, 215, 7],
  [332, 196, 5],
  [270, 238, 6],
  [355, 240, 4],
  [242, 205, 5],
  [318, 258, 4],
];
const SEVERE_LESIONS = [
  [300, 215, 9],
  [330, 190, 7],
  [262, 240, 8],
  [356, 246, 6],
  [238, 200, 7],
  [318, 262, 6],
  [210, 300, 8],
  [268, 402, 7],
  [330, 430, 6],
  [400, 380, 5],
  [180, 350, 6],
  [420, 190, 6],
];
const SEVERE_EXUDATES = [
  [286, 250, 11],
  [340, 300, 8],
  [230, 268, 7],
  [372, 208, 6],
];

/** The three demo scans offered on the upload screen. */
export const SAMPLES = [
  {
    id: 'healthy',
    label: 'Sample: Healthy',
    caption: 'Right eye · 45° field',
    image: fundusSvg({ lesions: HEALTHY_LESIONS, base: '#aa4517', core: '#cc6c26' }),
  },
  {
    id: 'moderate',
    label: 'Sample: Moderate DR',
    caption: 'Left eye · 45° field',
    image: fundusSvg({ lesions: MODERATE_LESIONS, base: '#a33e12', core: '#c4611e' }),
  },
  {
    id: 'severe',
    label: 'Sample: Severe DR',
    caption: 'Right eye · 50° field',
    image: fundusSvg({ lesions: SEVERE_LESIONS, exudates: SEVERE_EXUDATES, base: '#9a350f', core: '#ba5518' }),
  },
];

/*
 * DEMO: hardcoded for presentation, replace with real model inference API call.
 * Grades, confidence scores, saliency positions and explanation text below are
 * pre-scripted per sample rather than predicted.
 */
const RESULTS = {
  healthy: {
    severity: 0,
    gradeLabel: 'Grade 0 — No DR',
    tone: 'green',
    confidence: 96,
    explanation:
      'No microaneurysms, haemorrhages or exudates detected. Optic disc margins are sharp and the macula is clear, consistent with no diabetic retinopathy.',
    referral: 'Routine follow-up in 12 months.',
    // Saliency is diffuse and low-intensity when the model finds no pathology.
    heatmap: { x: 48, y: 50, size: 54, intensity: 0.22 },
    findings: [
      ['Microaneurysms', 'None detected'],
      ['Haemorrhages', 'None detected'],
      ['Hard exudates', 'None detected'],
      ['Neovascularisation', 'None detected'],
    ],
  },
  moderate: {
    severity: 2,
    gradeLabel: 'Grade 2 — Moderate DR',
    tone: 'orange',
    confidence: 92,
    explanation:
      'Model detected microaneurysms and dot-blot haemorrhages in the superior temporal region, with mild venous beading, consistent with Moderate DR.',
    referral: 'Refer to ophthalmologist within 30 days.',
    heatmap: { x: 46, y: 35, size: 33, intensity: 0.8 },
    findings: [
      ['Microaneurysms', '6 detected — superior temporal'],
      ['Haemorrhages', 'Dot-blot, 2 quadrants'],
      ['Hard exudates', 'None detected'],
      ['Neovascularisation', 'None detected'],
    ],
  },
  severe: {
    severity: 4,
    gradeLabel: 'Grade 4 — Proliferative DR',
    tone: 'red',
    confidence: 94,
    explanation:
      'Model detected extensive haemorrhages across all four quadrants, hard exudates encroaching on the macula and features suggestive of neovascularisation, consistent with Proliferative DR.',
    referral: 'Urgent referral required.',
    heatmap: { x: 44, y: 36, size: 40, intensity: 0.9 },
    findings: [
      ['Microaneurysms', '12+ detected — all quadrants'],
      ['Haemorrhages', 'Extensive, 4 quadrants'],
      ['Hard exudates', 'Present — macular involvement'],
      ['Neovascularisation', 'Suspected at disc'],
    ],
  },
};

/** Any real upload falls back to the Moderate DR script. */
export const FALLBACK_SAMPLE_ID = 'moderate';

export function gradeFor(sampleId) {
  return RESULTS[sampleId] ?? RESULTS[FALLBACK_SAMPLE_ID];
}

/**
 * DEMO: hardcoded for presentation, replace with real model inference API call.
 * e.g. `const res = await fetch(INFERENCE_URL, { method: 'POST', body: form })`.
 */
export function analyse(sampleId, { delay = 1500 } = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(gradeFor(sampleId)), delay);
  });
}

/** DEMO: stands in for the PHC's patient record system. */
export function makePatientId() {
  const n = String(Math.floor(Math.random() * 99999)).padStart(5, '0');
  return `PHC-${new Date().getFullYear()}-${n}`;
}
