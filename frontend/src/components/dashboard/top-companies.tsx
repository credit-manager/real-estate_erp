"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface TopCompaniesProps {
  companies: { company_id: number; company_name: string; revenue: number }[];
}

export function TopCompanies({ companies }: TopCompaniesProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Top Companies</CardTitle>
      </CardHeader>
      <CardContent>
        {companies.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">No revenue data</p>
        ) : (
          <div className="space-y-3">
            {companies.slice(0, 5).map((c, i) => (
              <div key={c.company_id} className="flex items-center gap-3">
                <span className="text-xs font-medium text-muted-foreground w-4">{i + 1}</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted shrink-0">
                  <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{c.company_name || `Company #${c.company_id}`}</p>
                </div>
                <span className="text-sm font-semibold tabular-nums">${c.revenue.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
