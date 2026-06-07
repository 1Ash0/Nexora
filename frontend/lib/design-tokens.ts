/**
 * Nexora Design Strategy
 * All visual values are derived from this token manifest.
 * Zero hardcoded hex in component files.
 */

export const NEXORA_TOKENS = {
  colors: {
    black: "#000000",
    green: "#00FF00",
    indigo: "#818CF8",
    amber: "#FCD34D",
    red: "#F87171",
    blue: "#60A5FA",
    surface: {
      1: "rgba(255, 255, 255, 0.02)",
      2: "rgba(255, 255, 255, 0.04)",
      3: "rgba(255, 255, 255, 0.06)",
    },
    border: {
      subtle: "rgba(255, 255, 255, 0.08)",
      mid: "rgba(255, 255, 255, 0.15)",
      accent: "rgba(255, 255, 255, 0.30)",
    },
    text: {
      primary: "#F8FAFC",
      secondary: "#94A3B8",
      muted: "#475569",
    },
  },
  typography: {
    mono: 'ui-monospace, "Cascadia Code", "Fira Code", monospace',
  },
  motion: {
    duration: {
      scramble: 800, // ms
      slideIn: 250,
      scaleReveal: 200,
      statusPulse: 2000,
    },
    frames: {
      scramble: 40,
    },
  },
  shadows: {
    modal: "0 25px 60px rgba(0,0,0,0.8)",
  },
} as const;

export type NexoraTokens = typeof NEXORA_TOKENS;
