import type { Metadata } from "next";
import "./globals.css";

import { AppQueryProvider } from "@/lib/query-provider";

export const metadata: Metadata = {
  title: "ChessGround Web",
  description: "Web-first shell for ChessGround",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppQueryProvider>{children}</AppQueryProvider>
      </body>
    </html>
  );
}
