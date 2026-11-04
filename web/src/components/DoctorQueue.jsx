import { useEffect, useState } from 'react';
import { getCases } from '../api.js';
import HistoryList from './HistoryList.jsx';

export default function DoctorQueue({ onOpen, onMock, history = false }) {
  const [filter, setFilter] = useState(history ? 'all' : 'pending');
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    getCases(filter)
      .then((response) => {
        if (!active) return;
        setData(response);
        if (response.cases.some((c) => c.mock)) onMock();
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [filter, refresh, onMock]);
  return (
    <section className={`card queue ${history ? 'history' : 'screen'}`}>
      <div className="queue-head">
        {history ? <h2>Recent screenings</h2> : <h1>Doctor queue</h1>}
        <button className="btn btn-ghost" onClick={() => setRefresh((n) => n + 1)}>
          Refresh {history ? 'screenings' : 'queue'}
        </button>
      </div>
      {!history && (
        <div className="seg queue-filters" role="group" aria-label="Case status">
          {['pending', 'reviewed', 'retake', 'all'].map((s) => (
            <button
              key={s}
              className={`seg-btn ${filter === s ? 'active' : ''}`}
              aria-pressed={filter === s}
              onClick={() => setFilter(s)}
            >
              {s[0].toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      )}
      {error ? (
        <p className="notice error" role="alert">
          {error}
        </p>
      ) : !data ? (
        <p role="status">Loading screenings…</p>
      ) : (
        <>
          <p className="queue-count">
            {data.total} {history ? 'screenings' : `${filter} cases`}
            {data.total > data.cases.length && ` · showing ${data.cases.length}`}
          </p>
          {data.cases.length ? (
            <HistoryList entries={data.cases} onOpen={onOpen} />
          ) : (
            <p className="empty-state">No {filter === 'all' ? '' : `${filter} `}screenings.</p>
          )}
        </>
      )}
    </section>
  );
}
