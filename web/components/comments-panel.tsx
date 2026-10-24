"use client";

import { useState } from "react";
import { Button, ErrorNote, Textarea } from "@/components/ui/primitives";
import { ROLE_LABEL, type AuditEvent, type Comment } from "@/lib/types";
import { errorMessage, formatDate } from "@/lib/utils";

export function CommentsPanel({ comments, onAdd }: { comments: Comment[]; onAdd: (body: string) => Promise<void> }) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {comments.length === 0 && <p className="text-sm text-stone-500">No comments yet. Start the conversation.</p>}
      {comments.map((c) => (
        <div key={c.id} className="rounded-md border border-stone-200 bg-white p-3 text-sm">
          <div className="mb-1 text-xs text-stone-500">
            <span className="font-medium text-stone-800">{c.author}</span> · {ROLE_LABEL[c.role]} · {formatDate(c.at)}
          </div>
          <p className="whitespace-pre-wrap">{c.body}</p>
        </div>
      ))}
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Leave a note for the team" aria-label="New comment" />
      <Button
        size="sm"
        disabled={!body.trim() || busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await onAdd(body.trim());
            setBody("");
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        Post comment
      </Button>
      <ErrorNote message={error} />
    </div>
  );
}

export function AuditLog({ events }: { events: AuditEvent[] }) {
  return (
    <ol className="space-y-1.5 border-l border-stone-200 pl-4 text-sm">
      {[...events].reverse().map((e, i) => (
        <li key={i}>
          <span className="text-xs text-stone-500">{formatDate(e.at)}</span> · <span className="font-medium">{e.actor}</span> {e.action}
          {e.detail && <span className="text-stone-600">: {e.detail}</span>}
        </li>
      ))}
    </ol>
  );
}
