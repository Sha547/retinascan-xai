// Sample photos and how they are analysed.
//
// The samples are real fundus photographs from the IDRiD official test set (CC BY 4.0,
// see public/samples/ATTRIBUTION.txt), never used for training. With a live API they are
// uploaded and graded by the real model like any other photo. On a site without an API
// (e.g. a static host), the exact responses recorded from the real model are replayed
// (public/samples/recorded.json, made by scripts/record_samples.py).

import { analyse as analyseApi, analyseRecorded, isDemoMode } from './api.js';

let samples = [];

/** Load the sample list and recorded outputs. Returns the recorded data, or null. */
export async function loadSamples() {
  try {
    const response = await fetch('/samples/recorded.json');
    if (!response.ok) return null;
    const data = await response.json();
    samples = data.samples.map((s) => ({
      id: s.id,
      label: s.label,
      caption: s.caption,
      image: `/samples/${s.file}`,
      officialGrade: s.official_grade,
    }));
    return data;
  } catch {
    return null;
  }
}

export const getSamples = () => samples;

export async function analyse(scan, options) {
  if (isDemoMode()) {
    if (scan.sampleId) return analyseRecorded(scan.sampleId, options);
    throw new Error(
      'No live model is connected to this site, so your own photo cannot be graded here. ' +
        'Choose one of the sample photos, or run the app locally with the model (see README).',
    );
  }
  let file = scan.file;
  if (scan.sampleId) {
    const blob = await (await fetch(scan.image)).blob();
    file = new File([blob], `${scan.sampleId}.jpg`, { type: blob.type || 'image/jpeg' });
  }
  return analyseApi(file, options);
}
