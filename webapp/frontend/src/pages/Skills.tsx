import { motion } from "framer-motion";
import { BookOpen } from "lucide-react";
import { useEffect, useState } from "react";

export default function Skills() {
  const [skills, setSkills] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetch("/api/skills")
      .then((r) => {
        if (!r.ok) throw new Error(`GET /api/skills returned ${r.status}`);
        return r.json();
      })
      .then((d) => setSkills(d.skills ?? []))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "failed to load skills"),
      )
      .finally(() => setLoading(false));
  }, []);

  const openSkill = (name: string) => {
    setSelected(name);
    setContent("Loading...");
    fetch(`/api/skills/${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`skill '${name}' not found (${r.status})`);
        return r.text();
      })
      .then(setContent)
      .catch((e) => setContent(e instanceof Error ? e.message : "load failed"));
  };

  const filtered = skills.filter((s) =>
    s.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="skills-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <BookOpen size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Skills</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-4">
        Expert contexts the Chat page loads as system preprompts, served live
        from skill files.
      </p>

      <input
        data-testid="search-skills"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search skills..."
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 mb-4"
      />

      {loading && <p className="text-sm text-zinc-400">Loading skills...</p>}
      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded p-4 text-sm text-red-300">
          {error}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="ml-3 underline"
          >
            Retry
          </button>
        </div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <p className="text-sm text-zinc-400">No skills installed yet.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="space-y-2" data-testid="skills-count">
          {filtered.map((s) => (
            <button
              type="button"
              key={s}
              data-testid={`skill-card-${s}`}
              onClick={() => openSkill(s)}
              className={`block w-full text-left border rounded p-3 text-sm transition-colors ${
                selected === s
                  ? "border-indigo-500 bg-indigo-950/40 text-indigo-200"
                  : "border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-indigo-700"
              }`}
            >
              <code className="font-mono">{s}</code>
              <span className="block text-xs text-zinc-500 mt-1">
                {filtered.length} total
              </span>
            </button>
          ))}
        </div>
        <div className="md:col-span-2 border border-zinc-800 rounded bg-zinc-900 p-4 min-h-[300px]">
          {selected ? (
            <pre
              data-testid="skill-content"
              className="text-xs text-zinc-300 whitespace-pre-wrap font-mono"
            >
              {content}
            </pre>
          ) : (
            <p className="text-sm text-zinc-500">
              Select a skill to preview its content.
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}
