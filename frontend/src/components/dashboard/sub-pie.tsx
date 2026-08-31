"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS: Record<string, string> = {
  active: "hsl(142 76% 36%)",
  trial: "hsl(38 92% 50%)",
  grace: "hsl(199 89% 48%)",
  expired: "hsl(0 84% 60%)",
  cancelled: "hsl(240 4% 46%)",
};

const LABELS: Record<string, string> = {
  active: "Active",
  trial: "Trial",
  grace: "Grace",
  expired: "Expired",
  cancelled: "Cancelled",
};

interface SubPieProps {
  statuses: Record<string, number>;
}

export function SubPie({ statuses }: SubPieProps) {
  const data = Object.entries(statuses)
    .map(([name, value]) => ({ name, value }))
    .filter((d) => d.value > 0);

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Subscriptions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-6">
          <div className="h-[160px] w-[160px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={72}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {data.map((d) => (
                    <Cell key={d.name} fill={COLORS[d.name] || "hsl(var(--muted))"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2.5">
            {data.map((d) => (
              <div key={d.name} className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[d.name] || "hsl(var(--muted))" }} />
                <span className="text-sm text-muted-foreground w-20">{LABELS[d.name] || d.name}</span>
                <span className="text-sm font-medium">{d.value}</span>
                <span className="text-xs text-muted-foreground">({total > 0 ? Math.round((d.value / total) * 100) : 0}%)</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
