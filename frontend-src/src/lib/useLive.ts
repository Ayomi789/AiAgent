import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DiffData, type HistoryRun, type LiveState, type ScanStatus } from "./api";

function usePoll<T>(fn: () => Promise<T>, ms: number, initial: T): T {
  const [value, setValue] = useState<T>(initial);
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    let alive = true;
    const tick = () => {
      ref
        .current()
        .then((v) => {
          if (alive) setValue(v);
        })
        .catch(() => {
          /* transient (sleep/wake, aborted run) — keep last good state */
        });
    };
    tick();
    const id = window.setInterval(tick, ms);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [ms]);
  return value;
}

const IDLE: LiveState = {
  status: "idle",
  stage: "No run yet",
  target: "",
  findings: [],
  recent_actions: [],
  step: 0,
  max_steps: 0,
};

export function useLiveState(): LiveState {
  return usePoll(() => api.state().catch(() => IDLE), 1500, IDLE);
}

const IDLE_SCAN: ScanStatus = {
  running: false,
  config: null,
  skip_llm: false,
  started: null,
  returncode: null,
  log_tail: [],
};

export function useScanStatus(): ScanStatus {
  return usePoll(() => api.scanStatus().catch(() => IDLE_SCAN), 1500, IDLE_SCAN);
}

export function useHistory() {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const data = await api.history();
      setRuns(data.runs || []);
    } catch {
      /* keep last good list */
    } finally {
      setLoaded(true);
    }
  }, []);
  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 8000);
    return () => window.clearInterval(id);
  }, [refresh]);
  return { runs, loaded, refresh };
}

export function useDiff(): DiffData | null {
  const [diff, setDiff] = useState<DiffData | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .diff()
      .then((d) => {
        if (alive) setDiff(d);
      })
      .catch(() => {});
    const id = window.setInterval(() => {
      api
        .diff()
        .then((d) => {
          if (alive) setDiff(d);
        })
        .catch(() => {});
    }, 8000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);
  return diff;
}
