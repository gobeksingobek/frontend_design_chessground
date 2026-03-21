/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        muted: {
          DEFAULT: "rgb(var(--muted) / <alpha-value>)",
          foreground: "rgb(var(--muted-foreground) / <alpha-value>)",
        },
        border: "rgb(var(--border) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        elevated: "rgb(var(--elevated) / <alpha-value>)",
        overlay: "rgb(var(--overlay) / <alpha-value>)",
        primary: {
          DEFAULT: "rgb(var(--primary) / <alpha-value>)",
          foreground: "rgb(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "rgb(var(--secondary) / <alpha-value>)",
          foreground: "rgb(var(--secondary-foreground) / <alpha-value>)",
        },
        success: {
          DEFAULT: "rgb(var(--success) / <alpha-value>)",
          foreground: "rgb(var(--success-foreground) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "rgb(var(--warning) / <alpha-value>)",
          foreground: "rgb(var(--warning-foreground) / <alpha-value>)",
        },
        danger: {
          DEFAULT: "rgb(var(--danger) / <alpha-value>)",
          foreground: "rgb(var(--danger-foreground) / <alpha-value>)",
        },
        focus: "rgb(var(--focus) / <alpha-value>)",
        selection: {
          DEFAULT: "rgb(var(--selection) / <alpha-value>)",
          foreground: "rgb(var(--selection-foreground) / <alpha-value>)",
        },
        hover: {
          DEFAULT: "rgb(var(--hover) / <alpha-value>)",
          foreground: "rgb(var(--hover-foreground) / <alpha-value>)",
        },
        eval: {
          light: "rgb(var(--eval-light) / <alpha-value>)",
          dark: "rgb(var(--eval-dark) / <alpha-value>)",
        },
        board: {
          light: "rgb(var(--board-light) / <alpha-value>)",
          dark: "rgb(var(--board-dark) / <alpha-value>)",
          'light-piece': "rgb(var(--board-light-piece) / <alpha-value>)",
          'dark-piece': "rgb(var(--board-dark-piece) / <alpha-value>)",
        },
        bg: "rgb(var(--background) / <alpha-value>)",
        text: {
          DEFAULT: "rgb(var(--foreground) / <alpha-value>)",
          muted: "rgb(var(--muted-foreground) / <alpha-value>)",
          subtle: "rgb(var(--muted-foreground) / <alpha-value>)",
        },
        panel: {
          DEFAULT: "rgb(var(--card) / <alpha-value>)",
          elevated: "rgb(var(--elevated) / <alpha-value>)",
          muted: "rgb(var(--muted) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--primary) / <alpha-value>)",
          strong: "rgb(var(--secondary) / <alpha-value>)",
          soft: "rgb(var(--primary) / <alpha-value>)",
        },
      },
      spacing: { xs: "0.25rem", sm: "0.5rem", md: "0.75rem", lg: "1rem", xl: "1.5rem", "2xl": "2rem", "3xl": "3rem", "control-gap": "0.75rem", "card-pad": "1.5rem", "grid-gap": "1.5rem", "section-gap": "2rem", "page-gap": "3rem", "page-pad": "1rem", "page-pad-lg": "2rem" },
      borderRadius: { sm: "0.5rem", md: "0.75rem", lg: "1rem", xl: "1.25rem", pill: "9999px" },
      boxShadow: { soft: "0 12px 30px -18px rgb(15 23 42 / 0.18)", panel: "0 18px 40px -24px rgb(15 23 42 / 0.22)", focus: "0 0 0 3px rgb(var(--focus) / 0.35)" },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "monospace"] },
      fontSize: {
        display: ["2.25rem", { lineHeight: "2.75rem", fontWeight: "700" }],
        "page-title": ["1.75rem", { lineHeight: "2.25rem", fontWeight: "650" }],
        "section-title": ["1.375rem", { lineHeight: "1.9rem", fontWeight: "600" }],
        "card-title": ["1.125rem", { lineHeight: "1.6rem", fontWeight: "600" }],
        body: ["0.95rem", { lineHeight: "1.65rem", fontWeight: "400" }],
        label: ["0.875rem", { lineHeight: "1.35rem", fontWeight: "500" }],
        caption: ["0.75rem", { lineHeight: "1.1rem", fontWeight: "500" }],
        mono: ["0.8125rem", { lineHeight: "1.35rem", fontWeight: "500" }],
        hero: ["1.875rem", { lineHeight: "2.25rem", fontWeight: "700" }],
        section: ["1.25rem", { lineHeight: "1.75rem", fontWeight: "600" }],
      },
      gridTemplateColumns: { shell: "16rem minmax(0, 1fr)", board: "minmax(0, 4fr) minmax(18rem, 1fr)" },
    },
  },
  plugins: [],
};
