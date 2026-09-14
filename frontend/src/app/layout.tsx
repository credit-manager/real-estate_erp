import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "2TO Control Center",
  description: "Enterprise Control Center — 2TO",
  icons: {
    icon: "/2to-logo.svg",
    shortcut: "/2to-logo.svg",
    apple: "/2to-logo.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
