import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["var(--font-inter)",  "system-ui", "sans-serif"],
        display: ["var(--font-syne)",   "system-ui", "sans-serif"],
        mono:    ["var(--font-mono)",   "ui-monospace", "monospace"],
      },
      colors: {
        // Base
        void:  "#070A12",
        navy: {
          900: "#070A12",
          800: "#0D1120",
          700: "#131B2E",
          600: "#1C2640",
        },
        // Accent — electric mint
        mint: {
          DEFAULT: "#10E8A0",
          dim:     "rgba(16,232,160,0.10)",
          border:  "rgba(16,232,160,0.25)",
          glow:    "rgba(16,232,160,0.20)",
        },
        // Accent 2 — electric purple
        purple: {
          DEFAULT: "#7C5CFC",
          light:   "#A78BFA",
          dim:     "rgba(124,92,252,0.12)",
          border:  "rgba(124,92,252,0.30)",
          glow:    "rgba(124,92,252,0.20)",
        },
        // Semantic
        amber:   { DEFAULT: "#FFB020", dim: "rgba(255,176,32,0.12)"   },
        red:     { DEFAULT: "#FF4040", dim: "rgba(255,64,64,0.12)"    },
        sky:     { DEFAULT: "#38BDF8", dim: "rgba(56,189,248,0.10)"   },
        // Text
        ink: {
          1: "#EEF2FF",
          2: "#9BA3BE",
          3: "#4D5B7A",
        },
      },
      borderColor: {
        subtle: "rgba(255,255,255,0.07)",
        mid:    "rgba(255,255,255,0.12)",
        strong: "rgba(255,255,255,0.22)",
      },
      boxShadow: {
        "mint-glow":   "0 0 40px rgba(16,232,160,0.15), 0 0 80px rgba(16,232,160,0.06)",
        "mint-sm":     "0 0 16px rgba(16,232,160,0.20)",
        "purple-glow": "0 0 40px rgba(124,92,252,0.20)",
        card:          "0 1px 3px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)",
        "card-hover":  "0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.10)",
      },
      keyframes: {
        "orb-1": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "33%":     { transform: "translate(40px,-30px) scale(1.08)" },
          "66%":     { transform: "translate(-25px,15px) scale(0.96)" },
        },
        "orb-2": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "40%":     { transform: "translate(-50px,25px) scale(1.05)" },
          "70%":     { transform: "translate(30px,-40px) scale(0.97)" },
        },
        "orb-3": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "50%":     { transform: "translate(20px,35px) scale(1.10)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(20px)" },
          to:   { opacity: "1", transform: "translateY(0)"    },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-right": {
          from: { opacity: "0", transform: "translateX(-10px)" },
          to:   { opacity: "1", transform: "translateX(0)"      },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-400% center" },
          "100%": { backgroundPosition: "400% center"  },
        },
        "pulse-dot": {
          "0%,100%": { opacity: "0.5", transform: "scale(1)"   },
          "50%":     { opacity: "1",   transform: "scale(1.3)" },
        },
        "border-beam": {
          "0%":   { backgroundPosition: "0% 0%" },
          "100%": { backgroundPosition: "200% 0%" },
        },
        scan: {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
      },
      animation: {
        "orb-1":     "orb-1 18s ease-in-out infinite",
        "orb-2":     "orb-2 22s ease-in-out infinite",
        "orb-3":     "orb-3 26s ease-in-out infinite",
        "fade-up":   "fade-up 0.6s cubic-bezier(0.16,1,0.3,1) forwards",
        "fade-in":   "fade-in 0.4s ease-out forwards",
        "slide-right": "slide-right 0.3s ease-out forwards",
        shimmer:     "shimmer 3s linear infinite",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        scan:        "scan 6s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
