"use client";

import type { ReactNode } from "react";

function inline(text: string, key: number): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${key}-b${i++}`} className="font-semibold">{tok.slice(2, -2)}</strong>);
    else out.push(<em key={`${key}-i${i++}`} className="italic text-text-secondary">{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function RichText({ text, className }: { text: string; className?: string }) {
  const lines = text.split("\n");
  return (
    <div className={className ?? "space-y-2 leading-relaxed"}>
      {lines.map((line, idx) => {
        const t = line.trim();
        if (!t) return <div key={idx} className="h-1" />;
        if (/^[-*]\s+/.test(t)) {
          return (
            <div key={idx} className="flex gap-2">
              <span className="text-green">•</span>
              <span>{inline(t.replace(/^[-*]\s+/, ""), idx)}</span>
            </div>
          );
        }
        return <p key={idx}>{inline(t, idx)}</p>;
      })}
    </div>
  );
}
