"use client";

import { useEffect, useRef } from "react";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

export interface CandleBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface CandleChartProps {
  bars: CandleBar[];
  ema9?: (number | null)[];
  ema21?: (number | null)[];
  ema50?: (number | null)[];
  height?: number;
}

const UP = "#00D68F";
const DOWN = "#FF4757";

export function CandleChart({ bars, ema9 = [], ema21 = [], ema50 = [], height = 380 }: CandleChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const labels = bars.map((b) => b.time);
    const ranges = bars.map((b) => [b.low, b.high]);

    const candlePlugin = {
      id: "candleBodies",
      afterDatasetsDraw(chart: Chart) {
        const { ctx, scales } = chart;
        const xs = scales.x as unknown as { getPixelForValue: (v: number) => number; width: number };
        const ys = scales.y as unknown as { getPixelForValue: (v: number) => number };
        const slot = xs.width / Math.max(bars.length, 1);
        const bodyW = Math.max(1, Math.min(9, slot * 0.6));

        ctx.save();
        bars.forEach((b, i) => {
          const x = xs.getPixelForValue(i);
          const up = b.close >= b.open;
          const color = up ? UP : DOWN;
          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = 1;

          const yHigh = ys.getPixelForValue(b.high);
          const yLow = ys.getPixelForValue(b.low);
          const yOpen = ys.getPixelForValue(b.open);
          const yClose = ys.getPixelForValue(b.close);

          ctx.beginPath();
          ctx.moveTo(x, yHigh);
          ctx.lineTo(x, yLow);
          ctx.stroke();

          const top = Math.min(yOpen, yClose);
          const h = Math.max(1, Math.abs(yClose - yOpen));
          ctx.fillRect(x - bodyW / 2, top, bodyW, h);
        });
        ctx.restore();
      },
    };

    const chart = new Chart(canvasRef.current, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "range",
            data: ranges as unknown as number[],
            backgroundColor: "transparent",
            borderWidth: 0,
            barPercentage: 1,
            categoryPercentage: 1,
            order: 3,
          },
          { type: "line", label: "EMA 9", data: ema9 as number[], borderColor: "#FFBE0B", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 0 },
          { type: "line", label: "EMA 21", data: ema21 as number[], borderColor: "#4C6FFF", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 1 },
          { type: "line", label: "EMA 50", data: ema50 as number[], borderColor: "#B14CFF", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 2 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#8B8FA3", font: { size: 12 }, usePointStyle: true } },
          tooltip: {
            filter: (item) => item.dataset.type === "line",
            callbacks: { label: (c) => `${c.dataset.label}: ${Number(c.parsed.y).toFixed(4)}` },
          },
        },
        scales: {
          x: { ticks: { color: "#5A5E72", maxTicksLimit: 10, autoSkip: true }, grid: { color: "#2D3142" } },
          y: { ticks: { color: "#5A5E72" }, grid: { color: "#2D3142" } },
        },
      },
      plugins: [candlePlugin],
    });

    return () => chart.destroy();
  }, [bars, ema9, ema21, ema50]);

  return (
    <div style={{ height }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
