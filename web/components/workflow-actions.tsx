"use client";

import { useState } from "react";
import Link from "next/link";
import { BadgeCheck, CornerUpLeft, Pencil, Send } from "lucide-react";
import { Button, ErrorNote, Input, buttonVariants } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";
import type { ContentItem, WorkflowAction } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

/** Creator -> Reviewer -> Approver. Buttons appear only for the role and state that allow them. */
export function WorkflowActions({
  item,
  onAction,
}: {
  item: ContentItem;
  onAction: (a: WorkflowAction, reason?: string) => Promise<void>;
}) {
  const { user } = useAuth();
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;

  const open = item.findings.filter((f) => !f.response).length;
  const isAuthor = user.id === item.author_id;
  const run = async (a: WorkflowAction, r?: string) => {
    setBusy(true);
    setError(null);
    try {
      await onAction(a, r);
      setAsking(false);
      setReason("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const canEdit = isAuthor && ["draft", "changes_requested", "needs_rereview"].includes(item.state);
  const canSubmit = isAuthor && user.role === "creator" && ["draft", "changes_requested"].includes(item.state);
  const canForward = user.role === "reviewer" && item.state === "in_review";
  const canReturn =
    (user.role === "reviewer" && item.state === "in_review") || (user.role === "approver" && item.state === "awaiting_approval");
  const canApprove = user.role === "approver" && item.state === "awaiting_approval";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {canEdit && (
          <Link href={`/editor?id=${item.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
            <Pencil className="h-3.5 w-3.5" /> Edit
          </Link>
        )}
        {canSubmit && (
          <Button size="sm" disabled={busy || open > 0} onClick={() => run("submit")} title={open ? "Respond to everything flagged first" : undefined}>
            <Send className="h-3.5 w-3.5" /> Send for review {open > 0 && `(${open} left to answer)`}
          </Button>
        )}
        {canForward && (
          <Button size="sm" disabled={busy} onClick={() => run("forward")}>
            <Send className="h-3.5 w-3.5" /> Send to approver
          </Button>
        )}
        {canReturn && !asking && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setAsking(true)}>
            <CornerUpLeft className="h-3.5 w-3.5" /> Ask for changes
          </Button>
        )}
        {canApprove && (
          <Button size="sm" disabled={busy} onClick={() => run("approve")}>
            <BadgeCheck className="h-3.5 w-3.5" /> Approve
          </Button>
        )}
      </div>
      {asking && (
        <div className="flex flex-wrap gap-2">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What should they change?" className="max-w-sm" />
          <Button size="sm" disabled={busy || reason.trim().length < 5} onClick={() => run("request_changes", reason.trim())}>
            Send back
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>
            Cancel
          </Button>
        </div>
      )}
      <ErrorNote message={error} />
    </div>
  );
}
