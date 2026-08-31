"use client";

import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon: React.ReactNode;
  sparkline?: number[];
}

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data.length) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const h = 24;
  const w = 60;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline
        fill="none"
        stroke={positive ? "hsl(142 76% 36%)" : "hsl(0 84% 60%)"}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

export function KpiCard({ title, value, change, changeLabel, icon, sparkline }: KpiCardProps) {
  const isPositive = (change ?? 0) > 0;
  const isNeutral = change === undefined || change === 0;

  return (
    <Card className="group relative overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold tracking-tight">{value}</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted/50 text-muted-foreground group-hover:bg-muted transition-colors">
            {icon}
          </div>
        </div>
        {(change !== undefined || sparkline) && (
          <div className="mt-3 flex items-center gap-2">
            {sparkline && <MiniSparkline data={sparkline} positive={isPositive} />}
            {change !== undefined && (
              <div className={cn(
                "flex items-center gap-0.5 text-xs font-medium",
                isPositive ? "text-emerald-600 dark:text-emerald-400" : isNeutral ? "text-muted-foreground" : "text-red-600 dark:text-red-400"
              )}>
                {isPositive ? <TrendingUp className="h-3 w-3" /> : isNeutral ? <Minus className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                <span>{isPositive ? "+" : ""}{change.toFixed(1)}%</span>
              </div>
            )}
            {changeLabel && <span className="text-xs text-muted-foreground">{changeLabel}</span>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
