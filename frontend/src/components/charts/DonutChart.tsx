"use client";

import { useRef, useEffect } from "react";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

interface DonutChartProps {
  labels: string[];
  data: number[];
  colors: string[];
  height?: number;
}

export function DonutChart({ labels, data, colors, height = 250 }: DonutChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const chart = new Chart(canvasRef.current, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "70%",
        plugins: { legend: { position: "bottom", labels: { color: "#8B8FA3", padding: 16, font: { size: 12 } } } },
      },
    });
    return () => chart.destroy();
  }, [data, labels, colors]);

  return <div style={{ height }}><canvas ref={canvasRef} /></div>;
}
