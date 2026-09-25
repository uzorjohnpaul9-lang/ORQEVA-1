import { clsx } from "clsx";
import type { ReactNode } from "react";

interface AdminCardProps {
  children: ReactNode;
  className?: string;
  padding?: boolean;
}

export function AdminCard({ children, className, padding = true }: AdminCardProps) {
  return (
    <div
      className={clsx(
        "bg-gradient-to-br from-bg-secondary via-bg-tertiary to-bg-tertiary",
        "border border-purple/25 rounded-xl shadow-[0_0_0_1px_rgba(155,89,182,0.08),0_8px_24px_-12px_rgba(155,89,182,0.35)]",
        padding && "p-5",
        className
      )}
    >
      {children}
    </div>
  );
}

export function AdminCardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("flex items-center justify-between mb-4", className)}>{children}</div>;
}

export function AdminCardTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-purple">{children}</h3>;
}

export function AdminStatCard({ label, value, change, icon }: { label: string; value: string; change?: string; icon?: ReactNode }) {
  const isPositive = change && !change.startsWith("-");
  return (
    <AdminCard>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold mt-1 text-purple">{value}</p>
          {change && (
            <p className={clsx("text-xs mt-1 font-medium", isPositive ? "text-green" : "text-red")}>
              {change}
            </p>
          )}
        </div>
        {icon && <div className="text-purple/60">{icon}</div>}
      </div>
    </AdminCard>
  );
}