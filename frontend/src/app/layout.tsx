import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ERP Control Center",
  description: "Master Admin Portal — DynamicPro ERP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
