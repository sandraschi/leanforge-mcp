import { useCallback, useEffect, useState } from "react";

/**
 * Backend-status listener with HTTP fallback (Tauri pattern).
 *
 * Inside the Tauri WebView it subscribes to the `backend-status` event the
 * Rust sidecar emits; everywhere else (dev browser) it degrades to the
 * caller's HTTP poll. Returns whether the Tauri event path is live so the UI
 * can say which transport reported ready.
 */
export function useBackendStatus(onEvent: () => void): {
  tauriLive: boolean;
} {
  const [tauriLive, setTauriLive] = useState(false);
  const handler = useCallback(() => {
    onEvent();
  }, [onEvent]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      try {
        // Dynamic import: dev-browser builds never bundle Tauri IPC.
        const { listen } = await import("@tauri-apps/api/event");
        if (cancelled) return;
        unlisten = await listen<string>("backend-status", (event) => {
          if (event.payload === "ready") {
            setTauriLive(true);
            handler();
          }
        });
      } catch {
        // Not in Tauri (dev browser) -- HTTP polling covers status.
      }
    })();
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [handler]);

  return { tauriLive };
}
