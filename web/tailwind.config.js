/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        panel: {
          DEFAULT: "rgb(var(--color-panel) / <alpha-value>)",
          elevated: "rgb(var(--color-panel-elevated) / <alpha-value>)",
          muted: "rgb(var(--color-panel-muted) / <alpha-value>)",
        },
        border: "rgb(var(--color-border) / <alpha-value>)",
        text: {
          DEFAULT: "rgb(var(--color-text) / <alpha-value>)",
          muted: "rgb(var(--color-text-muted) / <alpha-value>)",
          subtle: "rgb(var(--color-text-subtle) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          strong: "rgb(var(--color-accent-strong) / <alpha-value>)",
          soft: "rgb(var(--color-accent-soft) / <alpha-value>)",
        },
        success: {
          DEFAULT: "rgb(var(--color-success) / <alpha-value>)",
          soft: "rgb(var(--color-success-soft) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "rgb(var(--color-warning) / <alpha-value>)",
          soft: "rgb(var(--color-warning-soft) / <alpha-value>)",
        },
        danger: {
          DEFAULT: "rgb(var(--color-danger) / <alpha-value>)",
          soft: "rgb(var(--color-danger-soft) / <alpha-value>)",
        },
        board: { light: "#f0d9b5", dark: "#b58863" },
      },
      spacing: { xs: "0.25rem", sm: "0.5rem", md: "0.75rem", lg: "1rem", xl: "1.5rem", "2xl": "2rem", "3xl": "3rem" },
      borderRadius: { sm: "0.5rem", md: "0.75rem", lg: "1rem", xl: "1.25rem", pill: "9999px" },
      boxShadow: { soft: "0 12px 30px -18px rgba(15, 23, 42, 0.65)", panel: "0 18px 40px -24px rgba(8, 15, 30, 0.72)", focus: "0 0 0 3px rgba(56, 189, 248, 0.35)" },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "monospace"] },
      fontSize: { hero: ["1.875rem", { lineHeight: "2.25rem", fontWeight: "700" }], section: ["1.25rem", { lineHeight: "1.75rem", fontWeight: "600" }], label: ["0.875rem", { lineHeight: "1.25rem", fontWeight: "500" }] },
      gridTemplateColumns: { shell: "16rem minmax(0, 1fr)", board: "minmax(0, 4fr) minmax(18rem, 1fr)" },
    },
  },
  plugins: [],
};
