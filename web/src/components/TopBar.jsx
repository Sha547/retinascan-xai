export default function TopBar({ page, onNavigate, disabled, modelVersion }) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-name">RetinaScan XAI</span>
        <span className="brand-sub">
          Diabetic retinopathy screening
          {modelVersion && (
            <>
              {' · model '}
              <span className="mono">{modelVersion}</span>
            </>
          )}
        </span>
      </div>
      <nav className="topnav" aria-label="Main navigation">
        {[
          ['screening', 'Screening'],
          ['queue', 'Doctor queue'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={page === id ? 'active' : ''}
            aria-current={page === id ? 'page' : undefined}
            disabled={disabled}
            onClick={() => onNavigate(id)}
          >
            {label}
          </button>
        ))}
      </nav>
    </header>
  );
}
