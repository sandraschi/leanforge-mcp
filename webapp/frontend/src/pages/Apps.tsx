import { motion } from "framer-motion";
import { LayoutGrid } from "lucide-react";
import { useEffect, useState } from "react";

interface FleetApp {
  name: string;
  label: string;
  backend_port: number;
  frontend_port: number;
  url: string;
  online: boolean;
  http_status: number | null;
  version: string | null;
}

function AppCard({ app }: { app: FleetApp }) {
  return (
    <div
      data-testid={`fleet-app-${app.name}`}
      className="border border-zinc-800 rounded p-4 bg-zinc-900"
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-medium text-zinc-100">{app.label}</span>
        <span
          className={`ml-auto text-xs ${app.online ? "text-green-400" : "text-zinc-500"}`}
        >
          {app.online ? "online" : "offline"}
        </span>
      </div>
      <code className="text-xs font-mono text-zinc-500">
        {app.name} · :{app.frontend_port}
        {app.version ? ` · v${app.version}` : ""}
      </code>
      {app.online && (
        <a
          href={app.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block mt-2 text-sm text-indigo-400 hover:underline"
        >
          Open →
        </a>
      )}
    </div>
  );
}

export default function Apps() {
  const [registered, setRegistered] = useState<FleetApp[]>([]);
  const [experimental, setExperimental] = useState<FleetApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    fetch("/api/fleet/apps")
      .then((r) => {
        if (!r.ok) throw new Error(`GET /api/fleet/apps returned ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setRegistered(d.registered ?? []);
        setExperimental(d.experimental ?? []);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "discovery failed"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="apps-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <LayoutGrid size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Apps Hub</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-4">
        Fleet apps from the port registry, live-probed on every load. Status is
        observed, never assumed.
      </p>
      <button
        type="button"
        data-testid="apps-refresh"
        onClick={load}
        className="px-3 py-2 mb-4 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-indigo-500"
      >
        Re-probe
      </button>

      {loading && (
        <p className="text-sm text-zinc-400">Probing fleet apps...</p>
      )}
      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded p-4 text-sm text-red-300 mb-4">
          {error}
          <button type="button" onClick={load} className="ml-3 underline">
            Retry
          </button>
        </div>
      )}

      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide mb-3">
        Registered
      </h2>
      <div
        className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6"
        data-testid="apps-count"
      >
        {registered.map((a) => (
          <AppCard key={a.name} app={a} />
        ))}
      </div>

      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide mb-3">
        Experimental
      </h2>
      {experimental.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No unlisted apps detected. Set FLEET_EXTRA_PORTS=name:port to probe
          more.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {experimental.map((a) => (
            <AppCard key={a.name} app={a} />
          ))}
        </div>
      )}
    </motion.div>
  );
}
