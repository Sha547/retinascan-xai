import { BrandMark } from './Icons.jsx';

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="brand">
        <BrandMark className="brand-mark" />
        <span className="brand-name">RetinaScan XAI</span>
        <span className="brand-sep" />
        <span className="brand-sub">Explainable AI for Diabetic Retinopathy Screening</span>
      </div>
      <div className="topbar-right">
        <span className="demo-tag" title="Results are pre-scripted, not model output">Demo build</span>
        <span className="team-badge">
          <span className="dot" />
          MMDC Team
        </span>
      </div>
    </header>
  );
}
