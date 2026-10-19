import { useCallback, useEffect, useState } from "react";

const LEVELS = [0.5, 0.6, 0.7, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0];
const STORAGE_KEY = "tauri-zoom";

/**
 * Fleet zoom kit: Ctrl+wheel steps through LEVELS, Ctrl+0 resets to 1.0,
 * Ctrl +/- step. Persists to localStorage and applies CSS zoom so it works
 * identically in the Tauri WebView and the dev browser. Ctrl+K focuses the
 * first page search box when one exists.
 */
export function useZoom(): {
  zoom: number;
  resetZoom: () => void;
  stepZoom: (dir: 1 | -1) => void;
} {
  const [zoom, setZoom] = useState(1.0);

  useEffect(() => {
    try {
      const saved = Number(localStorage.getItem(STORAGE_KEY));
      if (LEVELS.includes(saved)) setZoom(saved);
    } catch {
      // storage unavailable -- stay at 1.0
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--fleet-zoom", String(zoom));
    const root = document.getElementById("root");
    if (root) root.style.zoom = String(zoom);
    try {
      localStorage.setItem(STORAGE_KEY, String(zoom));
    } catch {
      // ignore persistence failures
    }
  }, [zoom]);

  const nearest = useCallback(
    (dir: 1 | -1) => {
      let best = 0;
      for (let i = 1; i < LEVELS.length; i++) {
        const lv = LEVELS[i];
        const cur = LEVELS[best];
        if (
          lv !== undefined &&
          cur !== undefined &&
          Math.abs(lv - zoom) < Math.abs(cur - zoom)
        ) {
          best = i;
        }
      }
      const next = Math.min(LEVELS.length - 1, Math.max(0, best + dir));
      const level = LEVELS[next];
      if (level !== undefined) setZoom(level);
    },
    [zoom],
  );

  const resetZoom = useCallback(() => setZoom(1.0), []);
  const stepZoom = useCallback((dir: 1 | -1) => nearest(dir), [nearest]);

  useEffect(() => {
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      nearest(e.deltaY > 0 ? -1 : 1);
    };
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey) return;
      if (e.key === "0") {
        e.preventDefault();
        setZoom(1.0);
      } else if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        nearest(1);
      } else if (e.key === "-") {
        e.preventDefault();
        nearest(-1);
      } else if (e.key.toLowerCase() === "k") {
        const box = document.querySelector<HTMLElement>(
          "[data-testid^='search-']",
        );
        if (box) {
          e.preventDefault();
          box.focus();
        }
      }
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
    };
  }, [nearest]);

  return { zoom, resetZoom, stepZoom };
}
