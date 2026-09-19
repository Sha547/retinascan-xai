/*
 * Client-side PDF referral report — no server involved.
 *
 * The scan thumbnail is composited in a canvas from the same image and the same
 * `drawHeatmap` routine the results screen uses, so the embedded picture is
 * identical to what was on screen.
 */

import { jsPDF } from 'jspdf';
import { drawHeatmap, HEATMAP_SIZE } from './heatmap.js';

const NAVY = [11, 37, 69];
const TEAL = [13, 148, 136];
const INK = [30, 41, 59];
const MUTED = [100, 116, 139];
const HAIRLINE = [214, 222, 232];

const TONE_RGB = {
  green: [22, 128, 91],
  orange: [194, 100, 12],
  red: [190, 46, 42],
};

export function formatDate(date = new Date()) {
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** Render the scan plus its saliency overlay to a JPEG data URI for the PDF. */
export function composeScan({ image, map, overlay = true }) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = HEATMAP_SIZE;
      canvas.height = HEATMAP_SIZE;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#0d0603';
      ctx.fillRect(0, 0, HEATMAP_SIZE, HEATMAP_SIZE);
      ctx.drawImage(img, 0, 0, HEATMAP_SIZE, HEATMAP_SIZE);
      if (overlay) drawHeatmap(ctx, map);
      resolve(canvas.toDataURL('image/jpeg', 0.92));
    };
    // The report is still useful without the thumbnail, so never block on this.
    img.onerror = () => resolve(null);
    img.src = image;
  });
}

