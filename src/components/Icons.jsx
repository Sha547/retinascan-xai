const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export function UploadIcon(props) {
  return (
    <svg {...base} width={26} height={26} {...props}>
      <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

export function CheckIcon(props) {
  return (
    <svg {...base} width={12} height={12} strokeWidth={3} {...props}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function CheckCircleIcon(props) {
  return (
    <svg {...base} width={30} height={30} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.3l2.4 2.4 4.6-4.9" />
    </svg>
  );
}

export function DocIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  );
}

export function ScanIcon(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    </svg>
  );
}

export function RefreshIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 4v4h-4" />
    </svg>
  );
}

export function BrandMark(props) {
  return (
    <svg viewBox="0 0 32 32" width={28} height={28} {...props}>
      <rect width="32" height="32" rx="9" fill="#0B2545" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="#0D9488" strokeWidth="2.2" />
      <circle cx="16" cy="16" r="3.2" fill="#0D9488" />
      <path d="M16 4.5v3M16 24.5v3M4.5 16h3M24.5 16h3" stroke="#3E6C96" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
