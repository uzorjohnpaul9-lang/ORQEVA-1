"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi } from "lightweight-charts";

interface CandlePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface VolumePoint {
  time: number;
  value: number;
  color?: string;
}

const DEMO_DATA: CandlePoint[] = [
  { time: 1717200000, open: 1.0842, high: 1.0860, low: 1.0835, close: 1.0851 },
  { time: 1717203600, open: 1.0851, high: 1.0858, low: 1.0844, close: 1.0849 },
  { time: 1717207200, open: 1.0849, high: 1.0864, low: 1.0847, close: 1.0861 },
  { time: 1717210800, open: 1.0861, high: 1.0868, low: 1.0852, close: 1.0855 },
  { time: 1717214400, open: 1.0855, high: 1.0872, low: 1.0853, close: 1.0870 },
  { time: 1717218000, open: 1.0870, high: 1.0876, low: 1.0862, close: 1.0865 },
  { time: 1717221600, open: 1.0865, high: 1.0880, low: 1.0864, close: 1.0878 },
  { time: 1717225200, open: 1.0878, high: 1.0884, low: 1.0870, close: 1.0872 },
];

const DEMO_VOL: VolumePoint[] = [
  { time: 1717200000, value: 8420, color: "rgba(0,214,143,0.4)" },
  { time: 1717203600, value: 7650, color: "rgba(255,71,87,0.4)" },
  { time: 1717207200, value: 9120, color: "rgba(0,214,143,0.4)" },
  { time: 1717210800, value: 8340, color: "rgba(255,71,87,0.4)" },
  { time: 1717214400, value: 9780, color: "rgba(0,214,143,0.4)" },
  { time: 1717218000, value: 8620, color: "rgba(255,71,87,0.4)" },
  { time: 1717221600, value: 10420, color: "rgba(0,214,143,0.4)" },
  { time: 1717225200, value: 9160, color: "rgba(255,71,87,0.4)" },
];

const SYMBOLS = [
  { value: "EUR/USD", label: "EUR/USD" },
  { value: "BTC/USDT", label: "BTC/USDT" },
  { value: "XAU/USD", label: "XAU/USD" },
];

const INTERVALS = [
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1d", label: "1D" },
];

export function InteractiveMarketChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [symbol, setSymbol] = useState("EUR/USD");
  const [interval, setInterval] = useState("1h");
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0B0D17" },
        textColor: "#8B8FA3",
      },
      grid: {
        vertLines: { color: "#1F2233" },
        horzLines: { color: "#1F2233" },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#8B8FA3", style: 3 },
        horzLine: { color: "#8B8FA3", style: 3 },
      },
      rightPriceScale: {
        borderColor: "#2D3142",
      },
      timeScale: {
        borderColor: "#2D3142",
        timeVisible: true,
        secondsVisible: false,
      },
      height: 420,
    });

    const candleSeries = (chart as any).addCandlestickSeries({
      upColor: "#00D68F",
      downColor: "#FF4757",
      borderVisible: false,
      wickUpColor: "#00D68F",
      wickDownColor: "#FF4757",
    });

    const volumeSeries = (chart as any).addHistogramSeries({
      color: "#26a69a",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    candleSeries.setData(DEMO_DATA);
    volumeSeries.setData(DEMO_VOL);

    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    setIsReady(true);

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, []);

  return (
    <div className="relative mx-auto w-full max-w-[640px] overflow-hidden rounded-[22px] border border-white/[0.09] bg-[#0E1117]/95 shadow-[0_32px_100px_rgba(0,0,0,0.55)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="h-2.5 w-2.5 rounded-full bg-green animate-pulse" />
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-muted">Live chart preview</p>
            <p className="text-sm font-semibold text-text-primary">{symbol} <span className="font-normal text-text-muted">• {interval.toUpperCase()}</span></p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/[0.08] bg-white/[0.02] p-0.5">
            {SYMBOLS.map((s) => (
              <button
                key={s.value}
                onClick={() => setSymbol(s.value)}
                className={`px-2 py-1 text-[10px] uppercase tracking-[0.12em] rounded-md transition-colors ${symbol === s.value ? "bg-green/15 text-green" : "text-text-muted hover:text-text-primary"}`}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="flex rounded-lg border border-white/[0.08] bg-white/[0.02] p-0.5">
            {INTERVALS.map((i) => (
              <button
                key={i.value}
                onClick={() => setInterval(i.value)}
                className={`px-2 py-1 text-[10px] uppercase tracking-[0.12em] rounded-md transition-colors ${interval === i.value ? "bg-green/15 text-green" : "text-text-muted hover:text-text-primary"}`}
              >
                {i.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div ref={containerRef} className="h-[420px] w-full" />
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-text-muted">Loading chart…</div>
      )}
      <div className="border-t border-white/[0.06] px-5 py-3 text-[10px] uppercase tracking-[0.16em] text-text-muted">
        Demo data • Read-only • Zoom, pan & crosshair enabled
      </div>
    </div>
  );
}
