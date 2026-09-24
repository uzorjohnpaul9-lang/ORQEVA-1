"use client";

import { clsx } from "clsx";

interface ToastProps {
  message: string;
  type?: "success" | "error" | "info";
  onClose: () => void;
}

const icons: Record<string, string> = {
  success: "M20 6L9 17l-5-5",
  error: "M12 9v4m0 4h.01M12 2a10 10 0 100 20 10 10 0 000-20z",
  info: "M12 2a10 10 0 100 20 10 10 0 000-20zm0 5v2m0 4h.01",
};

const colors = {
  success: "bg-green/10 border-green/30 text-green",
  error: "bg-red/10 border-red/30 text-red",
  info: "bg-blue/10 border-blue/30 text-blue",
};

export function Toast({ message, type = "success", onClose }: ToastProps) {
  return (
    <div className={clsx("fixed bottom-24 xl:bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg animate-slide-up", colors[type])}>
      <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d={icons[type]} />
      </svg>
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
