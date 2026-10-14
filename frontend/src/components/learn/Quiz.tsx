"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export interface QuizQuestion {
  question: string;
  options: string[];
  answer: number;
  explanation: string;
  lesson?: string;
  slug?: string;
}

export function Quiz({ questions }: { questions: QuizQuestion[] }) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);

  if (questions.length === 0) {
    return <p className="text-sm text-text-muted">No quiz questions available.</p>;
  }

  const score = questions.reduce((acc, q, i) => acc + (answers[i] === q.answer ? 1 : 0), 0);
  const answeredCount = Object.keys(answers).length;
  const pct = Math.round((score / questions.length) * 100);

  const reset = () => {
    setAnswers({});
    setSubmitted(false);
  };

  return (
    <div className="space-y-5">
      {submitted && (
        <Card className={clsx(pct >= 70 ? "border-green/40" : "border-yellow/40")}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Your score</p>
              <p className="text-2xl font-bold mt-1">
                {score}/{questions.length}{" "}
                <span className={pct >= 70 ? "text-green" : "text-yellow"}>({pct}%)</span>
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={reset}>
              Try again
            </Button>
          </div>
          <p className="text-xs text-text-muted mt-3">
            {pct >= 70
              ? "Strong work — you're reading the market like a trader."
              : "Keep going — revisit the lessons, then come back."}
          </p>
        </Card>
      )}

      {questions.map((q, i) => {
        const chosen = answers[i];
        const correct = chosen === q.answer;
        return (
          <Card key={i}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <p className="text-sm font-medium">
                {i + 1}. {q.question}
              </p>
              {q.lesson && (
                <Badge variant="gray">{q.slug ? q.lesson.split(":")[0] : q.lesson}</Badge>
              )}
            </div>
            <div className="space-y-2">
              {q.options.map((opt, oi) => {
                const isChosen = chosen === oi;
                const showState = submitted || isChosen;
                return (
                  <button
                    key={oi}
                    onClick={() => !submitted && setAnswers((a) => ({ ...a, [i]: oi }))}
                    disabled={submitted}
                    className={clsx(
                      "w-full text-left text-sm rounded-lg border px-3.5 py-2.5 transition-colors",
                      !showState && "border-border bg-bg-tertiary hover:border-border-light",
                      showState && oi === q.answer && "border-green/60 bg-green-dim text-green",
                      showState && oi !== q.answer && isChosen && "border-red/60 bg-red-dim text-red",
                      showState && oi !== q.answer && !isChosen && "border-border bg-bg-tertiary opacity-60"
                    )}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
            {(submitted || chosen != null) && (
              <p className={clsx("text-xs mt-3", submitted ? (correct ? "text-green" : "text-text-secondary") : "text-text-muted")}>
                {submitted && !correct ? "Not quite. " : submitted && correct ? "Correct. " : ""}
                {q.explanation}
              </p>
            )}
          </Card>
        );
      })}

      {!submitted && (
        <Button
          onClick={() => setSubmitted(true)}
          disabled={answeredCount < questions.length}
          className="w-full"
        >
          {answeredCount < questions.length
            ? `Answer all ${questions.length} questions (${answeredCount} done)`
            : "Submit answers"}
        </Button>
      )}
    </div>
  );
}
