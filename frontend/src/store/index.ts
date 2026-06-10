import { create } from "zustand";
import { persist } from "zustand/middleware";

// ── Upload Config Store ─────────────────────────────────────────────────

interface UploadConfig {
  skipCleaning: boolean;
  chunkSizeMB: number;
  setSkipCleaning: (skip: boolean) => void;
  setChunkSizeMB: (size: number) => void;
}

export const useUploadConfig = create<UploadConfig>()(
  persist(
    (set) => ({
      skipCleaning: false,
      chunkSizeMB: 1,
      setSkipCleaning: (skip) => set({ skipCleaning: skip }),
      setChunkSizeMB: (size) => set({ chunkSizeMB: size }),
    }),
    { name: "autoinsight-upload-config" }
  )
);

// ── Dashboard Filter Store ──────────────────────────────────────────────

interface FilterState {
  dateRange: [string, string] | null;
  confidenceMin: number;
  searchQuery: string;
  setDateRange: (range: [string, string] | null) => void;
  setConfidenceMin: (min: number) => void;
  setSearchQuery: (query: string) => void;
  reset: () => void;
}

export const useDashboardFilters = create<FilterState>()(
  persist(
    (set) => ({
      dateRange: null,
      confidenceMin: 0,
      searchQuery: "",
      setDateRange: (range) => set({ dateRange: range }),
      setConfidenceMin: (min) => set({ confidenceMin: min }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      reset: () =>
        set({ dateRange: null, confidenceMin: 0, searchQuery: "" }),
    }),
    { name: "autoinsight-dashboard-filters" }
  )
);

// ── NLQ Chat Store ──────────────────────────────────────────────────────

interface NlqState {
  showReasoning: boolean;
  toggleReasoning: () => void;
}

export const useNlqStore = create<NlqState>()((set) => ({
  showReasoning: false,
  toggleReasoning: () => set((s) => ({ showReasoning: !s.showReasoning })),
}));
