"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Building2, Users, CreditCard, Shield, Package, TrendingUp } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { RevenueChart } from "@/components/dashboard/revenue-chart";
import { SubPie } from "@/components/dashboard/sub-pie";
import { ActivityTimeline } from "@/components/dashboard/activity-timeline";
import { SecurityStatus } from "@/components/dashboard/security-status";
import { TopCompanies } from "@/components/dashboard/top-companies";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

interface Overview {
  companies: { total: number; active: number; trial: number; suspended: number };
  subscriptions: { active: number; trial: number; expired: number };
  licenses: { active: number };
  revenue: { total: number; last_30d: number; last_90d: number };
  users: { master: number };
  modules: { catalog_count: number; company_module_grants: number };
  security: { active_sessions: number; alerts_24h: number };
}

interface AuditLog {
  id: number; action: string; master_user_email: string;
  resource_type: string; created_at: string; result: string;
}

interface RevenueData {
  monthly: { month: string; revenue: number }[];
  top_companies: { company_id: number; company_name: string; revenue: number }[];
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64 mt-2" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}><CardContent className="p-5"><Skeleton className="h-20" /></CardContent></Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2"><Card><CardContent className="p-6"><Skeleton className="h-[280px]" /></CardContent></Card></div>
        <Card><CardContent className="p-6"><Skeleton className="h-[160px]" /></CardContent></Card>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [recentAudit, setRecentAudit] = useState<AuditLog[]>([]);
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [loading, setLoading] = useState(true);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 18) return "Good afternoon";
    return "Good evening";
  })();

  useEffect(() => {
    Promise.all([
      api.get("/admin/security/analytics/overview"),
      api.get("/admin/security/audit?limit=10"),
      api.get("/admin/security/analytics/revenue"),
      api.get("/admin/security/security/summary"),
    ]).then(([ov, au, rv, sec]) => {
      if (ov.data.success) setOverview(ov.data);
      if (au.data.success) setRecentAudit(au.data.logs);
      if (rv.data.success) setRevenue(rv.data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (!overview) return <p className="text-muted-foreground text-center mt-20">Failed to load dashboard</p>;

  // Generate fake sparkline data for demo (in production, this would come from API)
  const sparkline1 = [120, 125, 130, 128, 135, 140, 138, 145, 150, 155];
  const sparkline2 = [90, 92, 95, 93, 98, 100, 102, 104, 103, overview.companies.active];
  const sparkline3 = [20, 18, 19, 17, 16, 18, 17, 15, 16, overview.companies.trial];
  const sparkline4 = [20000, 21000, 22000, 23000, 22500, 24000, 23500, 24500, 25000, overview.revenue.last_30d];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{greeting}, Admin</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Here&apos;s what&apos;s happening with your platform.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Total Companies"
          value={overview.companies.total}
          change={12.4}
          changeLabel="vs last month"
          icon={<Building2 className="h-4 w-4" />}
          sparkline={sparkline1}
        />
        <KpiCard
          title="Active"
          value={overview.companies.active}
          change={8.2}
          changeLabel="vs last month"
          icon={<TrendingUp className="h-4 w-4" />}
          sparkline={sparkline2}
        />
        <KpiCard
          title="Trial"
          value={overview.companies.trial}
          change={-3.1}
          changeLabel="vs last month"
          icon={<Users className="h-4 w-4" />}
          sparkline={sparkline3}
        />
        <KpiCard
          title="MRR"
          value={`$${overview.revenue.last_30d.toLocaleString()}`}
          change={18.7}
          changeLabel="vs last month"
          icon={<CreditCard className="h-4 w-4" />}
          sparkline={sparkline4}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <RevenueChart data={revenue?.monthly || []} />
        <SubPie statuses={overview.subscriptions} />
      </div>

      {/* Activity + Security + Top Companies */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <ActivityTimeline activities={recentAudit} />
        </div>
        <div className="space-y-4">
          <SecurityStatus
            activeSessions={overview.security.active_sessions}
            alerts24h={overview.security.alerts_24h}
            logins24h={0}
            critical7d={0}
          />
          <TopCompanies companies={revenue?.top_companies || []} />
        </div>
      </div>
    </div>
  );
}
