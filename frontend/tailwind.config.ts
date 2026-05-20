import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Mirrors the existing Streamlit palette in ui/styles.py
        rs: {
          primary: "#2563EB",
          "primary-dk": "#1D4ED8",
          yellow: "#FACC15",
          "yellow-dk": "#CA8A04",
          "yellow-lt": "#FEF9C3",
          ink: "#0F172A",
          "ink-2": "#334155",
          "ink-3": "#64748B",
          border: "#E2E8F0",
          "border-strong": "#CBD5E1",
          surface: "#FFFFFF",
          "surface-2": "#F8FAFC",
          bg: "#F1F5F9",
        },
      },
      boxShadow: {
        card: "0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04)",
        "card-hover": "0 4px 12px rgba(15,23,42,0.10)",
      },
      borderRadius: {
        card: "12px",
      },
    },
  },
  plugins: [],
};

export default config;
