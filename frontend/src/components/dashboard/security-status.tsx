"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Users, AlertTriangle, CheckCircle2 } from "lucide-react";

interface SecurityStatusProps {
  activeSessions: number;
  alerts24h: number;
  logins24h: number;
  critical7d: number;
}

export function SecurityStatus({ activeSessions, alerts24h, logins24h, critical7d }: SecurityStatusProps) {
  const healthy = alerts24h === 0 && critical7d === 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">Security</CardTitle>
          <div className="flex items-center gap-1.5">
            {healthy ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            )}
            <span className={`text-xs font-medium ${healthy ? "text-emerald-500" : "text-amber-500"}`}>
              {healthy ? "Healthy" : "Attention"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              Active Sessions
            </div>
            <span className="text-sm font-semibold">{activeSessions}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              Logins (24h)
            </div>
            <span className="text-sm font-semibold">{logins24h}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Alerts (24h)
            </div>
            <span className={`text-sm font-semibold ${alerts24h > 0 ? "text-red-500" : ""}`}>
              {alerts24h}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              Critical (7d)
            </div>
            <span className={`text-sm font-semibold ${critical7d > 0 ? "text-red-500" : ""}`}>
              {critical7d}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
