import { clsx } from "clsx";
import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: boolean;
  /** Lift + brighten border on hover. Use for clickable cards. */
  interactive?: boolean;
}

export function Card({ children, className, padding = true, interactive = false }: CardProps) {
  return (
    <div
      className={clsx(
        "bg-bg-secondary border border-border rounded-xl transition-[transform,border-color,box-shadow] duration-200 ease-out",
        padding && "p-5",
        interactive && "hover:-translate-y-0.5 hover:border-border-light hover:shadow-lg hover:shadow-black/20",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("flex items-center justify-between mb-4", className)}>{children}</div>;
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-text-primary">{children}</h3>;
}

export function StatCard({ label, value, change, icon }: { label: string; value: string; change?: string; icon?: ReactNode }) {
  const isPositive = change && !change.startsWith("-");
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change && (
            <p className={clsx("text-xs mt-1 font-medium", isPositive ? "text-green" : "text-red")}>
              {change}
            </p>
          )}
        </div>
        {icon && <div className="text-text-muted">{icon}</div>}
      </div>
    </Card>
  );
}
