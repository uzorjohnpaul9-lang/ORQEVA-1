"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

export interface CandleBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface PriceLine {
  price: number;
  label: string;
  color: string;
  dashed?: boolean;
}

export interface CandleChartProps {
  bars: CandleBar[];
  ema9?: (number | null)[];
  ema21?: (number | null)[];
  ema50?: (number | null)[];
  lines?: PriceLine[];
  height?: number;
}

const UP = "#00D68F";
const DOWN = "#FF4757";
const MIN_BARS = 8;

function fmt(v: number): string {
  return v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v.toFixed(4);
}

function ZoomButton({ label, onClick, title }: { label: string; onClick: () => void; title: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="w-7 h-7 flex items-center justify-center rounded-md border border-border bg-bg-secondary/90 text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors text-sm font-medium"
    >
      {label}
    </button>
  );
}

export function CandleChartInner({
  bars,
  ema9 = [],
  ema21 = [],
  ema50 = [],
  lines = [],
  height = 380,
}: CandleChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  // Visible window into `bars` as [start, end) indices; null = show all.
  const [view, setView] = useState<[number, number] | null>(null);

  const total = bars.length;
  const [start, end] = useMemo<[number, number]>(
    () => (view ? [view[0], view[1]] : [0, total]),
    [view, total]
  );
  const size = Math.max(1, end - start);

  useEffect(() => setMounted(true), []);

  // Reset the window whenever the underlying series changes (new symbol/interval).
  useEffect(() => {
    setView(null);
  }, [bars]);

  const clampView = useCallback(
    (s: number, e: number): [number, number] => {
      let n = Math.round(e - s);
      n = Math.max(MIN_BARS, Math.min(total, n));
      let ns = Math.round(s);
      if (ns < 0) ns = 0;
      if (ns + n > total) ns = total - n;
      if (ns < 0) ns = 0;
      return [ns, ns + n];
    },
    [total]
  );

  const zoomBy = useCallback(
    (ratio: number) => {
      if (total <= MIN_BARS) return;
      const cur = view ?? [0, total];
      const curSize = cur[1] - cur[0];
      const center = (cur[0] + cur[1]) / 2;
      const next = clampView(center - (curSize * ratio) / 2, center + (curSize * ratio) / 2);
      setView(next[0] === 0 && next[1] === total ? null : next);
    },
    [view, total, clampView]
  );

  const panByBars = useCallback(
    (delta: number) => {
      if (total <= MIN_BARS || !view) return;
      const next = clampView(view[0] + delta, view[1] + delta);
      setView(next[0] === 0 && next[1] === total ? null : next);
    },
    [view, total, clampView]
  );

  const reset = useCallback(() => setView(null), []);

  // Wheel zoom — needs a non-passive listener so we can preventDefault.
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (total <= MIN_BARS) return;
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? 0.8 : 1.25);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomBy, total, fullscreen]);

  // Pinch + drag via pointer events.
  const pointers = useRef<Map<number, number>>(new Map());
  const lastDist = useRef<number | null>(null);
  const lastX = useRef<number | null>(null);

  const onPointerDown = (e: ReactPointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, e.clientX);
    lastX.current = e.clientX;
    lastDist.current = null;
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, e.clientX);
    const xs = Array.from(pointers.current.values());
    if (xs.length >= 2) {
      const dist = Math.abs(xs[0] - xs[1]) || 1;
      if (lastDist.current != null && dist > 0) {
        zoomBy(lastDist.current / dist);
      }
      lastDist.current = dist;
    } else {
      const dx = e.clientX - (lastX.current ?? e.clientX);
      const width = areaRef.current?.clientWidth || 1;
      const barsPerPx = size / width;
      if (Math.abs(dx) >= 1) panByBars(-dx * barsPerPx);
      lastX.current = e.clientX;
    }
  };

  const onPointerUp = (e: ReactPointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size === 1) {
      lastX.current = Array.from(pointers.current.values())[0];
      lastDist.current = null;
    } else if (pointers.current.size === 0) {
      lastX.current = null;
      lastDist.current = null;
    }
  };

  // Chart lifecycle — re-runs only when the visible window changes.
  useEffect(() => {
    if (!canvasRef.current) return;

    const viewBars = bars.slice(start, end);
    const vEma9 = ema9.slice(start, end);
    const vEma21 = ema21.slice(start, end);
    const vEma50 = ema50.slice(start, end);

    const labels = viewBars.map((b) => b.time);
    const ranges = viewBars.map((b) => [b.low, b.high]);

    const candlePlugin = {
      id: "candleBodies",
      afterDatasetsDraw(chart: Chart) {
        const { ctx, scales } = chart;
        const xs = scales.x as unknown as { getPixelForValue: (v: number) => number; width: number };
        const ys = scales.y as unknown as { getPixelForValue: (v: number) => number };
        const slot = xs.width / Math.max(viewBars.length, 1);
        const bodyW = Math.max(2, Math.min(14, slot * 0.7));

        ctx.save();
        viewBars.forEach((b, i) => {
          const x = xs.getPixelForValue(i);
          const up = b.close >= b.open;
          const color = up ? UP : DOWN;
          const wickColor = up ? "#00D68F" : "#FF4757";

          const yHigh = ys.getPixelForValue(b.high);
          const yLow = ys.getPixelForValue(b.low);
          const yOpen = ys.getPixelForValue(b.open);
          const yClose = ys.getPixelForValue(b.close);

          // Wick
          ctx.strokeStyle = wickColor;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(x, yHigh);
          ctx.lineTo(x, yLow);
          ctx.stroke();

          // Body
          const top = Math.min(yOpen, yClose);
          const h = Math.max(2, Math.abs(yClose - yOpen));
          ctx.fillStyle = up ? "rgba(0, 214, 143, 0.9)" : "rgba(255, 71, 87, 0.9)";
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.fillRect(x - bodyW / 2, top, bodyW, h);
          ctx.strokeRect(x - bodyW / 2, top, bodyW, h);
        });
        ctx.restore();
      },
    };

    const linePlugin = {
      id: "priceLines",
      afterDatasetsDraw(chart: Chart) {
        if (lines.length === 0) return;
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const ys = scales.y as unknown as { getPixelForValue: (v: number) => number };

        ctx.save();
        ctx.font = "11px ui-monospace, monospace";
        ctx.textBaseline = "middle";
        lines.forEach((ln) => {
          const y = ys.getPixelForValue(ln.price);
          if (!isFinite(y) || y < chartArea.top || y > chartArea.bottom) return;

          ctx.strokeStyle = ln.color;
          ctx.lineWidth = 1.5;
          ctx.setLineDash(ln.dashed ? [6, 4] : []);
          ctx.beginPath();
          ctx.moveTo(chartArea.left, y);
          ctx.lineTo(chartArea.right, y);
          ctx.stroke();
          ctx.setLineDash([]);

          const text = `${ln.label} ${fmt(ln.price)}`;
          const pad = 4;
          const w = ctx.measureText(text).width + pad * 2;
          const h = 16;
          const x = chartArea.right - w - 4;
          ctx.fillStyle = ln.color;
          ctx.fillRect(x, y - h / 2, w, h);
          ctx.fillStyle = "#0B0D17";
          ctx.fillText(text, x + pad, y);
        });
        ctx.restore();
      },
    };

    const prices = viewBars.flatMap((b) => [b.low, b.high]).concat(lines.map((l) => l.price));
    let yMin: number | undefined;
    let yMax: number | undefined;
    if (prices.length > 0) {
      const lo = Math.min(...prices);
      const hi = Math.max(...prices);
      const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.015 || 1;
      yMin = lo - pad;
      yMax = hi + pad;
    }

    const crosshairPlugin = {
      id: "crosshair",
      afterDraw(chart: Chart, args: unknown, options: any) {
        const { ctx, chartArea, scales, tooltip } = chart;
        if (!chartArea) return;
        const active = (tooltip as any)?.getActiveElements?.();
        if (!active || active.length === 0) return;
        const el = active[0];
        const x = (scales.x as any).getPixelForValue(el.index);
        const y = el.element?.y ?? (scales.y as any).getPixelForValue(el.element?.yValue ?? 0);
        ctx.save();
        ctx.strokeStyle = "rgba(139, 143, 163, 0.5)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
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
          { type: "line", label: "EMA 9", data: vEma9 as number[], borderColor: "#FFBE0B", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 0 },
          { type: "line", label: "EMA 21", data: vEma21 as number[], borderColor: "#4C6FFF", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 1 },
          { type: "line", label: "EMA 50", data: vEma50 as number[], borderColor: "#B14CFF", backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, spanGaps: true, tension: 0.2, order: 2 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#8B8FA3", font: { size: 12 }, usePointStyle: true } },
          tooltip: {
            mode: "index",
            intersect: false,
            backgroundColor: "rgba(11, 13, 23, 0.95)",
            titleColor: "#E4E6EB",
            bodyColor: "#E4E6EB",
            borderColor: "#2D3142",
            borderWidth: 1,
            callbacks: {
              title: (items) => {
                const idx = items[0]?.dataIndex;
                if (idx == null) return "";
                const b = viewBars[idx];
                return b ? b.time : "";
              },
              label: (c) => {
                if (c.dataset.type === "line") {
                  return `${c.dataset.label}: ${Number(c.parsed.y).toFixed(4)}`;
                }
                if (c.dataset.label === "range") {
                  const idx = c.dataIndex;
                  const b = viewBars[idx];
                  if (b) {
                    const up = b.close >= b.open;
                    return [
                      `O: ${b.open.toFixed(4)}`,
                      `H: ${b.high.toFixed(4)}`,
                      `L: ${b.low.toFixed(4)}`,
                      `C: ${b.close.toFixed(4)} ${up ? "(+)" : "(-)"}`,
                    ];
                  }
                }
                return "";
              },
            },
          },
        },
        scales: {
          x: { ticks: { color: "#5A5E72", maxTicksLimit: 8, autoSkip: true, maxRotation: 0, minRotation: 0 }, grid: { color: "#1F2233", drawTicks: false } },
          y: { min: yMin, max: yMax, position: "right", ticks: { color: "#5A5E72", padding: 8 }, grid: { color: "#1F2233", drawTicks: false }, border: { display: false } },
        },
      },
      plugins: [candlePlugin, linePlugin, crosshairPlugin],
    });

    return () => chart.destroy();
  }, [bars, ema9, ema21, ema50, lines, start, end, fullscreen]);

  const controls = (
    <div className="absolute right-2 top-2 z-10 flex items-center gap-1">
      <span className="mr-1 hidden sm:inline text-[10px] text-text-muted">
        {start + 1}–{end} / {total}
      </span>
      <ZoomButton label="−" title="Zoom out" onClick={() => zoomBy(1.25)} />
      <ZoomButton label="+" title="Zoom in" onClick={() => zoomBy(0.8)} />
      <ZoomButton label="⟲" title="Reset zoom" onClick={reset} />
      <ZoomButton label={fullscreen ? "✕" : "⛶"} title={fullscreen ? "Exit fullscreen" : "Fullscreen"} onClick={() => setFullscreen((v) => !v)} />
    </div>
  );

  const chartArea = (
    <div
      ref={areaRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      className="relative w-full flex-1 min-h-0 touch-none select-none cursor-grab active:cursor-grabbing"
      style={{ height: fullscreen ? "100%" : height }}
    >
      {controls}
      <canvas ref={canvasRef} />
    </div>
  );

  if (fullscreen && mounted) {
    return createPortal(
      <div className="fixed inset-0 z-[100] flex flex-col bg-bg-primary p-3 md:p-6">
        {chartArea}
      </div>,
      document.body
    );
  }

  return <div className="relative">{chartArea}</div>;
}
