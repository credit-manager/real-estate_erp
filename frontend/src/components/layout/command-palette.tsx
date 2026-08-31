"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Search, Building2, CreditCard, Shield, Package, FileText, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

const pages = [
  { href: "/", label: "Dashboard", icon: Building2, keywords: ["home", "overview"] },
  { href: "/companies", label: "Companies", icon: Building2, keywords: ["clients", "tenants"] },
  { href: "/plans", label: "Plans", icon: CreditCard, keywords: ["pricing", "subscription"] },
  { href: "/modules", label: "Modules", icon: Package, keywords: ["features", "addons"] },
  { href: "/security", label: "Security", icon: Shield, keywords: ["auth", "2fa", "sessions"] },
  { href: "/audit", label: "Audit Logs", icon: FileText, keywords: ["logs", "history"] },
  { href: "/analytics", label: "Analytics", icon: BarChart3, keywords: ["charts", "metrics"] },
];

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = pages.filter((p) => {
    const q = query.toLowerCase();
    return (
      p.label.toLowerCase().includes(q) ||
      p.keywords.some((k) => k.includes(q))
    );
  });

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  const navigate = (href: string) => {
    router.push(href);
    onOpenChange(false);
    setQuery("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 max-w-md gap-0 overflow-hidden">
        {/* Search input */}
        <div className="flex items-center border-b px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages..."
            className="flex-1 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
            autoFocus
          />
          <kbd className="pointer-events-none hidden sm:inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[300px] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No results found.</p>
          ) : (
            <div className="space-y-0.5">
              {filtered.map((page) => (
                <button
                  key={page.href}
                  onClick={() => navigate(page.href)}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-accent transition-colors"
                >
                  <page.icon className="h-4 w-4 text-muted-foreground" />
                  <span>{page.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
