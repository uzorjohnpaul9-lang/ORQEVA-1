"use client";

import dynamic from "next/dynamic";
import { ChartSkeleton } from "./ChartSkeleton";
import type { CandleChartProps } from "./CandleChartInner";

export type { CandleBar, PriceLine } from "./CandleChartInner";

const Inner = dynamic(() => import("./CandleChartInner").then((m) => m.CandleChartInner), {
  ssr: false,
  loading: () => <ChartSkeleton height={380} />,
});

export function CandleChart(props: CandleChartProps) {
  return <Inner {...props} />;
}
