"use client";

import { useRef, useEffect } from "react";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

interface BarChartProps {
  data: { labels: string[]; datasets: { label: string; data: number[]; color: string }[] };
  height?: number;
}

export function BarChart({ data, height = 300 }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const chart = new Chart(canvasRef.current, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: data.datasets.map((ds) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: ds.color,
          borderRadius: 4,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: "#8B8FA3", font: { size: 12 } } } },
        scales: {
          x: { ticks: { color: "#5A5E72" }, grid: { display: false } },
          y: { ticks: { color: "#5A5E72" }, grid: { color: "#2D3142" } },
        },
      },
    });
    return () => chart.destroy();
  }, [data]);

  return <div style={{ height }}><canvas ref={canvasRef} /></div>;
}
