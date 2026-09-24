import { clsx } from "clsx";
import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, ...props }: InputProps) {
  return (
    <div className="space-y-1.5">
      {label && <label className="block text-sm font-medium text-text-secondary">{label}</label>}
      <input
        className={clsx(
          "w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-green/50 focus:ring-1 focus:ring-green/20 transition-colors",
          error && "border-red/50",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-red">{error}</p>}
    </div>
  );
}
