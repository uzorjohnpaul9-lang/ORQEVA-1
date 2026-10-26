"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface Term {
  term: string;
  category: string;
  definition: string;
}

export default function GlossaryPage() {
  const { token } = useAuth();
  const [terms, setTerms] = useState<Term[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  useEffect(() => {
    if (!token) return;
    api<{ terms: Term[] }>("/api/learn/glossary", { token })
      .then((r) => setTerms(r.terms))
      .catch(() => {});
  }, [token]);

  const categories = useMemo(() => {
    const set = new Set(terms.map((t) => t.category));
    return ["all", ...Array.from(set).sort()];
  }, [terms]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return terms
      .filter((t) => category === "all" || t.category === category)
      .filter((t) => !q || t.term.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q))
      .sort((a, b) => a.term.localeCompare(b.term));
  }, [terms, query, category]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Trading Glossary</h1>
          <p className="text-sm text-text-secondary mt-1">Every term used on ORQEVA, in plain English.</p>
        </div>
        <Link href="/learn" className="text-sm text-green hover:underline">
          ← Back to Academy
        </Link>
      </div>

      <div className="space-y-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search terms…"
          className="w-full bg-bg-tertiary border border-border rounded-lg px-3.5 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-green/50 focus:ring-1 focus:ring-green/20 transition-colors"
        />
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                category === c ? "bg-green text-bg-primary" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
              )}
            >
              {c === "all" ? "ALL" : c.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.length === 0 && (
          <Card>
            <p className="text-sm text-text-muted">No terms match your search.</p>
          </Card>
        )}
        {filtered.map((t) => (
          <Card key={t.term}>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold">{t.term}</h3>
              <Badge variant="gray">{t.category}</Badge>
            </div>
            <p className="text-sm text-text-secondary mt-2 leading-relaxed">{t.definition}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
