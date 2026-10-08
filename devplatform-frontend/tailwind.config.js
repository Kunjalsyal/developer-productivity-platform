/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", panel: "var(--panel)", ink: "var(--ink)", mute: "var(--mute)",
        line: "var(--line)", accent: "var(--accent)", "accent-ink": "var(--accent-ink)",
        cite: "var(--cite)", "cite-ink": "var(--cite-ink)", code: "var(--code)",
        ok: "var(--ok)", warn: "var(--warn)",
      },
      fontFamily: {
        sans: ['"Instrument Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
