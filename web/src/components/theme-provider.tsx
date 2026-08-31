"use client";

import { createContext, ReactNode, useContext, useMemo, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "cg-web-theme";

type ThemeContextValue = {
  theme: Theme;
  resolvedTheme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

export function resolveStoredTheme(value: string | null): Theme {
  return value === "light" || value === "dark" ? value : "dark";
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
}

function getPreferredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return resolveStoredTheme(window.localStorage.getItem(STORAGE_KEY));
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getPreferredTheme);

  const value = useMemo<ThemeContextValue>(() => ({
    theme,
    resolvedTheme: theme,
    setTheme: (nextTheme) => {
      setThemeState(nextTheme);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, nextTheme);
      }
      applyTheme(nextTheme);
    },
    toggleTheme: () => {
      const nextTheme = theme === "dark" ? "light" : "dark";
      setThemeState(nextTheme);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, nextTheme);
      }
      applyTheme(nextTheme);
    },
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
