"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Building2, CreditCard, Shield, Package, AlertTriangle, Clock } from "lucide-react";

interface Activity {
  id: number;
  action: string;
  master_user_email: string;
  resource_type: string;
  created_at: string;
  result: string;
}

const actionIcons: Record<string, typeof Building2> = {
  COMPANY_CREATED: Building2,
  COMPANY_TRANSITION: Building2,
  SUBSCRIPTION_RENEWED: CreditCard,
  LICENSE_SUSPENDED: Shield,
  MODULE_ENABLED: Package,
  MODULE_DISABLED: Package,
  ACCOUNT_LOCKED: AlertTriangle,
  EMERGENCY_KILL_ALL: AlertTriangle,
};

function timeAgo(dateStr: string) {
  if (!dateStr) return "";
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now.getTime() - then.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function friendlyAction(action: string) {
  return action
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ActivityTimelineProps {
  activities: Activity[];
}

export function ActivityTimeline({ activities }: ActivityTimelineProps) {
  return (
    <Card className="col-span-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">Recent Activity</CardTitle>
          <Badge variant="secondary" className="text-xs">
            <Clock className="mr-1 h-3 w-3" />
            Live
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {activities.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No recent activity</p>
        ) : (
          <div className="space-y-0">
            {activities.map((activity, i) => {
              const Icon = actionIcons[activity.action] || Building2;
              return (
                <div
                  key={activity.id}
                  className="flex items-start gap-3 py-3 border-b last:border-0"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">
                      <span className="font-medium">{activity.master_user_email}</span>
                      {" "}
                      <span className="text-muted-foreground">{friendlyAction(activity.action)}</span>
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-muted-foreground">{activity.resource_type}</span>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground">{timeAgo(activity.created_at)}</span>
                    </div>
                  </div>
                  <Badge
                    variant={activity.result === "SUCCESS" ? "success" : "destructive"}
                    className="shrink-0 text-[10px]"
                  >
                    {activity.result}
                  </Badge>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
