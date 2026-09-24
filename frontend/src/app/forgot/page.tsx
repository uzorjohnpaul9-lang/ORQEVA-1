"use client";

import { useState } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { API_BASE } from "@/lib/api";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await fetch(`${API_BASE}/api/auth/forgot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch {
      setError("Something went wrong - try again");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-green/20 flex items-center justify-center mx-auto mb-4">
            <span className="text-green font-bold text-xl">O</span>
          </div>
          <h1 className="text-2xl font-bold">Reset your password</h1>
          <p className="text-sm text-text-secondary mt-1">We&apos;ll send you a reset link</p>
        </div>

        <Card>
          {sent ? (
            <div className="space-y-4 text-center py-4">
              <p className="text-sm text-text-primary">
                If an account exists for <b>{email}</b>, a reset link is on its way
                (email — or your ORQEVA notifications / Telegram if email isn&apos;t configured).
              </p>
              <Link href="/login" className="text-green hover:underline text-sm">
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="bg-red/10 border border-red/30 rounded-lg px-4 py-3 text-sm text-red">{error}</div>
              )}
              <Input
                label="Email"
                type="email"
                placeholder="trader@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Sending..." : "Send reset link"}
              </Button>
              <div className="text-center">
                <Link href="/login" className="text-xs text-text-secondary hover:text-green">
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
