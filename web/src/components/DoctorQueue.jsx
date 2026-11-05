import { useEffect, useState } from 'react';
import { getCases } from '../api.js';
import HistoryList from './HistoryList.jsx';

const FILTERS = [
  ['pending', 'Pending'],
  ['reviewed', 'Reviewed'],
  ['retake', 'Retake'],
  ['all', 'All'],
];
const EMPTY = {
  pending: 'No cases waiting for review.',
  reviewed: 'No reviewed cases yet.',
  retake: 'No cases need a retake.',
  all: 'No screenings recorded yet.',
};

export default function DoctorQueue({ onOpen, onMock, history = false }) {
  const [filter, setFilter] = useState(history ? 'all' : 'pending');
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
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
  function reload(nextFilter = filter) {
    setData(null);
    setError('');
    setFilter(nextFilter);
    setRefresh((n) => n + 1);
  }
  const Title = history ? 'h2' : 'h1';
  return (
    <section
      className={`panel queue ${history ? 'history' : 'screen'}`}
      aria-labelledby={`${history ? 'history' : 'queue'}-title`}
    >
      <div className="panel-head">
        <Title id={`${history ? 'history' : 'queue'}-title`}>
          {history ? 'Recent screenings' : 'Doctor queue'}
        </Title>
        <button type="button" className="btn btn-small" onClick={() => reload()}>
          Refresh
        </button>
      </div>
      <div className="queue-bar">
        {!history && (
          <div className="seg" role="group" aria-label="Case status">
            {FILTERS.map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={filter === id ? 'active' : ''}
                aria-pressed={filter === id}
                onClick={() => reload(id)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        {data && (
          <span className="muted num">
            {data.total} {data.total === 1 ? 'case' : 'cases'}
            {data.total > data.cases.length && `, showing ${data.cases.length}`}
            {!history && filter === 'pending' && ' · ordered by triage priority'}
          </span>
        )}
      </div>
      {error ? (
        <p className="callout tone-red" role="alert">
          {error}
        </p>
      ) : !data ? (
        <p className="panel-body muted" role="status">
          Loading cases…
        </p>
      ) : data.cases.length ? (
        <HistoryList entries={data.cases} onOpen={onOpen} numbered={!history} />
      ) : (
        <p className="empty-state">{EMPTY[filter]}</p>
      )}
    </section>
  );
}
