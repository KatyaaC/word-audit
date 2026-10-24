"use client";

import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { SeverityBadge } from "@/components/labels";
import type { Finding } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  findings: Finding[];
  activeId: string | null;
  onSelect: (f: Finding) => void;
  onApply: (f: Finding) => void;
}

/** Sidebar list of live Layer A findings while writing. Applying a suggestion is always the creator's click. */
export function LiveFindings({ findings, activeId, onSelect, onApply }: Props) {
  if (findings.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
        <CheckCircle2 className="h-4 w-4" /> Looking good. Nothing to flag so far.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {findings.map((f) => (
        <li
          key={f.id}
          className={cn(
            "cursor-pointer rounded-md border p-3 text-sm transition-colors",
            f.id === activeId ? "border-stone-900 bg-stone-50" : "border-stone-200 hover:border-stone-400",
          )}
          onClick={() => onSelect(f)}
        >
          <div className="mb-1 flex items-center gap-2">
            <SeverityBadge severity={f.severity} />
            <span className="font-mono text-xs text-stone-500">{f.rule_id}</span>
          </div>
          <p className="font-medium">{f.message}</p>
          {f.id === activeId && <p className="mt-1 text-stone-600">{f.explanation}</p>}
          {f.fix_type === "replace" && f.span && f.suggestion !== null && f.suggestion !== undefined && (
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={(e) => {
                e.stopPropagation();
                onApply(f);
              }}
            >
              {f.suggestion === "" ? "Remove" : `Use "${f.suggestion}"`}
            </Button>
          )}
          {f.fix_type === "insert" && f.suggestion && (
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={(e) => {
                e.stopPropagation();
                onApply(f);
              }}
            >
              Add it for me
            </Button>
          )}
          {f.fix_type === "advice" && f.suggestion && <p className="mt-1 text-xs text-stone-500">{f.suggestion}</p>}
        </li>
      ))}
    </ul>
  );
}
