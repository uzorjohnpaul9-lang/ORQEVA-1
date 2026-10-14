"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/Card";
import { Quiz, type QuizQuestion } from "@/components/learn/Quiz";

export default function QuizPage() {
  const { token } = useAuth();
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!token) return;
    api<{ questions: QuizQuestion[] }>("/api/learn/quiz", { token })
      .then((r) => setQuestions(r.questions))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Final Exam</h1>
          <p className="text-sm text-text-secondary mt-1">
            Every lesson&apos;s quiz in one place. Answer all, then submit for your score.
          </p>
        </div>
        <Link href="/learn" className="text-sm text-green hover:underline">
          ← Back to Academy
        </Link>
      </div>

      {!loaded && <Card><p className="text-sm text-text-muted">Loading questions…</p></Card>}
      {loaded && <Quiz questions={questions} />}

      <p className="text-xs text-text-muted">
        Educational content only — not financial advice.
      </p>
    </div>
  );
}
