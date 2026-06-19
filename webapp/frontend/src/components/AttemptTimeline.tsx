import type { Attempt } from "../api";

export default function AttemptTimeline({
  attempts,
}: {
  attempts: Attempt[];
}) {
  if (attempts.length === 0) {
    return <p className="text-gray-500 text-sm">No attempts yet.</p>;
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {[...attempts].reverse().map((a, i) => (
        <div
          key={i}
          className={`border rounded p-3 text-xs font-mono ${
            a.success
              ? "border-green-700 bg-green-950/30"
              : "border-border bg-surface-2"
          }`}
        >
          <div className="flex justify-between text-gray-400 mb-1">
            <span>
              Agent {a.agent_index} · Turn {a.turn}
            </span>
            <span>{a.llm_model}</span>
          </div>
          <pre className="text-gray-300 whitespace-pre-wrap max-h-20 overflow-y-auto">
            {a.compiler_output || "(no output)"}
          </pre>
        </div>
      ))}
    </div>
  );
}
