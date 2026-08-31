import type { Metadata } from "next";
import Script from "next/script";
import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./globals.css";

import { ThemeProvider } from "@/components/theme-provider";
import { AppQueryProvider } from "@/lib/query-provider";

export const metadata: Metadata = {
  title: "ChessGround",
  description: "A focused workspace for chess repertoire analysis and training.",
};

const themeInitScript = `
(() => {
  const storageKey = "cg-web-theme";
  const stored = window.localStorage.getItem(storageKey);
  const theme = stored === "light" || stored === "dark"
    ? stored
    : "dark";
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script id="theme-init" strategy="beforeInteractive">{themeInitScript}</Script>
        <ThemeProvider>
          <AppQueryProvider>{children}</AppQueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
