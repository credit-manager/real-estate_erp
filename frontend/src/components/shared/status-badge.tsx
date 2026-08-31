import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const statusConfig: Record<string, { label: string; variant: "success" | "warning" | "destructive" | "info" | "secondary" }> = {
  active: { label: "Active", variant: "success" },
  trial: { label: "Trial", variant: "warning" },
  suspended: { label: "Suspended", variant: "destructive" },
  expired: { label: "Expired", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "secondary" },
  inactive: { label: "Inactive", variant: "secondary" },
  grace: { label: "Grace", variant: "info" },
  revoked: { label: "Revoked", variant: "destructive" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] || { label: status, variant: "secondary" as const };
  return (
    <Badge variant={config.variant} className={cn("capitalize", className)}>
      {config.label}
    </Badge>
  );
}
