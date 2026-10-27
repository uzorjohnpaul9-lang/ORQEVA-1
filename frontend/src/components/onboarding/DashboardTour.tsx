"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { TOUR_SESSION_KEY, TOUR_STORAGE_KEY } from "@/lib/onboarding";

type TourStep = {
  target: string;
  fallback: string;
  eyebrow: string;
  title: string;
  body: string;
};

const STEPS: TourStep[] = [
  {
    target: "overview",
    fallback: "overview",
    eyebrow: "Your home base",
    title: "Start with Overview",
    body: "Portfolio value, total P&L, open-position count and active signals are collected here. The Action Center points you to anything that needs attention before you act.",
  },
  {
    target: "signals",
    fallback: "signals",
    eyebrow: "The feed",
    title: "Review AI Signals",
    body: "Each setup carries a direction, entry, invalidation, target and confidence. Confidence ranks setups; it is not a promise of outcome.",
  },
  {
    target: "risk",
    fallback: "more",
    eyebrow: "Guardrails",
    title: "Know Risk Mgmt",
    body: "Set daily loss limits, exposure caps and the kill switch before placing orders. Risk checks apply to paper and live routes.",
  },
  {
    target: "trading",
    fallback: "more",
    eyebrow: "Practice first",
    title: "Place a paper trade",
    body: "Open Trade, choose a symbol and keep Route set to Paper. No real money moves until you explicitly enable live routing.",
  },
  {
    target: "portfolio",
    fallback: "more",
    eyebrow: "Review and learn",
    title: "Track Portfolio and Help",
    body: "Portfolio now groups performance, positions, history and analytics. Help & Guide has the full walkthrough, and you can replay this tour from there.",
  },
];

function readStorage(key: string, storage: Storage): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string, storage: Storage) {
  try {
    storage.setItem(key, value);
  } catch {
    // Storage can be unavailable in private browsing; the tour still works.
  }
}

function visibleTarget(keys: string[]): HTMLElement | null {
  for (const key of keys) {
    const elements = Array.from(
      document.querySelectorAll<HTMLElement>(`[data-tour="${key}"]`)
    );
    for (const element of elements) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      if (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      ) {
        return element;
      }
    }
  }
  return null;
}

export function DashboardTour() {
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  const step = STEPS[index];

  const finish = useCallback(() => {
    writeStorage(TOUR_STORAGE_KEY, "done", window.localStorage);
    setActive(false);
  }, []);

  const next = useCallback(() => {
    if (index === STEPS.length - 1) {
      finish();
      return;
    }
    setIndex((value) => value + 1);
  }, [finish, index]);

  const previous = useCallback(() => {
    setIndex((value) => Math.max(0, value - 1));
  }, []);

  useEffect(() => {
    if (readStorage(TOUR_STORAGE_KEY, window.localStorage)) return;
    if (readStorage(TOUR_SESSION_KEY, window.sessionStorage)) return;

    const timer = window.setTimeout(() => {
      writeStorage(TOUR_SESSION_KEY, "shown", window.sessionStorage);
      setActive(true);
    }, 700);

    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!active) return;

    previousFocus.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const timer = window.setTimeout(() => {
      cardRef.current?.querySelector<HTMLButtonElement>("[data-tour-next]")?.focus();
    }, 60);

    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previousOverflow;
      previousFocus.current?.focus?.();
    };
  }, [active]);

  useEffect(() => {
    if (!active) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        finish();
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        next();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        previous();
        return;
      }
      if (event.key !== "Tab" || !cardRef.current) return;

      const focusable = Array.from(
        cardRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [active, finish, next, previous]);

  useEffect(() => {
    if (!active) return;

    const measure = () => {
      const target = visibleTarget([step.target, step.fallback]);
      if (!target) {
        setTargetRect(null);
        return;
      }

      let rect = target.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > window.innerHeight) {
        target.scrollIntoView({ block: "nearest", inline: "nearest" });
        rect = target.getBoundingClientRect();
      }
      setTargetRect(rect);
    };

    const frame = window.requestAnimationFrame(measure);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [active, step.fallback, step.target]);

  const cardStyle = useMemo<CSSProperties>(() => {
    if (typeof window === "undefined") return {};
    if (!targetRect) {
      return {
        left: "50%",
        top: "50%",
        width: "min(360px, calc(100vw - 2rem))",
        transform: "translate(-50%, -50%)",
      };
    }

    if (window.innerWidth < 1024) {
      return {
        left: 16,
        right: 16,
        bottom: Math.max(92, window.innerHeight - targetRect.top + 16),
      };
    }

    const width = 360;
    let left = targetRect.right + 18;
    if (left + width > window.innerWidth - 16) {
      left = Math.max(16, targetRect.left - width - 18);
    }
    const top = Math.min(
      Math.max(16, targetRect.top - 24),
      Math.max(16, window.innerHeight - 310)
    );

    return { left, top, width };
  }, [targetRect]);

  if (!active) return null;

  return (
    <div
      className="fixed inset-0 z-[100]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dashboard-tour-title"
    >
      {!targetRect && <div className="absolute inset-0 bg-[#03060A]/75" />}
      {targetRect && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed rounded-xl border-2 border-green shadow-[0_0_0_9999px_rgba(3,6,10,0.78)] transition-[top,left,width,height] duration-200"
          style={{
            top: targetRect.top - 4,
            left: targetRect.left - 4,
            width: targetRect.width + 8,
            height: targetRect.height + 8,
          }}
        />
      )}

      <div
        ref={cardRef}
        className="fixed rounded-2xl border border-white/[0.1] bg-[#0E1219] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.55)] sm:p-6"
        style={cardStyle}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-green/80">
              {step.eyebrow}
            </p>
            <h2
              id="dashboard-tour-title"
              className="mt-2 text-lg font-semibold tracking-[-0.02em] text-text-primary"
            >
              {step.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={finish}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-white/[0.06] hover:text-text-primary"
            aria-label="Skip tour"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-3 text-sm leading-6 text-text-secondary">{step.body}</p>

        <div className="mt-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-1.5" aria-label={`Step ${index + 1} of ${STEPS.length}`}>
            {STEPS.map((item, itemIndex) => (
              <span
                key={item.title}
                className={`h-1.5 rounded-full transition-all ${
                  itemIndex === index ? "w-5 bg-green" : "w-1.5 bg-white/20"
                }`}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            {index > 0 && (
              <button
                type="button"
                onClick={previous}
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-medium text-text-secondary transition-colors hover:bg-white/[0.06] hover:text-text-primary"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back
              </button>
            )}
            <button
              type="button"
              data-tour-next
              onClick={next}
              className="inline-flex items-center gap-1.5 rounded-lg bg-green px-3 py-2 text-xs font-semibold text-bg-primary transition-colors hover:bg-green/90 active:scale-[0.98]"
            >
              {index === STEPS.length - 1 ? "Finish" : "Next"}
              {index < STEPS.length - 1 && <ArrowRight className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
