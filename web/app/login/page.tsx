"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote, Input, Label } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";
import { DEMO_PASSWORD, DEMO_USERS } from "@/lib/mock-store";
import { ROLE_LABEL } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

export default function LoginPage() {
  const { login, user, ready } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState(DEMO_USERS[0].email);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && user) router.replace("/content");
  }, [ready, user, router]);

  async function signIn(e?: React.FormEvent, as?: string) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(as ?? email, as ? DEMO_PASSWORD : password);
      router.replace("/content");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 text-lg font-semibold">
            <ShieldCheck className="h-6 w-6 text-emerald-700" /> WordAudit
          </div>
          <CardTitle>Welcome back</CardTitle>
          <CardDescription>Catch risky wording and unsupported claims before they go live.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <form onSubmit={signIn} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
            <ErrorNote message={error} />
          </form>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-stone-500">Or jump in as… (password {DEMO_PASSWORD})</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_USERS.map((u) => (
                <Button key={u.id} variant="outline" size="sm" disabled={busy} onClick={() => signIn(undefined, u.email)}>
                  {ROLE_LABEL[u.role]}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
