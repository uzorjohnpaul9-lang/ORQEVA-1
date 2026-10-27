"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

export interface WorkspaceTab {
  href: string;
  label: string;
}

export function WorkspaceTabs({
  tabs,
  label,
}: {
  tabs: WorkspaceTab[];
  label: string;
}) {
  const pathname = usePathname();

  return (
    <div className="sticky top-0 z-20 -mx-4 -mt-4 border-b border-border bg-bg-primary/95 px-4 backdrop-blur lg:static lg:mx-0 lg:mt-0 lg:rounded-xl lg:border lg:px-2">
      <nav className="flex gap-1 overflow-x-auto py-2" aria-label={label}>
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-green/10 text-green"
                  : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
