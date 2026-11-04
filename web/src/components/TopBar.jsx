import { BrandMark } from './Icons.jsx';

export default function TopBar({ page, onNavigate, disabled }) {
  return <header className="topbar">
    <div className="brand"><BrandMark className="brand-mark" /><span className="brand-name">RetinaScan XAI</span>
      <span className="brand-sep" /><span className="brand-sub">Diabetic retinopathy screening</span></div>
    <nav className="topbar-right" aria-label="Main navigation">
      <button className={`seg-btn ${page === 'screening' ? 'active' : ''}`} aria-current={page === 'screening' ? 'page' : undefined}
        disabled={disabled} onClick={() => onNavigate('screening')}>Screening</button>
      <button className={`seg-btn ${page === 'queue' ? 'active' : ''}`} aria-current={page === 'queue' ? 'page' : undefined}
        disabled={disabled} onClick={() => onNavigate('queue')}>Doctor queue</button>
    </nav>
  </header>;
}
