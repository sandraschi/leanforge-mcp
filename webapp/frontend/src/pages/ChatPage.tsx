import { useState, useEffect, useRef } from "react";
import { MessageCircle, Send, Eraser, Download } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string; ts?: string };

const STORAGE_KEY = "leanforge-chat-history";
const PERSONALITY_KEY = "leanforge-chat-personality";

const PERSONALITIES: Record<string, string> = {
  "lean-expert":
    "You are a Lean 4 expert. Answer concisely and accurately. Reference specific tactics, lemmas, and version numbers when relevant.",
  "theorem-coach":
    "You are a patient theorem-proving coach. Guide the user step by step through Lean proofs. Ask clarifying questions before suggesting tactics.",
  "mathlib-guide":
    "You are a Mathlib specialist. Help users find the right lemmas and navigate the Mathlib ecosystem. Suggest search queries for get_mathlib_search.",
  custom: "",
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [personality, setPersonality] = useState("lean-expert");
  const [customPrompt, setCustomPrompt] = useState("");
  const [skillContent, setSkillContent] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setMessages(JSON.parse(saved));
      const p = localStorage.getItem(PERSONALITY_KEY);
      if (p) setPersonality(p);
    } catch {}
    fetch("/api/skills").then((r) => r.json()).then((d) => {
      if (d.skills?.includes("lean_expert")) {
        fetch("/api/skills/lean_expert").then((r) => r.text()).then(setSkillContent);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-100)));
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const buildSystemPrompt = () => {
    let base = skillContent || "You are a Lean 4 assistant.";
    if (personality === "custom" && customPrompt) return customPrompt;
    const role = PERSONALITIES[personality];
    if (role) base += "\n\n---\n\n## Role\n" + role;
    return base;
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Msg = { role: "user", content: input.trim(), ts: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const r = await fetch("http://127.0.0.1:11434/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "deepseek-prover-v2:7b",
          messages: [
            { role: "system", content: buildSystemPrompt() },
            ...messages.map((m) => ({ role: m.role, content: m.content })),
            { role: "user", content: userMsg.content },
          ],
          stream: false,
        }),
      });
      const data = await r.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message?.content || "(no response)", ts: new Date().toISOString() },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: backend unreachable. Is Ollama running on port 11434?", ts: new Date().toISOString() },
      ]);
    }
    setLoading(false);
  };

  const clearChat = () => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const exportChat = () => {
    const text = messages.map((m) => `[${m.ts || "?"}] ${m.role}: ${m.content}`).join("\n\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leanforge-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="chat-page" className="flex flex-col h-full bg-zinc-950">
      {/* Controls bar */}
      <div data-testid="chat-controls" className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800 bg-zinc-900">
        <MessageCircle size={18} className="text-amber-500" />
        <span className="text-sm text-zinc-400">skill:lean-expert</span>
        <select
          data-testid="personality-select"
          value={personality}
          onChange={(e) => { setPersonality(e.target.value); localStorage.setItem(PERSONALITY_KEY, e.target.value); }}
          className="bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1 text-xs"
        >
          <option value="lean-expert">Lean Expert</option>
          <option value="theorem-coach">Theorem Coach</option>
          <option value="mathlib-guide">Mathlib Guide</option>
          <option value="custom">Custom</option>
        </select>
        <div className="flex-1" />
        <button data-testid="chat-export" onClick={exportChat} disabled={messages.length === 0}
          className="p-1.5 text-zinc-500 hover:text-zinc-100 disabled:opacity-30">
          <Download size={16} />
        </button>
        <button data-testid="chat-clear" onClick={clearChat} disabled={messages.length === 0}
          className="p-1.5 text-zinc-500 hover:text-zinc-100 disabled:opacity-30">
          <Eraser size={16} />
        </button>
      </div>

      {/* Custom prompt editor */}
      {personality === "custom" && (
        <textarea value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
          placeholder="Enter custom system prompt..."
          className="mx-4 mt-2 p-2 bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-300 h-20 resize-none"
        />
      )}

      {/* Messages */}
      <div data-testid="chat-messages" className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-zinc-600 mt-12">
            <MessageCircle size={32} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">Ask me about Lean 4 tactics, syntax, or theorems.</p>
            <div data-testid="example-prompts" className="flex flex-wrap justify-center gap-2 mt-4">
              {["What is the current Lean version?", "How do I use omega?", "Find lemma: map composition", "Help with calc block"].map((p) => (
                <button key={p} onClick={() => setInput(p)}
                  className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded-full text-zinc-400 hover:bg-zinc-700">
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-2 text-sm ${
              m.role === "user" ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-200"
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800 rounded-xl px-4 py-2 text-sm text-zinc-400 animate-pulse">Thinking...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-zinc-800 p-3">
        <div className="flex gap-2">
          <input
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
            placeholder="Ask about Lean 4..."
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
          />
          <button data-testid="chat-send" onClick={send} disabled={loading || !input.trim()}
            className="bg-amber-600 hover:bg-amber-500 disabled:bg-zinc-700 rounded-xl px-4 py-2 text-white">
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
