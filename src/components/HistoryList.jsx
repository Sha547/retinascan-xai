const formatter = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export default function HistoryList({ entries, onClear }) {
  if (entries.length === 0) return null;

  return (
    <section className="card history" aria-label="Recent screenings">
      <div className="history-head">
        <h3>Recent screenings</h3>
        <button type="button" className="link-btn" onClick={onClear}>
          Clear
        </button>
      </div>
      <ul className="history-list">
        {entries.map((e) => (
          <li key={e.patientId} className="history-row">
            <span className="history-id">{e.patientId}</span>
            <span className="history-name">{e.scanName}</span>
            <span className={`badge ${e.tone}`}>{e.gradeLabel.replace(/^Grade \d — /, '')}</span>
            <span className="history-conf">{e.confidence}%</span>
            <time className="history-time" dateTime={e.at}>
              {formatter.format(new Date(e.at))}
            </time>
          </li>
        ))}
      </ul>
    </section>
  );
}
