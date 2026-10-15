"use client";

import dynamic from "next/dynamic";
import { ChartSkeleton } from "./ChartSkeleton";
import type { BarChartProps } from "./BarChartInner";

const Inner = dynamic(() => import("./BarChartInner").then((m) => m.BarChartInner), {
  ssr: false,
  loading: () => <ChartSkeleton />,
});

export function BarChart(props: BarChartProps) {
  return <Inner {...props} />;
}
