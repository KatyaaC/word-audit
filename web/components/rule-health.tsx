"use client";

import { useState } from "react";
import { HeartPulse, Split, Waves } from "lucide-react";
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { LintResult } from "@/lib/types";
import { errorMessage, formatDate } from "@/lib/utils";

/** Runs the Guideline Linter and lists rules that are vague or contradict each other. */
export function RuleHealth() {
  const [result, setResult] = useState<LintResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.lintRules());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const conflicts = result?.findings.filter((f) => f.kind === "conflict") ?? [];
  const vague = result?.findings.filter((f) => f.kind === "ambiguity") ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-3">
          <HeartPulse className="h-5 w-5 text-emerald-700" />
          <div>
            <CardTitle>Rule health</CardTitle>
            <CardDescription>Find rules that people will read differently, and rules that contradict each other.</CardDescription>
          </div>
          <Button className="ml-auto" size="sm" variant="outline" onClick={run} disabled={busy}>
            {busy ? "Checking rules…" : result ? "Check again" : "Check my rules"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ErrorNote message={error} />
        {result && (
          <>
            <p className="text-sm text-stone-600">
              Checked {result.rules_checked} rules, {formatDate(result.checked_at)}.{" "}
              {result.findings.length === 0
                ? "No vague or conflicting rules found."
                : `${conflicts.length} conflict${conflicts.length === 1 ? "" : "s"} and ${vague.length} vague rule${vague.length === 1 ? "" : "s"}.`}
            </p>
            {[...conflicts, ...vague].map((f, i) => (
              <div key={i} className="rounded-md border border-stone-200 p-3 text-sm">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  {f.kind === "conflict" ? (
                    <Badge variant="high">
                      <Split className="h-3 w-3" /> Rules contradict
                    </Badge>
                  ) : (
                    <Badge variant="warning">
                      <Waves className="h-3 w-3" /> Open to interpretation
                    </Badge>
                  )}
                  {f.rules.map((r) => (
                    <span key={r.key} className="font-mono text-xs text-stone-500">
                      {r.key}
                    </span>
                  ))}
                </div>
                <p>{f.explanation}</p>
                {f.rules.map((r) => r.text && (
                  <blockquote key={r.key} className="mt-1 border-l-2 border-stone-300 pl-3 text-stone-600">
                    “{r.text}”
                  </blockquote>
                ))}
                {f.vague_terms.length > 0 && (
                  <p className="mt-1 text-xs text-stone-500">Vague words: {f.vague_terms.join(", ")}. Try adding examples of what passes and fails.</p>
                )}
              </div>
            ))}
          </>
        )}
      </CardContent>
    </Card>
  );
}
