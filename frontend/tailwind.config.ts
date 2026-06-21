import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        panel: "0 18px 45px rgba(33, 43, 54, 0.08)"
      }
    }
  },
  plugins: []
} satisfies Config;
