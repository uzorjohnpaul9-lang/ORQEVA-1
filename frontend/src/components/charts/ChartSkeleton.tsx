"use client";

export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div
      style={{ height }}
      className="animate-pulse rounded-lg bg-bg-tertiary/60"
      aria-hidden="true"
    />
  );
}
