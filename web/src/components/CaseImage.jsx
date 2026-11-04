import { useEffect, useState } from 'react';
import { getCaseImage, getSimilarImage, isDemoMode } from '../api.js';

export default function CaseImage({ id, similar = false, alt, className = '', onSize, onReady }) {
  const [state, setState] = useState({ url: null, error: '', loading: true });
  useEffect(() => {
    let active = true;
    let url;
    (similar ? getSimilarImage(id) : getCaseImage(id)).then(blob => {
      if (!active) return;
      url = blob ? URL.createObjectURL(blob) : null;
      setState({ url, error: '', loading: false });
    }).catch(error => { if (active) setState({ url: null, error: error.message, loading: false }); });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [id, similar]);
  if (!state.url) return <div className={`image-placeholder ${className}`} role="img" aria-label={alt}>
    {state.error || (state.loading ? 'Loading image…' : isDemoMode() ? 'Image unavailable in fixture demo' : 'Image unavailable')}
  </div>;
  return <img className={className} src={state.url} alt={alt}
    onLoad={event => { onSize?.(event.currentTarget.naturalWidth / event.currentTarget.naturalHeight); onReady?.(true); }}
    onError={() => { onReady?.(false); setState({ url: null, loading: false, error: 'Image could not be displayed.' }); }} />;
}
