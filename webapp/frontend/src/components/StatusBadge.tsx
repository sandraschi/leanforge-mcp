const colors: Record<string, string> = {
  queued: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  running: "bg-blue-900/50 text-blue-300 border-blue-700",
  complete: "bg-green-900/50 text-green-300 border-green-700",
  failed: "bg-red-900/50 text-red-300 border-red-700",
  cancelled: "bg-gray-700/50 text-gray-300 border-gray-600",
  interrupted: "bg-orange-900/50 text-orange-300 border-orange-700",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = colors[status] ?? "bg-gray-800 text-gray-400 border-gray-600";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${cls}`}
    >
      {status}
    </span>
  );
}
