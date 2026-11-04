import { fundusSvg, rasterise } from './fundus.js';
import { analyse as analyseApi, isDemoMode } from './api.js';

export const SAMPLES = [
  {
    id: 'graded',
    label: 'Sample: graded fixture',
    caption: 'Synthetic illustration',
    image: fundusSvg(),
  },
  {
    id: 'abstained',
    label: 'Sample: abstained fixture',
    caption: 'Synthetic illustration',
    image: fundusSvg({ base: '#963d18' }),
  },
  {
    id: 'retake',
    label: 'Sample: retake fixture',
    caption: 'Synthetic illustration',
    image: fundusSvg({ base: '#461d0b', core: '#53290e' }),
  },
];

export async function analyse(scan, options) {
  let file = scan.file;
  if (scan.sampleId && !isDemoMode()) {
    const png = await rasterise(scan.image);
    file = new File([await (await fetch(png)).blob()], 'synthetic-sample.png', {
      type: 'image/png',
    });
  }
  return analyseApi(file, { ...options, outcome: scan.sampleId ?? options.outcome });
}
