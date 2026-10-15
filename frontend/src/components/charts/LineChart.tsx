"use client";

import dynamic from "next/dynamic";
import { ChartSkeleton } from "./ChartSkeleton";
import type { LineChartProps } from "./LineChartInner";

const Inner = dynamic(() => import("./LineChartInner").then((m) => m.LineChartInner), {
  ssr: false,
  loading: () => <ChartSkeleton />,
});

export function LineChart(props: LineChartProps) {
  return <Inner {...props} />;
}
