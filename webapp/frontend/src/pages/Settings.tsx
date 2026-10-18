import { motion } from "framer-motion";
import {
  Cloud,
  Cpu,
  FlaskConical,
  Settings as SettingsIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { fetchLlmDiscover, fetchLlmModels, fetchLlmOnboarding } from "../api";
import { useLlmStore } from "../store/llm";

export default function Settings() {
  const {
    providers,
    loaded,
    loading,
    error,
    selectedTier,
    setSelectedTier,
    refresh,
  } = useLlmStore();
  const [models, setModels] = useState<string[]>([]);
  const [modelsLive, setModelsLive] = useState(false);
  const [facts, setFacts] = useState<string[]>([]);
  const [recommended, setRecommended] = useState("");
  const [discover, setDiscover] = useState<{
    ollama: boolean;
    lm_studio: boolean;
  } | null>(null);

  useEffect(() => {
    refresh();
    fetchLlmModels()
      .then((d) => {
        setModels(d.models);
        setModelsLive(d.live);
      })
      .catch(() => {});
    fetchLlmOnboarding()
      .then((d) => {
        setFacts(d.facts);
        setRecommended(d.recommended_path);
      })
      .catch(() => {});
  }, []);

  const testProviders = async () => {
    try {
      setDiscover(await fetchLlmDiscover());
    } catch {
      setDiscover(null);
    }
    await refresh();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="settings-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <SettingsIcon size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Settings</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-6">
        LLM providers for proof search and chat. API keys live in server
        environment variables only -- never in the browser.
      </p>

      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide mb-3">
        Providers
      </h2>
      {loading && !loaded && (
        <p className="text-sm text-zinc-400">Probing providers...</p>
      )}
      {error && <p className="text-sm text-red-300 mb-3">{error}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {providers.map((p) => {
          const ready = p.free ? p.detected : (p.detected ?? p.configured);
          return (
            <div
              key={p.id}
              data-testid={`llm-provider-card-${p.id}`}
              className={`border rounded p-4 bg-zinc-900 ${
                selectedTier === p.tier
                  ? "border-indigo-500"
                  : "border-zinc-800"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                {p.free ? (
                  <Cpu size={16} className="text-green-400" />
                ) : (
                  <Cloud size={16} className="text-sky-300" />
                )}
                <span className="text-sm font-medium text-zinc-100">
                  {p.label}
                </span>
                <span className="text-xs text-zinc-500">tier {p.tier}</span>
                <span
                  data-testid={`llm-status-${p.id}`}
                  className={`ml-auto text-xs ${ready ? "text-green-400" : "text-amber-400"}`}
                >
                  {ready ? "ready" : p.free ? "not detected" : "key not set"}
                </span>
              </div>
              <code className="text-xs font-mono text-zinc-400">{p.model}</code>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  data-testid={`llm-select-${p.id}`}
                  onClick={() => setSelectedTier(p.tier)}
                  className="px-3 py-1 text-sm border border-zinc-700 rounded text-zinc-300 hover:border-indigo-500"
                >
                  Use for chat
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <button
        type="button"
        data-testid="llm-test-providers"
        onClick={testProviders}
        className="px-4 py-2 border border-zinc-700 rounded text-sm text-zinc-200 hover:border-indigo-500 mb-8"
      >
        <FlaskConical size={14} className="inline mr-1" /> Test providers
      </button>
      {discover && (
        <p className="text-sm text-zinc-400 mb-8" data-testid="llm-test-result">
          Ollama: {discover.ollama ? "reachable" : "unreachable"} · LM Studio:{" "}
          {discover.lm_studio ? "reachable" : "unreachable"}
        </p>
      )}

      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide mb-3">
        Models
      </h2>
      <div
        className="border border-zinc-800 rounded bg-zinc-900 p-4 mb-8"
        data-testid="llm-models"
      >
        <p className="text-xs text-zinc-500 mb-2">
          {modelsLive ? "Live from Ollama" : "Curated fallback"}
        </p>
        {models.map((m) => (
          <code key={m} className="block text-sm font-mono text-zinc-300">
            {m}
          </code>
        ))}
      </div>

      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide mb-3">
        Onboarding
      </h2>
      <div
        className="border border-zinc-800 rounded bg-zinc-900 p-4"
        data-testid="llm-onboarding"
      >
        <ul className="list-disc list-inside text-sm text-zinc-300 space-y-1">
          {facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
        {recommended && (
          <p className="text-sm text-indigo-300 mt-2">
            Recommended next step:{" "}
            <code className="font-mono">{recommended}</code>. Full guide:{" "}
            <code className="font-mono">docs/ONBOARDING.md</code>.
          </p>
        )}
      </div>
    </motion.div>
  );
}
