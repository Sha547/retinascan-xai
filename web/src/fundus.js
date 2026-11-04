/*
 * DEMO: synthetic "fundus photographs".
 *
 * A real deployment would receive actual retinal images from a fundus camera at
 * the PHC. For the presentation we draw stand-in retina images as SVG so the
 * demo has no external image dependencies and works fully offline.
 */

const VESSELS = [
  'M470,300 C400,250 320,230 190,190',
  'M470,300 C400,330 320,370 180,420',
  'M470,300 C420,215 400,140 380,70',
  'M470,300 C420,390 400,470 390,565',
  'M470,300 C380,295 300,305 120,300',
  'M400,262 C360,210 330,180 300,120',
  'M360,345 C320,395 300,430 290,490',
  'M300,300 C250,275 210,265 150,245',
  'M280,312 C240,340 205,355 150,365',
];

function vesselLayer() {
  return VESSELS.map(
    (d, i) =>
      `<path d="${d}" fill="none" stroke="#8d1f14" stroke-opacity="${0.85 - i * 0.04}" stroke-width="${
        i < 4 ? 9 - i : 4.5 - i * 0.2
      }" stroke-linecap="round"/>`,
  ).join('');
}

function dots(list, fill, opacity) {
  return list
    .map(([cx, cy, r]) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" fill-opacity="${opacity}"/>`)
    .join('');
}

/**
 * Build a fundus-style SVG as a data URI.
 * `lesions` are dark microaneurysm/haemorrhage dots, `exudates` are pale blobs.
 */
export function fundusSvg({ lesions = [], exudates = [], base = '#a53e13', core = '#c4611f' } = {}) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640">
  <defs>
    <radialGradient id="retina" cx="52%" cy="48%" r="62%">
      <stop offset="0%" stop-color="${core}"/>
      <stop offset="62%" stop-color="${base}"/>
      <stop offset="100%" stop-color="#481204"/>
    </radialGradient>
    <radialGradient id="disc" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffe9b8"/>
      <stop offset="70%" stop-color="#f2c777"/>
      <stop offset="100%" stop-color="#d99a4a" stop-opacity="0.35"/>
    </radialGradient>
    <radialGradient id="macula" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#6d1f09" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#6d1f09" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="globe"><circle cx="320" cy="320" r="300"/></clipPath>
  </defs>
  <rect width="640" height="640" fill="#120704"/>
  <g clip-path="url(#globe)">
    <circle cx="320" cy="320" r="300" fill="url(#retina)"/>
    ${vesselLayer()}
    <circle cx="470" cy="300" r="52" fill="url(#disc)"/>
    <circle cx="470" cy="300" r="22" fill="#f8d79a" fill-opacity="0.75"/>
    <circle cx="255" cy="330" r="105" fill="url(#macula)"/>
    ${dots(lesions, '#5a0c04', 0.92)}
    ${dots(exudates, '#fff2c4', 0.85)}
  </g>
  <circle cx="320" cy="320" r="299" fill="none" stroke="#000" stroke-opacity="0.45" stroke-width="2"/>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/**
 * Canvas drawing of SVG sources is inconsistent across browsers, so every image
 * the app handles is normalised to a square PNG data URI before it reaches the
 * results view and the PDF compositor.
 */
export function rasterise(src, size = 640) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#0d0603';
      ctx.fillRect(0, 0, size, size);
      // cover-fit the source into the square canvas
      const scale = Math.max(size / img.width, size / img.height);
      const w = img.width * scale;
      const h = img.height * scale;
      ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('Could not read image'));
    img.src = src;
  });
}
