"use client";

import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { RichText } from "@/components/learn/RichText";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "Explain market structure like I'm new",
  "What is a liquidity sweep?",
  "How do I size a position?",
  "How should I read a signal's confidence?",
];

export function InstructorChat({ signalId, signalLabel }: { signalId?: string; signalLabel?: string }) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<boolean | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!token) return;
    api<{ configured: boolean }>("/api/learn/status", { token })
      .then((s) => setLive(s.configured))
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const content = text.trim();
    if (!token || !content || busy) return;
    const history = [...messages, { role: "user" as const, content }];
    setMessages(history);
    setInput("");
    setBusy(true);
    try {
      const r = await api<{ reply: string; live: boolean }>("/api/learn/tutor", {
        method: "POST",
        token,
        body: { messages: history },
      });
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
      setLive(r.live);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Sorry — I couldn't reach the instructor. Please try again." }]);
    } finally {
      setBusy(false);
    }
  };

  const explainSignal = async () => {
    if (!token || !signalId || busy) return;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: `Explain the ${signalLabel || "selected"} signal` }]);
    try {
      const r = await api<{ reply: string; live: boolean }>("/api/learn/explain-signal", {
        method: "POST",
        token,
        body: { signal_id: signalId },
      });
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
      setLive(r.live);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "I couldn't load that signal." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex flex-col h-[560px]">
      <CardHeader>
        <CardTitle>AI Instructor</CardTitle>
        <Badge variant={live ? "green" : "yellow"} dot>
          {live ? "LIVE MODEL" : "GUIDED MODE"}
        </Badge>
      </CardHeader>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <div className="text-sm text-text-secondary space-y-3">
            <p>
              Ask anything about trading — I&apos;ll teach it against the public methodologies behind
              ORQEVA&apos;s engines and real signals.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="text-xs bg-bg-tertiary hover:bg-bg-hover border border-border rounded-full px-3 py-1.5 text-text-secondary hover:text-text-primary transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={clsx(
                "max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm",
                m.role === "user" ? "bg-green text-bg-primary" : "bg-bg-tertiary text-text-primary"
              )}
            >
              <RichText text={m.content} className={m.role === "user" ? "leading-relaxed" : "space-y-2 leading-relaxed"} />
            </div>
          </div>
        ))}

        {busy && <div className="text-xs text-text-muted animate-pulse">Instructor is thinking…</div>}
        <div ref={endRef} />
      </div>

      {signalId && (
        <div className="mt-3">
          <Button variant="secondary" size="sm" onClick={explainSignal} disabled={busy}>
            Explain this signal
          </Button>
        </div>
      )}

      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          rows={2}
          placeholder="Ask the instructor… (Enter to send)"
          className="flex-1 resize-none bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-green/50 focus:ring-1 focus:ring-green/20 transition-colors"
        />
        <Button type="submit" disabled={busy || !input.trim()}>
          Send
        </Button>
      </form>
    </Card>
  );
}
