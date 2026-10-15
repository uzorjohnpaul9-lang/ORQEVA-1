import { clsx } from "clsx";

interface SignalPulseProps {
  size?: number;
  color?: string;
  rings?: number;
  className?: string;
  /** Center a child (e.g. an icon) instead of a solid dot. */
  children?: React.ReactNode;
}

/**
 * Signal-Pulse — the ORQEVA signature motif.
 * Concentric rings broadcast outward from a core: a signal being transmitted.
 * Pure CSS keyframes so it stays cheap and works without JS.
 */
export function SignalPulse({
  size = 40,
  color = "var(--color-green)",
  rings = 3,
  className,
  children,
}: SignalPulseProps) {
  return (
    <span
      className={clsx("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {Array.from({ length: rings }).map((_, i) => (
        <span
          key={i}
          className="absolute inset-0 rounded-full animate-pulse-ring"
          style={{
            border: `1.5px solid ${color}`,
            animationDelay: `${i * (2.4 / rings)}s`,
          }}
        />
      ))}
      <span
        className="relative flex items-center justify-center rounded-full"
        style={{
          width: size * 0.36,
          height: size * 0.36,
          background: color,
          color: "var(--color-bg-primary)",
        }}
      >
        {children}
      </span>
    </span>
  );
}
