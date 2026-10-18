import { create } from "zustand";
import type { LlmProvider } from "../api";
import { fetchLlmProviders } from "../api";

interface LlmState {
  providers: LlmProvider[];
  loaded: boolean;
  loading: boolean;
  error: string | null;
  selectedTier: number;
  setSelectedTier: (tier: number) => void;
  refresh: () => Promise<void>;
}

export const useLlmStore = create<LlmState>((set) => ({
  providers: [],
  loaded: false,
  loading: false,
  error: null,
  selectedTier: 1,
  setSelectedTier: (tier) => set({ selectedTier: tier }),
  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const d = await fetchLlmProviders();
      set({ providers: d.providers, loaded: true, loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "provider probe failed",
      });
    }
  },
}));
