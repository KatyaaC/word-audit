"use client";

import type { Finding } from "@/lib/types";

/** Read-only view of the content with finding spans highlighted. Clicking a highlight selects the finding. */
export function HighlightedText({
  text,
  findings,
  activeId,
  onSelect,
}: {
  text: string;
  findings: Finding[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  const spans = findings
    .filter((f) => f.span && f.span.end > f.span.start)
    .sort((a, b) => a.span!.start - b.span!.start);

  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const f of spans) {
    const { start, end } = f.span!;
    if (start < cursor) continue; // overlapping span: the earlier one wins
    if (start > cursor) parts.push(text.slice(cursor, start));
    parts.push(
      <mark
        key={f.id}
        onClick={() => onSelect(f.id)}
        title={f.message}
        className={`bg-transparent la-${f.severity}${f.id === activeId ? " la-active" : ""}`}
      >
        {text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  }
  parts.push(text.slice(cursor));

  return <div className="whitespace-pre-wrap leading-7">{parts}</div>;
}
