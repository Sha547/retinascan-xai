/*
 * DEMO: stands in for a real Grad-CAM saliency map — blob positions come from
 * the pre-scripted result, not from model gradients.
 *
 * One draw routine shared by the on-screen overlay and the PDF report, so the
 * clinician's screen and the printed referral always show the same map.
 */

export const HEATMAP_SIZE = 640;

// Approximation of the "jet" colormap most Grad-CAM implementations use.
const RAMP = [
  [0.0, [190, 18, 60], 0.95],
  [0.26, [239, 68, 68], 0.82],
  [0.46, [251, 146, 60], 0.58],
  [0.66, [56, 189, 248], 0.34],
  [0.86, [37, 99, 235], 0.16],
  [1.0, [37, 99, 235], 0],
];

/** A primary activation blob, plus a weaker secondary one on higher grades. */
function blobsFor(map) {
  return [
    { x: map.x, y: map.y, size: map.size, scale: 1 },
    ...(map.intensity > 0.5 ? [{ x: map.x + 12, y: map.y + 20, size: map.size * 0.6, scale: 0.62 }] : []),
  ];
}

export function drawHeatmap(ctx, map, size = HEATMAP_SIZE) {
  ctx.save();
  ctx.filter = `blur(${Math.round(size * 0.022)}px)`;

  blobsFor(map).forEach((b) => {
    const cx = (b.x / 100) * size;
    const cy = (b.y / 100) * size;
    const r = ((b.size / 100) * size) / 2;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    RAMP.forEach(([stop, [red, green, blue], alpha]) => {
      grad.addColorStop(stop, `rgba(${red}, ${green}, ${blue}, ${alpha * map.intensity * b.scale})`);
    });
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
}
