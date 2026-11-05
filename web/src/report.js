import { jsPDF } from 'jspdf';
import { DISCLAIMER, GRADE_LABELS, percent } from './api.js';
import { capitalise, eyeLabel, formatDateTime, statusLabel } from './format.js';

export { formatDate } from './format.js';

const INK = [22, 25, 29];
const MUTED = [93, 102, 114];
const RULE = [190, 195, 202];
const SOFT = [228, 231, 235];

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not load an image for the report.'));
    img.src = src;
  });
}
/** The original and PNG overlay share aspect ratio and alignment; never crop either. */
export async function composeScan({ image, heatmap, overlay = false, opacity = 1, split = 0 }) {
  const img = await loadImage(image);
  const scale = Math.min(1, 1200 / Math.max(img.naturalWidth, img.naturalHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  if (overlay && heatmap) {
    const map = await loadImage(heatmap);
    ctx.save();
    ctx.beginPath();
    ctx.rect((canvas.width * split) / 100, 0, canvas.width * (1 - split / 100), canvas.height);
    ctx.clip();
    ctx.globalAlpha = opacity;
    ctx.drawImage(map, 0, 0, canvas.width, canvas.height);
    ctx.restore();
  }
  return { data: canvas.toDataURL('image/jpeg', 0.9), width: canvas.width, height: canvas.height };
}

export async function generateReport({
  result,
  scanImage,
  originalImage,
  similarImages = [],
  mock = false,
}) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const p = result.prediction;
  const margin = 18;
  const width = 210 - margin * 2;
  const bottom = 268;
  let y;

  const font = (size = 10, bold = false, color = INK) => {
    doc.setFont('helvetica', bold ? 'bold' : 'normal');
    doc.setFontSize(size);
    doc.setTextColor(...color);
  };
  const rule = (at, color = RULE, weight = 0.3) => {
    doc.setDrawColor(...color);
    doc.setLineWidth(weight);
    doc.line(margin, at, margin + width, at);
  };

  function header(first) {
    font(13, true);
    doc.text('RetinaScan XAI', margin, 18);
    font(9, false, MUTED);
    doc.text('Diabetic retinopathy screening: referral report', margin, 23.5);
    font(9, false, MUTED);
    doc.text(`Case ${result.case_id}`, margin + width, 18, { align: 'right' });
    doc.text(`Printed ${formatDateTime(new Date())}`, margin + width, 23.5, { align: 'right' });
    rule(27, INK, 0.5);
    y = 33;
    if (first) {
      font(10);
      doc.text('Primary health centre: ____________________________________________', margin, y);
      y += 7;
      doc.text('Referred to: ______________________________________________________', margin, y);
      y += 6;
    }
    if (mock || result.model.mock) {
      y += 2;
      font(10, true, [107, 63, 0]);
      doc.text('Mock model: outputs are not real predictions.', margin, y);
      y += 6;
    }
  }
  function ensure(height) {
    if (y + height > bottom) {
      doc.addPage();
      header(false);
    }
  }
  function heading(value, keep = 16) {
    ensure(keep + 12);
    y += 5;
    font(10.5, true);
    doc.text(value, margin, y);
    y += 2;
    rule(y);
    y += 5;
  }
  function paragraph(value, { size = 10, bold = false, color = INK } = {}) {
    font(size, bold, color);
    for (const line of doc.splitTextToSize(String(value), width)) {
      ensure(5.5);
      font(size, bold, color);
      doc.text(line, margin, y);
      y += size * 0.45 + 0.6;
    }
    y += 1.5;
  }
  /** Two-column label/value table; wraps long values. */
  function kvTable(rows, labelWidth = 52) {
    for (const [label, value, bold] of rows) {
      font(9.5);
      const lines = doc.splitTextToSize(String(value), width - labelWidth - 2);
      ensure(lines.length * 4.6 + 4);
      font(9.5, false, MUTED);
      doc.text(label, margin, y);
      font(9.5, bold);
      doc.text(lines, margin + labelWidth, y);
      const end = y + (lines.length - 1) * 4.6 + 1.8;
      rule(end, SOFT, 0.2);
      y = end + 4.6;
    }
  }
  function table(columns, rows) {
    // columns: [{ label, width, align }]
    const draw = (cells, bold, color) => {
      let x = margin;
      font(9.5, bold, color);
      cells.forEach((cell, i) => {
        const col = columns[i];
        const tx = col.align === 'right' ? x + col.width - 1 : x;
        doc.text(String(cell), tx, y, { align: col.align === 'right' ? 'right' : 'left' });
        x += col.width;
      });
    };
    ensure(12);
    draw(
      columns.map((c) => c.label),
      true,
      MUTED,
    );
    y += 1.6;
    rule(y, RULE, 0.25);
    y += 4.2;
    for (const row of rows) {
      ensure(6);
      draw(row.cells, row.bold, INK);
      y += 1.6;
      rule(y, SOFT, 0.2);
      y += 4.2;
    }
    y += 1;
  }
  function picture(image, x, top, w, h) {
    doc.setDrawColor(...RULE);
    doc.setLineWidth(0.2);
    if (image) {
      const scale = Math.min(w / image.width, h / image.height);
      const iw = image.width * scale;
      const ih = image.height * scale;
      doc.addImage(image.data, 'JPEG', x + (w - iw) / 2, top + (h - ih) / 2, iw, ih);
    } else {
      doc.rect(x, top, w, h);
      font(8, false, MUTED);
      doc.text('Image unavailable', x + w / 2, top + h / 2, { align: 'center' });
    }
  }

  header(true);

  heading('Patient and screening');
  kvTable([
    ['Patient ID', result.patient_id, true],
    ['Eye', eyeLabel(result.eye)],
    ['Case ID', result.case_id],
    ['Screened', formatDateTime(result.created_at)],
    ['Case status', statusLabel(result.status)],
  ]);

  heading('Model findings', 60);
  if (!p) paragraph('No grade: the image did not pass the quality check.', { bold: true });
  else {
    if (p.abstained)
      paragraph(
        'Not confident: routed to doctor for review. The grade below is tentative and the referable decision is pending doctor review.',
        { bold: true },
      );
    const prob =
      p.referable_prob != null ? ` (referable probability ${percent(p.referable_prob)})` : '';
    kvTable([
      [
        p.abstained ? 'Tentative grade (ICDR)' : 'Grade (ICDR)',
        `${p.grade}  ${p.grade_label}`,
        !p.abstained,
      ],
      ['Calibrated confidence', percent(p.confidence)],
      [
        'Referable decision',
        p.abstained
          ? `Pending doctor review; model's tentative call: ${p.referable ? 'referable' : 'not referable'}${prob}`
          : `${p.referable ? 'Referable' : 'Not referable'}${prob}`,
        !p.abstained,
      ],
    ]);
    if (p.probs) {
      y += 2;
      table(
        [
          { label: 'Grade', width: 18 },
          { label: 'Label', width: 60 },
          { label: 'Calibrated probability', width: 45, align: 'right' },
        ],
        p.probs.map((value, i) => ({
          cells: [i, GRADE_LABELS[i], percent(value)],
          bold: i === p.grade,
        })),
      );
    } else paragraph('Grade probabilities unavailable in this fixture.', { color: MUTED });
  }

  heading('Recommendation');
  paragraph(result.recommendation ?? 'Recommendation unavailable in this summary-only fixture.', {
    bold: true,
  });

  heading('Fundus image', 76);
  const imgW = (width - 8) / 2;
  const imgH = 58;
  ensure(imgH + 12);
  const top = y;
  picture(originalImage ?? null, margin, top, imgW, imgH);
  picture(scanImage, margin + imgW + 8, top, imgW, imgH);
  y = top + imgH + 4;
  font(8.5, false, MUTED);
  doc.text('Original', margin, y);
  doc.text('Grad-CAM overlay', margin + imgW + 8, y);
  y += 5;
  paragraph(result.evidence?.heatmap_note ?? 'Heatmap unavailable in this fixture.', { size: 9 });
  if (result.fixturePartial)
    paragraph('Summary-only fixture: full evidence and recommendation are unavailable.', {
      size: 9,
      color: MUTED,
    });

  heading('Similar training images', 70);
  const similar = result.evidence?.similar ?? [];
  if (!similar.length)
    paragraph('Similar-image evidence unavailable in this fixture.', { color: MUTED });
  else {
    const w = (width - 16) / 3;
    ensure(w + 14);
    const t = y;
    similar.forEach((item, index) => {
      const x = margin + index * (w + 8);
      picture(similarImages[index], x, t, w, w * 0.8);
      font(8.5);
      doc.text(
        doc.splitTextToSize(`Grade ${item.grade}  ${item.grade_label}`, w),
        x,
        t + w * 0.8 + 4.5,
      );
      font(8.5, false, MUTED);
      doc.text(`Distance ${Number(item.distance).toFixed(2)}`, x, t + w * 0.8 + 9);
    });
    y = t + w * 0.8 + 14;
  }

  heading('Doctor review');
  if (!result.decisions.length) paragraph('No reviewer decision recorded.', { color: MUTED });
  else {
    kvTable([['Final grade', `${result.final_grade}  ${GRADE_LABELS[result.final_grade]}`, true]]);
    y += 1;
    table(
      [
        { label: 'Time', width: 40 },
        { label: 'Reviewer', width: 42 },
        { label: 'Action', width: 24 },
        { label: 'Final grade', width: 40 },
      ],
      result.decisions.map((d) => ({
        cells: [
          formatDateTime(d.created_at),
          doc.splitTextToSize(d.reviewer, 40)[0],
          capitalise(d.action),
          `${d.final_grade}  ${GRADE_LABELS[d.final_grade]}`,
        ],
      })),
    );
    for (const d of result.decisions.filter((x) => x.note))
      paragraph(`Note (${d.reviewer}, ${formatDateTime(d.created_at)}): ${d.note}`, { size: 9 });
  }
  ensure(16);
  y += 8;
  font(10);
  doc.text('Reviewing ophthalmologist: ____________________________', margin, y);
  doc.text('Signature: ________________', margin + width, y, { align: 'right' });
  y += 4;

  heading('Model');
  kvTable([
    ['Model version', result.model.version],
    [
      'Calibration',
      result.model.calibrated_on
        ? `Temperature-scaled on ${result.model.calibrated_on} split`
        : '—',
    ],
  ]);

  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page++) {
    doc.setPage(page);
    rule(274, RULE, 0.3);
    font(8, false, MUTED);
    doc.text(doc.splitTextToSize(DISCLAIMER, width - 30), margin, 279);
    doc.text(`Page ${page} of ${pages}`, margin + width, 279, { align: 'right' });
    if (mock || result.model.mock) {
      font(8, true, [107, 63, 0]);
      doc.text('Mock model: outputs are not real predictions.', margin, 289);
    }
  }
  const safeId = result.case_id.replace(/[^\w-]/g, '');
  doc.save(`RetinaScan-referral-${safeId}.pdf`);
}
