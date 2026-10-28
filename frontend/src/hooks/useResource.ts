import { useEffect, useState } from 'react';
import type { ResourceResult } from '../api/resources';

/** Components supply a stable loader; cleanup owns every pending response. */
export function useResource<T>(load: (signal: AbortSignal) => Promise<ResourceResult<T>>) {
  const [state, setState] = useState<{ load: typeof load; result: ResourceResult<T> } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    void load(controller.signal).then(result => {
      if (current && !controller.signal.aborted) setState({ load, result });
    }).catch(() => {
      if (current && !controller.signal.aborted) {
        setState({ load, result: { ok: false, kind: 'network', status: null, message: 'Unable to load data. Please try again.' } });
      }
    });
    return () => { current = false; controller.abort(); };
  }, [load]);
  // Hide old results immediately on a scope/query change, before effect cleanup.
  return state?.load === load ? state.result : null;
}
