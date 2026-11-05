// Display formatting only. Every value comes from the API or a fixture.

export function formatDate(date = new Date()) {
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatDateTime(date) {
  if (!date) return '—';
  return new Date(date).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export const capitalise = (value) =>
  value ? String(value)[0].toUpperCase() + String(value).slice(1) : '—';

export const eyeLabel = (eye) => capitalise(eye ?? 'unknown');

export const STATUS_LABELS = {
  pending: 'Pending',
  accepted: 'Accepted',
  overridden: 'Overridden',
  retake: 'Retake',
};
export const statusLabel = (status) => STATUS_LABELS[status] ?? capitalise(status);

const METRICS = {
  sharpness: { label: 'Sharpness', format: (v) => v.toFixed(1) },
  brightness: { label: 'Brightness (0–255)', format: (v) => v.toFixed(0) },
  contrast: { label: 'Contrast', format: (v) => v.toFixed(1) },
  field_coverage: { label: 'Field coverage', format: (v) => `${(v * 100).toFixed(1)}%` },
  glare_fraction: { label: 'Glare', format: (v) => `${(v * 100).toFixed(1)}%` },
};

/** [[label, formattedValue], ...] in API order. Unknown metrics are shown with 2 decimals. */
export function formatMetrics(metrics = {}) {
  return Object.entries(metrics).map(([name, value]) => {
    const spec = METRICS[name];
    const label = spec?.label ?? capitalise(name.replaceAll('_', ' '));
    if (typeof value !== 'number' || !Number.isFinite(value)) return [name, label, String(value)];
    return [name, label, spec ? spec.format(value) : value.toFixed(2)];
  });
}
