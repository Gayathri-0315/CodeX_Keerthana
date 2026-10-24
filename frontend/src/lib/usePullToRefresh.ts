import { useEffect, useRef, useState } from "react";

const TRIGGER_PX = 70;

/** Touch pull-down at the top of the page. Returns the current pull distance for an indicator. */
export function usePullToRefresh(onRefresh: () => Promise<unknown>) {
  const [pull, setPull] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const latest = useRef(onRefresh);
  latest.current = onRefresh;

  useEffect(() => {
    let startY = -1;
    let current = 0;
    const onStart = (e: TouchEvent) => {
      startY = window.scrollY <= 0 ? e.touches[0].clientY : -1;
    };
    const onMove = (e: TouchEvent) => {
      if (startY < 0) return;
      const dy = e.touches[0].clientY - startY;
      current = dy > 0 ? Math.min(110, dy * 0.5) : 0;
      setPull(current);
    };
    const onEnd = () => {
      if (startY >= 0 && current >= TRIGGER_PX * 0.5) {
        setRefreshing(true);
        latest.current().finally(() => setRefreshing(false));
      }
      startY = -1;
      current = 0;
      setPull(0);
    };
    window.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("touchmove", onMove, { passive: true });
    window.addEventListener("touchend", onEnd);
    return () => {
      window.removeEventListener("touchstart", onStart);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend", onEnd);
    };
  }, []);

  return { pull, refreshing, ready: pull >= TRIGGER_PX * 0.5 };
}
