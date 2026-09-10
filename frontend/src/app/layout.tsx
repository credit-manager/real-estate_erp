import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "2TO Control Center",
  description: "Master Admin Portal — 2TO",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
