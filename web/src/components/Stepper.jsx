const STEPS = ['Upload', 'Quality check', 'Grading', 'Referral report'];

export default function Stepper({ current }) {
  return (
    <ol className="stepper" aria-label="Screening steps">
      {STEPS.map((label, i) => (
        <li
          key={label}
          className={i === current ? 'active' : i < current ? 'done' : ''}
          aria-current={i === current ? 'step' : undefined}
        >
          <span className="step-num">{i + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}
