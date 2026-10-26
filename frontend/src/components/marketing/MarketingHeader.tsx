"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { SignalPulse } from "@/components/ui/SignalPulse";

const links = [
  { label: "Start here", href: "#start-here" },
  { label: "Platform", href: "#platform" },
  { label: "How it works", href: "#how" },
  { label: "Markets", href: "#markets" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

export function MarketingHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#090B0F]/95">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-5 sm:px-8">
        <Link
          href="/"
          className="group inline-flex shrink-0 items-center gap-3"
          aria-label="ORQEVA home"
        >
          <SignalPulse size={28} rings={2} className="shrink-0" />
          <span className="text-[13px] font-semibold tracking-[0.28em] text-text-primary">
            ORQEVA
          </span>
        </Link>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Primary">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[13px] font-medium text-text-secondary transition-colors hover:text-text-primary active:text-green"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/login"
            className="px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 rounded-lg bg-green px-4 py-2 text-sm font-medium text-bg-primary transition-colors hover:bg-green/90 active:scale-[0.98]"
          >
            Start free
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="mobile-navigation"
          aria-label={open ? "Close menu" : "Open menu"}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] text-text-secondary transition-colors hover:bg-white/[0.05] hover:text-text-primary md:hidden"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div
          id="mobile-navigation"
          className="border-t border-white/[0.06] bg-[#090B0F] px-5 pb-5 pt-3 md:hidden"
        >
          <nav className="flex flex-col" aria-label="Mobile">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="border-b border-white/[0.05] py-3.5 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary active:text-green"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="mt-5 flex flex-col gap-2.5">
            <Link
              href="/register"
              onClick={() => setOpen(false)}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-green px-4 py-2.5 text-sm font-medium text-bg-primary active:scale-[0.98]"
            >
              Start free
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="inline-flex items-center justify-center rounded-lg border border-white/[0.08] px-4 py-2.5 text-sm font-medium text-text-secondary"
            >
              Sign in
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
