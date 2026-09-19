const STEPS = ['Upload', 'Quality check', 'AI analysis', 'Referral report'];

export default function Stepper({ current }) {
  return (
    <nav className="stepper" aria-label="Screening pipeline">
      {STEPS.map((label, i) => (
        <div className="step-group" key={label}>
          {i > 0 && <span className="step-line" />}
          <div
            className={`step ${i === current ? 'active' : ''} ${i < current ? 'done' : ''}`}
            aria-current={i === current ? 'step' : undefined}
          >
            <span className="step-num">{i < current ? '✓' : i + 1}</span>
            <span className="step-label">{label}</span>
          </div>
        </div>
      ))}
    </nav>
  );
}
