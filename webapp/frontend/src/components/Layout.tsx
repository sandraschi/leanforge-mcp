import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/problems", label: "Problems" },
  { to: "/submit", label: "New Theorem" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
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
                  : "text-gray-400 hover:text-gray-200"
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="flex-1 p-6 max-w-6xl w-full mx-auto">{children}</main>
    </div>
  );
}
