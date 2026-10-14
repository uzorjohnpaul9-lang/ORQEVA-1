"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InstructorChat } from "@/components/learn/InstructorChat";
import { Quiz, type QuizQuestion } from "@/components/learn/Quiz";

interface LessonMeta {
  slug: string;
  title: string;
  level: string;
  minutes: number;
  category: string;
  methodology: string | null;
  summary: string;
}

interface Lesson extends LessonMeta {
  objectives: string[];
  sections: { heading: string; body: string[]; bullets?: string[] }[];
  takeaways: string[];
  quiz: QuizQuestion[];
}

interface LearnStatus {
  configured: boolean;
  provider: string;
  model: string;
  lessons: number;
  glossary_terms: number;
  methodologies: number;
}

const STORAGE_KEY = "orqeva.learn.done";

function levelVariant(level: string): "green" | "yellow" | "red" | "gray" {
  if (level === "beginner") return "green";
  if (level === "intermediate") return "yellow";
  if (level === "advanced") return "red";
  return "gray";
}

export default function LearnPage() {
  const { token } = useAuth();
  const [status, setStatus] = useState<LearnStatus | null>(null);
  const [lessons, setLessons] = useState<LessonMeta[]>([]);
  const [active, setActive] = useState<Lesson | null>(null);
  const [loadingLesson, setLoadingLesson] = useState(false);
  const [done, setDone] = useState<string[]>([]);

  useEffect(() => {
    try {
      setDone(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"));
    } catch {
      setDone([]);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    api<LearnStatus>("/api/learn/status", { token }).then(setStatus).catch(() => {});
    api<{ lessons: LessonMeta[] }>("/api/learn/lessons", { token })
      .then((r) => setLessons(r.lessons))
      .catch(() => {});
  }, [token]);

  const openLesson = async (slug: string) => {
    if (!token) return;
    setLoadingLesson(true);
    try {
      const lesson = await api<Lesson>(`/api/learn/lessons/${slug}`, { token });
      setActive(lesson);
    } catch {
      /* ignore */
    } finally {
      setLoadingLesson(false);
    }
  };

  const toggleDone = (slug: string) => {
    setDone((prev) => {
      const next = prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug];
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const progress = lessons.length ? Math.round((done.filter((s) => lessons.some((l) => l.slug === s)).length / lessons.length) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">ORQEVA Academy</h1>
          <p className="text-sm text-text-secondary mt-1">
            Learn trading from the methodologies behind the engines — with an AI Instructor at your side.
          </p>
        </div>
        <Badge variant={status?.configured ? "green" : "yellow"} dot>
          {status?.configured ? "INSTRUCTOR LIVE" : "GUIDED MODE"}
        </Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="flex items-center justify-between">
          <div>
            <p className="text-xs text-text-muted uppercase tracking-wider">Progress</p>
            <p className="text-2xl font-bold mt-1">{progress}%</p>
            <p className="text-xs text-text-muted mt-1">
              {done.filter((s) => lessons.some((l) => l.slug === s)).length}/{lessons.length || status?.lessons || 0} lessons
            </p>
          </div>
          <div className="w-14 h-14 rounded-full grid place-items-center border-2 border-green/40 text-green text-sm font-bold">
            {progress}%
          </div>
        </Card>
        <Link href="/learn/glossary">
          <Card className="h-full hover:border-border-light transition-colors">
            <p className="text-xs text-text-muted uppercase tracking-wider">Reference</p>
            <p className="font-semibold mt-1">Glossary</p>
            <p className="text-xs text-text-secondary mt-1">
              {status?.glossary_terms ?? 40} trading terms, plain English →
            </p>
          </Card>
        </Link>
        <Link href="/learn/quiz">
          <Card className="h-full hover:border-border-light transition-colors">
            <p className="text-xs text-text-muted uppercase tracking-wider">Test yourself</p>
            <p className="font-semibold mt-1">Final Exam</p>
            <p className="text-xs text-text-secondary mt-1">All lessons, one score →</p>
          </Card>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-5">
        <aside className="space-y-2">
          {lessons.length === 0 && <p className="text-sm text-text-muted">Loading lessons…</p>}
          {lessons.map((l) => (
            <button
              key={l.slug}
              onClick={() => openLesson(l.slug)}
              className={clsx(
                "w-full text-left rounded-xl border px-3.5 py-3 transition-colors",
                active?.slug === l.slug
                  ? "border-green/50 bg-bg-tertiary"
                  : "border-border bg-bg-secondary hover:border-border-light"
              )}
            >
              <div className="flex items-center gap-2">
                {done.includes(l.slug) && <span className="text-green text-xs">✓</span>}
                <span className="text-sm font-medium leading-snug">{l.title}</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Badge variant={levelVariant(l.level)}>{l.level}</Badge>
                <span className="text-[11px] text-text-muted">{l.minutes} min</span>
              </div>
            </button>
          ))}
        </aside>

        <div className="space-y-5">
          {loadingLesson && <Card><p className="text-sm text-text-muted">Loading lesson…</p></Card>}

          {!active && !loadingLesson && (
            <Card>
              <CardHeader>
                <CardTitle>Start here</CardTitle>
              </CardHeader>
              <p className="text-sm text-text-secondary">
                Pick a lesson on the left. Each one teaches a public methodology and shows how
                ORQEVA&apos;s engines express the same idea in live signals. Ask the Instructor below
                anything you get stuck on.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4">
                {["market-structure-bos-choch", "risk-and-position-sizing", "trend-following", "reading-orqeva-signals"].map(
                  (slug) => {
                    const meta = lessons.find((l) => l.slug === slug);
                    if (!meta) return null;
                    return (
                      <button
                        key={slug}
                        onClick={() => openLesson(slug)}
                        className="text-left text-sm rounded-lg border border-border bg-bg-tertiary hover:border-border-light px-3 py-2.5 transition-colors"
                      >
                        {meta.title}
                      </button>
                    );
                  }
                )}
              </div>
            </Card>
          )}

          {active && !loadingLesson && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold">{active.title}</h2>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={levelVariant(active.level)}>{active.level}</Badge>
                    <Badge variant="gray">{active.category}</Badge>
                    <span className="text-xs text-text-muted">{active.minutes} min read</span>
                  </div>
                </div>
                <Button
                  variant={done.includes(active.slug) ? "secondary" : "primary"}
                  size="sm"
                  onClick={() => toggleDone(active.slug)}
                >
                  {done.includes(active.slug) ? "✓ Completed" : "Mark complete"}
                </Button>
              </div>

              <p className="text-sm text-text-secondary mt-4">{active.summary}</p>

              {active.objectives?.length > 0 && (
                <div className="mt-4 bg-bg-tertiary rounded-lg p-4">
                  <p className="text-xs text-text-muted uppercase mb-2">You&apos;ll learn to</p>
                  <ul className="space-y-1">
                    {active.objectives.map((o, i) => (
                      <li key={i} className="text-sm flex gap-2">
                        <span className="text-green">→</span>
                        <span>{o}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-6 space-y-6">
                {active.sections?.map((sec, i) => (
                  <div key={i}>
                    <h3 className="font-semibold text-base mb-2">{sec.heading}</h3>
                    <div className="space-y-2">
                      {sec.body?.map((p, j) => (
                        <p key={j} className="text-sm text-text-secondary leading-relaxed">
                          {p}
                        </p>
                      ))}
                    </div>
                    {sec.bullets && sec.bullets.length > 0 && (
                      <ul className="mt-3 space-y-1.5">
                        {sec.bullets.map((b, j) => (
                          <li key={j} className="text-sm flex gap-2">
                            <span className="text-green mt-0.5">•</span>
                            <span className="text-text-secondary">{b}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>

              {active.takeaways?.length > 0 && (
                <div className="mt-6 rounded-lg border border-green/30 bg-green-dim p-4">
                  <p className="text-xs text-green uppercase mb-2">Key takeaways</p>
                  <ul className="space-y-1.5">
                    {active.takeaways.map((t, i) => (
                      <li key={i} className="text-sm flex gap-2">
                        <span className="text-green">✓</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {active.quiz?.length > 0 && (
                <div className="mt-6">
                  <h3 className="font-semibold text-base mb-3">Check your understanding</h3>
                  <Quiz questions={active.quiz} />
                </div>
              )}
            </Card>
          )}

          <InstructorChat />
        </div>
      </div>

      <p className="text-xs text-text-muted">
        Educational content only — not financial advice. Trading involves substantial risk of loss.
      </p>
    </div>
  );
}
