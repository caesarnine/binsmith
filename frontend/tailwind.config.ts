import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"] ,
  theme: {
    extend: {
      fontFamily: {
        sans: ["Spline Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Fraunces", "serif"]
      },
      colors: {
        ink: {
          900: "#1b1a17",
          800: "#2a2723",
          700: "#3b362e",
          500: "#6b6258",
          200: "#d9d1c6"
        }
      },
      boxShadow: {
        soft: "0 20px 60px -30px rgba(15, 23, 42, 0.35)",
        glow: "0 12px 30px -18px rgba(15, 118, 110, 0.6)"
      }
    }
  },
  plugins: [typography]
};

export default config;
