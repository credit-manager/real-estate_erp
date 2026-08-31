"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Building2, CreditCard, Shield, Package,
  FileText, BarChart3, Settings, LogOut, ChevronLeft, ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";

const mainNav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/plans", label: "Plans", icon: CreditCard },
  { href: "/modules", label: "Modules", icon: Package },
];

const securityNav = [
  { href: "/security", label: "Security", icon: Shield },
  { href: "/audit", label: "Audit Logs", icon: FileText },
];

const insightNav = [
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

function NavItem({ href, label, icon: Icon, collapsed }: { href: string; label: string; icon: any; collapsed: boolean }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));

  const link = (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        collapsed && "justify-center px-2"
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }
  return link;
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, logout } = useAuth();

  return (
    <TooltipProvider delayDuration={0}>
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 68 : 256 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-card"
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-2 px-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary">
            <span className="text-xs font-bold text-primary-foreground">DP</span>
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden"
              >
                <span className="text-sm font-semibold whitespace-nowrap">ERP Control</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <Separator />

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {/* Main */}
          <div className="space-y-1">
            {!collapsed && <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Overview</p>}
            {mainNav.map((item) => (
              <NavItem key={item.href} {...item} collapsed={collapsed} />
            ))}
          </div>

          {/* Security */}
          <div className="space-y-1">
            {!collapsed && <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Security</p>}
            {securityNav.map((item) => (
              <NavItem key={item.href} {...item} collapsed={collapsed} />
            ))}
          </div>

          {/* Insights */}
          <div className="space-y-1">
            {!collapsed && <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Insights</p>}
            {insightNav.map((item) => (
              <NavItem key={item.href} {...item} collapsed={collapsed} />
            ))}
          </div>
        </nav>

        <Separator />

        {/* Bottom */}
        <div className="p-3 space-y-1">
          <NavItem href="/settings" label="Settings" icon={Settings} collapsed={collapsed} />
          <button
            onClick={logout}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive",
              collapsed && "justify-center px-2"
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>

        <Separator />

        {/* User info */}
        <div className={cn("flex items-center gap-3 p-3", collapsed && "justify-center")}>
          <Avatar className="h-8 w-8">
            <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
              {(user?.full_name || user?.email || "A").charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <AnimatePresence>
            {!collapsed && user && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden min-w-0"
              >
                <p className="text-sm font-medium truncate">{user.full_name || user.email}</p>
                <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={onToggle}
          className="absolute -right-3 top-7 z-50 flex h-6 w-6 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm hover:text-foreground transition-colors"
        >
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
        </button>
      </motion.aside>
    </TooltipProvider>
  );
}
