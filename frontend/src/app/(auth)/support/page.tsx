"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

interface TicketView {
  id: string;
  subject: string;
  message: string;
  category: string;
  status: string;
  reply?: string | null;
  replied_at?: string | null;
  created_at: string;
}

interface TicketCreate {
  subject: string;
  message: string;
  category: string;
  email?: string;
}

export default function SupportPage() {
  const { user, token } = useAuth();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("general");
  const [tickets, setTickets] = useState<TicketView[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      if (user && token) {
        const r = await api<{ tickets: TicketView[] }>("/api/support", { token });
        setTickets(r.tickets);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load tickets");
    }
  };

  useEffect(() => { void load(); }, [user, token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) { setError("Subject and message required"); return; }
    if (!user && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { setError("Valid email required"); return; }
    setSubmitting(true); setError(null); setNotice(null);
    try {
      const body: TicketCreate = { subject, message, category };
      if (!user) body.email = email.trim().toLowerCase();
      await api<TicketView>("/api/support", { method: "POST", token: (user && token) ? token : undefined, body });
      setSubject(""); setMessage(""); setEmail(""); setNotice("Ticket submitted. We'll reply soon.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Support</h1>
        <p className="text-sm text-text-secondary mt-1">Open a ticket or check replies.</p>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <Card>
        <CardHeader><CardTitle>New Ticket</CardTitle></CardHeader>
        <form onSubmit={submit} className="space-y-3">
          {!user && (
            <Input label="Contact email" value={email} onChange={(e)=>setEmail(e.target.value)} placeholder="you@example.com" required />
          )}
          <Input label="Subject" value={subject} onChange={(e)=>setSubject(e.target.value)} placeholder="Brief summary" required />
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Category</label>
            <Select value={category} onChange={(e)=>setCategory(e.target.value)} options={[
              {value:"general",label:"General"},
              {value:"billing",label:"Billing"},
              {value:"technical",label:"Technical"},
              {value:"account",label:"Account"},
              {value:"other",label:"Other"},
            ]} />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm text-text-secondary">Message</label>
            <textarea className="w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none focus:border-green/50 focus:ring-1 focus:ring-green/20 min-h-[140px]" value={message} onChange={(e)=>setMessage(e.target.value)} placeholder="Describe the issue or question..." required />
          </div>
          <Button type="submit" disabled={submitting}>{submitting ? "Submitting..." : "Submit Ticket"}</Button>
        </form>
      </Card>

      {user && (
        <Card padding={false}>
          <div className="px-4 pt-4"><CardTitle>My Tickets</CardTitle></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b border-border/50 text-left text-text-muted">
                  <th className="px-4 py-2">Subject</th>
                  <th className="px-4 py-2">Category</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Reply</th>
                  <th className="px-4 py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {tickets.length===0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-text-muted">No tickets yet.</td></tr>}
                {tickets.map(t=>(
                  <tr key={t.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5 font-medium">{t.subject}</td>
                    <td className="px-4 py-2.5 capitalize">{t.category}</td>
                    <td className="px-4 py-2.5"><Badge variant={t.status==="open"?"yellow":t.status==="in_progress"?"blue":t.status==="resolved"?"green":"gray"}>{t.status}</Badge></td>
                    <td className="px-4 py-2.5 text-xs text-text-secondary truncate max-w-[200px]">{t.reply || "â€”"}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(t.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {!user && (
        <p className="text-sm text-text-secondary">
          Already have an account? <Link href="/login" className="text-green hover:underline">Sign in</Link> to see your replies.
        </p>
      )}
    </div>
  );
}
