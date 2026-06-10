import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18202f",
        muted: "#647084",
        line: "#d8dee8",
        panel: "#f7f8fb",
        brand: "#1f7a6d",
        accent: "#c9572b",
        steel: "#3b5f7a"
      },
      boxShadow: {
        soft: "0 12px 30px rgba(24, 32, 47, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

