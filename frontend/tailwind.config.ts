import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        muted: "#667085",
        line: "#d7e4f7",
        panel: "#f6f9ff",
        surface: "#ffffff",
        brand: "#2563eb",
        brandDeep: "#1746a2",
        brandSoft: "#e8f1ff",
        brandMist: "#f3f8ff",
        accent: "#c9572b",
        steel: "#3b5f7a"
      },
      borderRadius: {
        app: "1.5rem",
        control: "0.875rem"
      },
      boxShadow: {
        soft: "0 18px 50px rgba(37, 99, 235, 0.10)",
        card: "0 24px 70px rgba(15, 23, 42, 0.10)",
        button: "0 14px 26px rgba(37, 99, 235, 0.22)"
      }
    }
  },
  plugins: []
};

export default config;
