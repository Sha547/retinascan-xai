import { jsPDF } from 'jspdf';
import { DISCLAIMER, GRADE_LABELS, percent } from './api.js';

const NAVY = [11, 37, 69];
const TEAL = [13, 148, 136];
const INK = [30, 41, 59];
const MUTED = [80, 98, 120];
export function formatDate(date = new Date()) {
  return new Date(date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}
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
  ctx.fillStyle = '#0d0603'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  if (overlay && heatmap) {
    const map = await loadImage(heatmap);
    ctx.save(); ctx.beginPath();
    ctx.rect(canvas.width * split / 100, 0, canvas.width * (1 - split / 100), canvas.height); ctx.clip();
    ctx.globalAlpha = opacity; ctx.drawImage(map, 0, 0, canvas.width, canvas.height); ctx.restore();
  }
  return { data: canvas.toDataURL('image/jpeg', 0.9), width: canvas.width, height: canvas.height };
}
export async function generateReport({ result, scanImage, similarImages = [], mock = false }) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const p = result.prediction;
  const margin = 16;
  const width = 178;
  let y;
  function header() {
    doc.setFillColor(...NAVY); doc.rect(0, 0, 210, 28, 'F');
    doc.setFillColor(...TEAL); doc.rect(0, 28, 210, 1, 'F');
    doc.setTextColor(255, 255, 255); doc.setFont('helvetica', 'bold'); doc.setFontSize(15);
    doc.text('RetinaScan XAI', margin, 13);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(9);
    doc.text('Diabetic Retinopathy Screening Report', margin, 21);
    y = 38;
    if (mock || result.model.mock) {
      doc.setTextColor(140, 48, 22); doc.setFont('helvetica', 'bold'); doc.setFontSize(10);
      doc.text('Mock model: outputs are not real predictions.', margin, y); y += 10;
    }
  }
  function ensure(height) { if (y + height > 267) { doc.addPage(); header(); } }
  function text(value, { bold = false, size = 10, color = INK } = {}) {
    doc.setFont('helvetica', bold ? 'bold' : 'normal'); doc.setFontSize(size); doc.setTextColor(...color);
    const lines = doc.splitTextToSize(String(value), width);
    for (const line of lines) {
      ensure(6); doc.setFont('helvetica', bold ? 'bold' : 'normal'); doc.setFontSize(size); doc.setTextColor(...color);
      doc.text(line, margin, y); y += 5;
    }
    y += 2;
  }
  function heading(value) { ensure(15); y += 3; text(value, { bold: true, size: 11, color: NAVY }); }
  function picture(image, x, top, w, h) {
    if (image) {
      const scale = Math.min(w / image.width, h / image.height);
      const iw = image.width * scale, ih = image.height * scale;
      doc.addImage(image.data, 'JPEG', x + (w - iw) / 2, top + (h - ih) / 2, iw, ih);
    } else {
      doc.setFillColor(240, 244, 248); doc.rect(x, top, w, h, 'F');
      doc.setTextColor(...MUTED); doc.setFont('helvetica', 'normal'); doc.setFontSize(8);
      doc.text('Image unavailable', x + w / 2, top + h / 2, { align: 'center' });
    }
  }
  header();
  text(`Patient ID: ${result.patient_id}`, { bold: true });
  text(`Case ID: ${result.case_id}`);
  text(`Screening date: ${new Date(result.created_at).toISOString()} | Eye: ${result.eye}`);
  text(`Model version: ${result.model.version} | Status: ${result.status}`);
  heading('Model screening output');
  if (!p) text('No grade: image quality failed.', { bold: true });
  else {
    if (p.abstained) text('Not confident: routed to doctor for review', { bold: true, size: 12 });
    text(`${p.abstained ? "Model's tentative grade" : 'Grade'}: ${p.grade} - ${p.grade_label}`, { size: p.abstained ? 9 : 11, bold: !p.abstained });
    text(`Calibrated confidence: ${percent(p.confidence)} | Abstained: ${p.abstained ? 'Yes' : 'No'}`);
    text(`Referable decision: ${p.referable ? 'Referable' : 'Not referable'}`);
    if (p.referable_prob != null) text(`Referable probability: ${percent(p.referable_prob)}`);
  }
  heading('Recommendation'); text(result.recommendation ?? 'Recommendation unavailable in this summary-only fixture.');
  heading('Scan with heatmap');
  ensure(78); picture(scanImage, margin, y, 90, 70); y += 74;
  text(result.evidence?.heatmap_note ?? 'Heatmap unavailable in this fixture.', { size: 9 });
  if (result.fixturePartial) text('Summary-only fixture: full evidence and recommendation are unavailable.', { size: 9 });
  heading('Similar cases from the training set');
  const similar = result.evidence?.similar ?? [];
  if (!similar.length) text('Similar-case evidence unavailable in this fixture.');
  else {
    ensure(79);
    const top = y;
    similar.forEach((item, index) => {
      const x = margin + index * 61;
      picture(similarImages[index], x, top, 55, 45);
      doc.setFont('helvetica', 'normal'); doc.setTextColor(...INK); doc.setFontSize(8);
      const label = doc.splitTextToSize(`Known grade ${item.grade}: ${item.grade_label}`, 55);
      doc.text(label, x, top + 50);
      doc.text(`Distance: ${item.distance}`, x, top + 50 + label.length * 4);
    });
    y += 78;
  }
  heading('Reviewer decision history');
  if (!result.decisions.length) text('No reviewer decision recorded.');
  else {
    text(`Current final grade: ${result.final_grade} - ${GRADE_LABELS[result.final_grade]}`, { bold: true });
    for (const d of result.decisions) {
      text(`${d.created_at} | ${d.reviewer} | ${d.action} | Final grade ${d.final_grade} (${GRADE_LABELS[d.final_grade]})`);
      if (d.note) text(d.note);
    }
  }
  for (let page = 1; page <= doc.getNumberOfPages(); page++) {
    doc.setPage(page); doc.setFont('helvetica', 'normal'); doc.setFontSize(8); doc.setTextColor(...MUTED);
    doc.text(doc.splitTextToSize(DISCLAIMER, width), margin, 278);
    doc.text(`Page ${page} of ${doc.getNumberOfPages()}`, 194, 292, { align: 'right' });
  }
  const safeId = result.case_id.replace(/[^\w-]/g, '');
  doc.save(`RetinaScan-XAI-Report-${safeId}.pdf`);
}
