import { clsx } from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}

const variants = {
  primary: "bg-green text-bg-primary hover:bg-green/90 font-medium",
  secondary: "bg-bg-tertiary text-text-primary hover:bg-bg-hover border border-border",
  danger: "bg-red text-white hover:bg-red/90",
  ghost: "text-text-secondary hover:bg-bg-hover hover:text-text-primary",
};

const sizes = {
  sm: "px-3 py-1.5 text-xs rounded-md",
  md: "px-4 py-2 text-sm rounded-lg",
  lg: "px-6 py-3 text-base rounded-lg",
};

export function Button({ variant = "primary", size = "md", className, children, ...props }: ButtonProps) {
  return (
    <button className={clsx("inline-flex items-center justify-center gap-2 transition-colors disabled:opacity-50", variants[variant], sizes[size], className)} {...props}>
      {children}
    </button>
  );
}
