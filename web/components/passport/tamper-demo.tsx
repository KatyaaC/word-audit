"use client";

import { useEffect, useState } from "react";
import { RotateCcw, ShieldAlert, ShieldCheck } from "lucide-react";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { fingerprint } from "@/lib/canonical";
import type { Passport, VerifyResult } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

/**
 * Tamper-detection demo. Edit the approved text and verify: the SHA-256 fingerprint
 * changes, so verification fails. Whitespace-only edits still pass because both
 * sides canonicalise the text first.
 */
export function TamperDemo({ passport }: { passport: Passport }) {
  const [text, setText] = useState(passport.canonical_text);
  const [liveHash, setLiveHash] = useState(passport.fingerprint);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fingerprint(text).then((h) => !cancelled && setLiveHash(h));
    return () => {
      cancelled = true;
    };
  }, [text]);

  const changed = liveHash !== passport.fingerprint;

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.verifyPassport(passport.id, text));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const ok = result && result.signature_valid && result.fingerprint_match;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Has it been changed?</CardTitle>
        <CardDescription>Try it: change a single word in the approved text below, then press Check.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-28 font-mono text-xs" aria-label="Approved text" />
        <div className="grid gap-1 text-xs">
          <div>
            <span className="text-stone-500">Approved fingerprint: </span>
            <code className="break-all">{passport.fingerprint}</code>
          </div>
          <div>
            <span className="text-stone-500">This text’s fingerprint: </span>
            <code className={`break-all ${changed ? "text-red-700" : "text-emerald-700"}`}>{liveHash}</code>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={verify} disabled={busy}>
            {busy ? "Checking…" : "Check"}
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setText(passport.canonical_text);
              setResult(null);
            }}
          >
            <RotateCcw className="h-4 w-4" /> Put it back
          </Button>
        </div>
        <ErrorNote message={error} />
        {result && (
          <div
            className={`flex items-start gap-3 rounded-md border p-3 text-sm ${
              ok ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900"
            }`}
          >
            {ok ? <ShieldCheck className="mt-0.5 h-5 w-5" /> : <ShieldAlert className="mt-0.5 h-5 w-5" />}
            <div>
              <p className="font-semibold">{ok ? "Matches. This is exactly what was approved." : "Doesn’t match. This text has changed since it was approved."}</p>
              <p>Signature {result.signature_valid ? "is genuine" : "is not genuine"} · fingerprint {result.fingerprint_match ? "matches" : "is different"}</p>
              {ok && result.current_status !== "valid" && (
                <p className="mt-1">The text is unchanged, but a fact it relies on has changed since, so it needs another look.</p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
