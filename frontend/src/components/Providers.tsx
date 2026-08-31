"use client";

import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/contexts/AuthContext";
import { AppShell } from "@/components/layout/app-shell";
import { usePathname } from "next/navigation";

function InnerLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  if (isLogin) {
    return <>{children}</>;
  }

  return <AppShell>{children}</AppShell>;
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <AuthProvider>
        <InnerLayout>{children}</InnerLayout>
      </AuthProvider>
    </ThemeProvider>
  );
}
