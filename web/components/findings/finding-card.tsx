"use client";

import { useState } from "react";
import { Check, Pencil, ShieldCheck, X } from "lucide-react";
import { Badge, Button, ErrorNote, Input, Textarea } from "@/components/ui/primitives";
import { ClaimStatusBadge, FindingStatusBadge, SeverityBadge, SourceBadge } from "@/components/labels";
import type { Decision, Finding } from "@/lib/types";
import { cn, errorMessage, formatDate } from "@/lib/utils";

const MIN_REASON = 5;

interface Props {
  finding: Finding;
  active: boolean;
  canRespond: boolean;
  onSelect: () => void;
  onRespond: (decision: Decision, reason: string, modified?: string) => Promise<void>;
}

const DECISION_STYLE: Record<Decision, { label: string; v: "success" | "warning" | "high" }> = {
  accepted: { label: "Accepted", v: "success" },
  modified: { label: "Edited", v: "warning" },
  rejected: { label: "Rejected", v: "high" },
};

/** One finding: its source, status, explanation, suggested fix, and the creator's accept / modify / reject. */
export function FindingCard({ finding: f, active, canRespond, onSelect, onRespond }: Props) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");
  const [modified, setModified] = useState(f.suggestion ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonOk = reason.trim().length >= MIN_REASON;
  const modifiedOk = decision !== "modified" || modified.trim().length > 0;

  async function submit() {
    if (!decision) return;
    setBusy(true);
    setError(null);
    try {
      await onRespond(decision, reason.trim(), decision === "modified" ? modified.trim() : undefined);
      setDecision(null);
      setReason("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      onClick={onSelect}
      className={cn(
        "rounded-lg border bg-white p-4 text-sm transition-colors",
        active ? "border-stone-900 shadow-sm" : "border-stone-200 hover:border-stone-400",
        f.response && "opacity-80",
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <SeverityBadge severity={f.severity} />
        <SourceBadge finding={f} />
        <FindingStatusBadge finding={f} />
        {f.claim_status && <ClaimStatusBadge status={f.claim_status} />}
        <span className="ml-auto font-mono text-xs text-stone-500">{f.rule_id ?? f.fact_id ?? f.kind}</span>
      </div>

      <p className="font-medium">{f.message}</p>
      <p className="mt-1 text-stone-600">{f.explanation}</p>
      {f.target && <p className="mt-1 text-xs text-stone-500">Applies to: {f.target}</p>}

      {f.suggestion !== null && f.suggestion !== undefined && f.fix_type !== "advice" && (
        <div className="mt-3 rounded-md bg-emerald-50 p-2.5">
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-emerald-900">
            Try this instead
            {f.suggestion_verified && (
              <Badge variant="success">
                <ShieldCheck className="h-3 w-3" /> We re-checked this fix
              </Badge>
            )}
          </div>
          <p className="text-emerald-950">
            {f.matched_text && (
              <>
                <span className="diff-del">{f.matched_text}</span> →{" "}
              </>
            )}
            <span className="diff-ins">{f.suggestion === "" ? "(remove)" : f.suggestion}</span>
          </p>
        </div>
      )}
      {f.fix_type === "advice" && f.suggestion && <p className="mt-2 text-xs text-stone-600">{f.suggestion}</p>}

      {f.response ? (
        <div className="mt-3 rounded-md border border-stone-200 bg-stone-50 p-2.5 text-xs">
          <Badge variant={DECISION_STYLE[f.response.decision].v}>{DECISION_STYLE[f.response.decision].label}</Badge>{" "}
          by {f.response.by}, {formatDate(f.response.at)}
          <p className="mt-1 text-stone-700">“{f.response.reason}”</p>
          {f.response.modified_text && <p className="mt-1 text-stone-700">Changed to: “{f.response.modified_text}”</p>}
        </div>
      ) : canRespond ? (
        <div className="mt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant={decision === "accepted" ? "default" : "outline"} onClick={() => setDecision("accepted")}>
              <Check className="h-3.5 w-3.5" /> Accept
            </Button>
            <Button size="sm" variant={decision === "modified" ? "default" : "outline"} onClick={() => setDecision("modified")}>
              <Pencil className="h-3.5 w-3.5" /> Edit
            </Button>
            <Button size="sm" variant={decision === "rejected" ? "destructive" : "outline"} onClick={() => setDecision("rejected")}>
              <X className="h-3.5 w-3.5" /> Reject
            </Button>
          </div>
          {decision && (
            <>
              {decision === "modified" && (
                <Input value={modified} onChange={(e) => setModified(e.target.value)} placeholder="How would you word it?" aria-label="Modified text" />
              )}
              <Textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  decision === "rejected"
                    ? "Why doesn't this apply? The reviewer will see your note."
                    : "A quick note on why. The reviewer will see it."
                }
                aria-label="Reason"
                className="min-h-16"
              />
              <div className="flex items-center gap-2">
                <Button size="sm" disabled={!reasonOk || !modifiedOk || busy} onClick={submit}>
                  {busy ? "Saving…" : "Save"}
                </Button>
                {!reasonOk && <span className="text-xs text-stone-500">Add a short note first.</span>}
              </div>
              <ErrorNote message={error} />
            </>
          )}
        </div>
      ) : null}
    </article>
  );
}
