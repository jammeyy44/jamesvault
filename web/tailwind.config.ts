import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "#0B0E17",
        card: "#131927",
        ink: "#FFFFFF",
        primary: "#38BDF8",
        electric: "#00D2FF",
        violet: "#7C3AED",
        soft: "#141A29",
        line: "#1E2638",
        muted: "#94A3B8",
        success: "#36D98A",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
        "cyan-gradient": "linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)",
        "brand-text": "linear-gradient(110deg, #38BDF8 0%, #C084FC 100%)",
      },
      boxShadow: {
        card: "0 10px 30px -10px rgba(0, 0, 0, 0.6)",
        lift: "0 18px 40px -12px rgba(124, 58, 237, 0.45)",
        glow: "0 0 25px -5px rgba(56, 189, 248, 0.4)",
      },
      borderRadius: { xl2: "1.25rem", xl3: "1.75rem" },
      keyframes: {
        wiggle: { "0%, 100%": { transform: "rotate(-9deg)" }, "50%": { transform: "rotate(9deg)" } },
        blink: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.35" } },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
