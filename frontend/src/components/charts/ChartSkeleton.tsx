"use client";

export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div
      style={{ height }}
      className="relative overflow-hidden rounded-lg bg-bg-tertiary/60"
      aria-hidden="true"
    >
      <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    </div>
  );
}
