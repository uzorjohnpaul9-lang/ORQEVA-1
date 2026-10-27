"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { supabase } from "@/lib/supabase";

function ResetForm() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [hasSession, setHasSession] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords don't match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      const { error: err } = await supabase.auth.updateUser({ password });
      if (err) throw err;
      await supabase.auth.signOut().catch(() => {});
      router.push("/login?reset=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setHasSession(Boolean(session));
      setReady(true);
    });
  }, []);

  if (!ready) {
    return (
      <Card>
        <div className="space-y-4 text-center py-4">
          <p className="text-sm text-text-secondary">Loading...</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      {!hasSession ? (
        <div className="space-y-4 text-center py-4">
          <p className="text-sm text-text-secondary">
            This link is missing its reset token. Request a fresh one.
          </p>
          <Link href="/forgot" className="text-green hover:underline text-sm">
            Request new link
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red/10 border border-red/30 rounded-lg px-4 py-3 text-sm text-red">{error}</div>
          )}
          <Input
            label="New password"
            type="password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Input
            label="Confirm password"
            type="password"
            placeholder="Repeat it"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Updating..." : "Set new password"}
          </Button>
        </form>
      )}
    </Card>
  );
}

export default function ResetPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-green/20 flex items-center justify-center mx-auto mb-4">
            <span className="text-green font-bold text-xl">O</span>
          </div>
          <h1 className="text-2xl font-bold">Choose a new password</h1>
          <p className="text-sm text-text-secondary mt-1">ORQEVA account recovery</p>
        </div>
        <Suspense fallback={<Card><p className="text-sm text-text-muted">Loading...</p></Card>}>
          <ResetForm />
        </Suspense>
        <div className="mt-6 text-center text-sm text-text-secondary">
          Remembered it?{" "}
          <Link href="/login" className="text-green hover:underline">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
