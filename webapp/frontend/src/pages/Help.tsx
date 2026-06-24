import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { fetchDoc } from "../api";

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

type TabId = "overview" | "install" | "configuration" | "tools" | "lean" | "development";

// Map tab → actual doc name (install tab uses TROUBLESHOOTING as fallback;
// we want INSTALL but it's at the root, not in docs/ — serve it via its own entry)
const TAB_DOCS: Record<TabId, string | null> = {
  overview:      null,
  install:       "INSTALL",
  configuration: "CONFIGURATION",
  tools:         "TOOLS",
  lean:          "LEAN",
  development:   "DEVELOPMENT",
};

// ---------------------------------------------------------------------------
// Markdown renderer components — match dark theme
// ---------------------------------------------------------------------------

const mdComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold text-gray-100 mt-6 mb-3">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-gray-100 mt-6 mb-2 border-b border-zinc-800 pb-1">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-indigo-300 mt-4 mb-1.5">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="text-sm text-gray-300 leading-relaxed mb-3">{children}</p>
  ),
  a: ({ href, children }) => (
    <a href={href ?? "#"} target="_blank" rel="noopener noreferrer"
      className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <pre className="bg-zinc-900 border border-zinc-700 rounded p-3 text-xs text-green-300 font-mono overflow-x-auto mb-4 whitespace-pre">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="bg-zinc-800 text-indigo-300 px-1 py-0.5 rounded text-xs font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  table: ({ children }) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-zinc-700">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="text-left py-2 pr-4 text-gray-400 font-medium">{children}</th>
  ),
  td: ({ children }) => (
    <td className="py-2 pr-4 text-gray-300 align-top border-b border-zinc-800">{children}</td>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside text-sm text-gray-300 mb-3 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside text-sm text-gray-300 mb-3 space-y-1">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-amber-500 bg-amber-950/30 pl-3 py-2 rounded-r text-xs text-amber-200 mb-4">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-zinc-800 my-4" />,
  strong: ({ children }) => <strong className="text-gray-200 font-semibold">{children}</strong>,
};

// ---------------------------------------------------------------------------
// Markdown doc pane
// ---------------------------------------------------------------------------

function DocPane({ docName }: { docName: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setContent(null);
    setError(null);
    fetchDoc(docName)
      .then(setContent)
      .catch((e) => setError(String(e)));
  }, [docName]);

  if (error) {
    return (
      <div className="border border-red-800 bg-red-950/20 rounded p-4 text-sm text-red-300">
        Could not load <code className="text-red-400">{docName}.md</code> from backend.
        <div className="text-xs text-red-400/70 mt-1">{error}</div>
        <div className="text-xs text-gray-500 mt-2">
          Make sure the backend is running: <code>uv run python -m webapp.backend.main</code>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="text-sm text-gray-600 py-8 text-center animate-pulse">
        Loading {docName}.md…
      </div>
    );
  }

  return (
    <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
      {content}
    </ReactMarkdown>
  );
}

// ---------------------------------------------------------------------------
// Overview tab — static (no doc file, just explanatory content)
// ---------------------------------------------------------------------------

function OverviewStatic() {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-100 mt-2 mb-3">leanforge-mcp documentation</h2>
      <p className="text-sm text-gray-300 leading-relaxed mb-4">
        Select a tab above to read the documentation. All content is served live from the
        markdown files in <code className="bg-zinc-800 text-indigo-300 px-1 rounded text-xs">docs/</code> —
        so this page always reflects the current state of the repo.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {[
          { tab: "install" as TabId,       title: "Install",        desc: "Prerequisites, Lean workspace setup, Claude Desktop config" },
          { tab: "configuration" as TabId, title: "Configuration",   desc: "All config.toml options and environment variables" },
          { tab: "tools" as TabId,         title: "Tool Reference",  desc: "All 8 MCP tools with parameters, return shapes, examples" },
          { tab: "lean" as TabId,          title: "Lean 4 Reference", desc: "Tactic guide, compiler errors, Mathlib conventions, bibliography" },
          { tab: "development" as TabId,   title: "Development",     desc: "Setup, project layout, phase B priorities, critical rules" },
        ].map(({ title, desc }) => (
          <div key={title} className="border border-border bg-surface-2 rounded p-3">
            <div className="text-sm font-medium text-indigo-300 mb-1">{title}</div>
            <div className="text-xs text-gray-500">{desc}</div>
          </div>
        ))}
      </div>

      <div className="border border-zinc-800 rounded p-3 text-xs text-gray-500">
        <div className="font-medium text-gray-400 mb-1">GitHub</div>
        <a href="https://github.com/sandraschi/leanforge-mcp"
          target="_blank" rel="noopener noreferrer"
          className="text-indigo-400 hover:underline">
          github.com/sandraschi/leanforge-mcp
        </a>
        <span className="mx-2 text-zinc-700">·</span>
        <a href="https://arxiv.org/abs/2605.22763"
          target="_blank" rel="noopener noreferrer"
          className="text-indigo-400 hover:underline">
          AlphaProof Nexus paper
        </a>
        <span className="mx-2 text-zinc-700">·</span>
        <a href="https://leansearch.net"
          target="_blank" rel="noopener noreferrer"
          className="text-indigo-400 hover:underline">
          LeanSearch
        </a>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Help page
// ---------------------------------------------------------------------------

export default function Help() {
  const [active, setActive] = useState<TabId>("overview");

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview",      label: "Overview" },
    { id: "install",       label: "Install" },
    { id: "configuration", label: "Configuration" },
    { id: "tools",         label: "Tools" },
    { id: "lean",          label: "Lean 4" },
    { id: "development",   label: "Development" },
  ];

  function renderContent() {
    if (active === "overview") return <OverviewStatic />;
    const doc = TAB_DOCS[active];
    if (!doc) return <p className="text-sm text-gray-500">No content for this tab.</p>;
    return <DocPane docName={doc} />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-semibold">Help</h1>
        <a
          href="https://github.com/sandraschi/leanforge-mcp"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-500 hover:text-indigo-400"
        >
          github.com/sandraschi/leanforge-mcp ↗
        </a>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-zinc-700 mb-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              active === tab.id
                ? "border-indigo-500 text-indigo-300"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="max-w-4xl">
        {renderContent()}
      </div>
    </div>
  );
}
