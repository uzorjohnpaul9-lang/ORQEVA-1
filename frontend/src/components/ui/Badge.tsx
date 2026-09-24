import { clsx } from "clsx";

interface BadgeProps {
  variant?: "green" | "red" | "blue" | "yellow" | "purple" | "gray";
  children: React.ReactNode;
  dot?: boolean;
}

const variants = {
  green: "bg-green-dim text-green",
  red: "bg-red-dim text-red",
  blue: "bg-blue-dim text-blue",
  yellow: "bg-yellow-dim text-yellow",
  purple: "bg-purple-dim text-purple",
  gray: "bg-bg-tertiary text-text-secondary",
};

export function Badge({ variant = "gray", children, dot }: BadgeProps) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium", variants[variant])}>
      {dot && <span className={clsx("w-1.5 h-1.5 rounded-full", `bg-current`)} />}
      {children}
    </span>
  );
}
