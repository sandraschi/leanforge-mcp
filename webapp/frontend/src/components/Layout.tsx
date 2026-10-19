import { NavLink } from "react-router-dom";
import { useZoom } from "../hooks/useZoom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Inbox" },
  { to: "/problems", label: "Problems" },
  { to: "/submit", label: "New Theorem" },
  { to: "/chat", label: "Chat" },
  { to: "/tools", label: "Tools" },
  { to: "/skills", label: "Skills" },
  { to: "/logs", label: "Logs" },
  { to: "/settings", label: "Settings" },
  { to: "/apps", label: "Apps" },
  { to: "/help", label: "Help" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { zoom, resetZoom } = useZoom();
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="border-b border-border bg-surface-2 px-6 py-3 flex items-center gap-6">
        <span className="text-lg font-semibold text-indigo-400 tracking-tight">
          leanforge-mcp
        </span>
        <div className="flex gap-4 text-sm">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                isActive
                  ? "text-indigo-300 font-medium"
                  : "text-zinc-400 hover:text-zinc-200"
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {zoom !== 1.0 && (
            <button
              type="button"
              data-testid="zoom-indicator"
              onClick={resetZoom}
              title="Reset zoom (Ctrl+0)"
              className="text-xs text-zinc-400 border border-zinc-700 rounded px-2 py-0.5 hover:border-indigo-500"
            >
              {Math.round(zoom * 100)}%
            </button>
          )}
        </div>
      </nav>
      <main className="flex-1 p-6 max-w-6xl w-full mx-auto">{children}</main>
    </div>
  );
}
