"use client";

import dynamic from "next/dynamic";
import { ChartSkeleton } from "./ChartSkeleton";
import type { DonutChartProps } from "./DonutChartInner";

const Inner = dynamic(() => import("./DonutChartInner").then((m) => m.DonutChartInner), {
  ssr: false,
  loading: () => <ChartSkeleton height={250} />,
});

export function DonutChart(props: DonutChartProps) {
  return <Inner {...props} />;
}