export async function generateReport({ result, patientId, scanImage, fileName }) {
  const scan = scanImage;
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const pageW = 210;
  const M = 16;
  const tone = TONE_RGB[result.tone] ?? INK;

  // ---- Header band -------------------------------------------------------
  doc.setFillColor(...NAVY);
  doc.rect(0, 0, pageW, 30, 'F');
  doc.setFillColor(...TEAL);
  doc.rect(0, 30, pageW, 1.2, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(15);
  doc.text('RetinaScan XAI', M, 15);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9.5);
  doc.setTextColor(186, 208, 224);
  doc.text('Diabetic Retinopathy Screening Report', M, 21.5);
  doc.setFontSize(8);
  doc.text('MMDC Team', pageW - M, 15, { align: 'right' });
  doc.text('Explainable AI Screening', pageW - M, 20, { align: 'right' });

  // ---- Patient / scan metadata ------------------------------------------
  let y = 44;
  const meta = [
    ['Patient ID', patientId],
    ['Report date', formatDate()],
    ['Source image', fileName || 'Demo sample scan'],
    ['Screening site', 'Primary Health Centre — Teleophthalmology Unit'],
  ];
  doc.setFontSize(8);
  meta.forEach(([label, value], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = M + col * 92;
    const ly = y + row * 11;
    doc.setTextColor(...MUTED);
    doc.setFont('helvetica', 'normal');
    doc.text(label.toUpperCase(), x, ly);
    doc.setTextColor(...INK);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(String(value), x, ly + 5);
    doc.setFontSize(8);
  });

  y += 20;
  doc.setDrawColor(...HAIRLINE);
  doc.setLineWidth(0.3);
  doc.line(M, y, pageW - M, y);

  // ---- Scan + Grad-CAM overlay ------------------------------------------
  y += 9;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10.5);
  doc.setTextColor(...NAVY);
  doc.text('Retinal scan with Grad-CAM saliency overlay', M, y);

  y += 4;
  const imgSize = 72;
  if (scan) {
    doc.addImage(scan, 'JPEG', M, y, imgSize, imgSize);
  } else {
    doc.setFillColor(240, 244, 248);
    doc.rect(M, y, imgSize, imgSize, 'F');
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text('Scan image unavailable', M + imgSize / 2, y + imgSize / 2, { align: 'center' });
  }
  doc.setDrawColor(...HAIRLINE);
  doc.rect(M, y, imgSize, imgSize);

  // ---- Grade + confidence panel -----------------------------------------
  const px = M + imgSize + 10;
  const pw = pageW - M - px;
  let py = y + 2;

  doc.setFillColor(...tone);
  doc.roundedRect(px, py, pw, 13, 2, 2, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text(result.gradeLabel.replace('—', '-'), px + 5, py + 8.6);

  py += 20;
  doc.setTextColor(...MUTED);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.text('MODEL CONFIDENCE', px, py);
  doc.setTextColor(...NAVY);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(20);
  doc.text(`${result.confidence}%`, px, py + 9);

  // confidence bar
  const barY = py + 13;
  doc.setFillColor(...HAIRLINE);
  doc.roundedRect(px, barY, pw, 2.4, 1.2, 1.2, 'F');
  doc.setFillColor(...TEAL);
  doc.roundedRect(px, barY, (pw * result.confidence) / 100, 2.4, 1.2, 1.2, 'F');

  // findings table
  py = barY + 10;
  doc.setFontSize(8);
  doc.setTextColor(...MUTED);
  doc.setFont('helvetica', 'normal');
  doc.text('DETECTED FEATURES', px, py);
  py += 4.5;
  result.findings.forEach(([label, value]) => {
    doc.setDrawColor(...HAIRLINE);
    doc.line(px, py, px + pw, py);
    py += 4.6;
    doc.setTextColor(...INK);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.text(label, px, py);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...MUTED);
    doc.text(value, px + pw, py, { align: 'right' });
    py += 2.4;
  });

  // ---- Explanation -------------------------------------------------------
  y += imgSize + 12;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10.5);
  doc.setTextColor(...NAVY);
  doc.text('AI explanation', M, y);
  y += 6;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9.5);
  doc.setTextColor(...INK);
  const lines = doc.splitTextToSize(result.explanation, pageW - M * 2);
  doc.text(lines, M, y);
  y += lines.length * 5 + 6;

  // ---- Referral recommendation ------------------------------------------
  doc.setFillColor(243, 247, 250);
  doc.roundedRect(M, y, pageW - M * 2, 20, 2, 2, 'F');
  doc.setFillColor(...tone);
  doc.roundedRect(M, y, 1.6, 20, 0.8, 0.8, 'F');
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...MUTED);
  doc.text('REFERRAL RECOMMENDATION', M + 6, y + 7.5);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11.5);
  doc.setTextColor(...NAVY);
  doc.text(result.referral, M + 6, y + 15);

  // ---- Clinical notes ----------------------------------------------------
  y += 28;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10.5);
  doc.setTextColor(...NAVY);
  doc.text('Clinician notes', M, y);
  y += 6;
  doc.setDrawColor(...HAIRLINE);
  for (let i = 0; i < 4; i += 1) {
    doc.line(M, y + i * 9, pageW - M, y + i * 9);
  }
  y += 34;

  // ---- Signature + footer ------------------------------------------------
  y += 10;
  doc.setDrawColor(...HAIRLINE);
  doc.line(M, y, M + 60, y);
  doc.line(pageW - M - 60, y, pageW - M, y);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...MUTED);
  doc.text('Screening technician', M, y + 5);
  doc.text('Reviewing ophthalmologist', pageW - M, y + 5, { align: 'right' });

  doc.setDrawColor(...HAIRLINE);
  doc.line(M, 276, pageW - M, 276);
  doc.setFontSize(7.5);
  doc.setTextColor(...MUTED);
  const footer = doc.splitTextToSize(
    'Generated by RetinaScan XAI — for clinical validation only. Final diagnosis must be confirmed by a licensed ophthalmologist.',
    pageW - M * 2,
  );
  doc.text(footer, M, 281);
  doc.text(`${patientId} · Page 1 of 1`, pageW - M, 291, { align: 'right' });

  const fileSafeId = patientId.replace(/[^\w-]/g, '');
  doc.save(`RetinaScan-XAI-Report-${fileSafeId}.pdf`);
}
