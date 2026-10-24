"use client";

import { useMemo, useState } from "react";
import { NativeSelect } from "@/components/ui/primitives";
import type { Decision, Finding, FindingLayer } from "@/lib/types";
import { FindingCard } from "./finding-card";

interface Props {
  findings: Finding[];
  activeId: string | null;
  canRespond: boolean;
  onSelect: (id: string) => void;
  onRespond: (findingId: string, decision: Decision, reason: string, modified?: string) => Promise<void>;
}

export function FindingsPanel({ findings, activeId, canRespond, onSelect, onRespond }: Props) {
  const [layer, setLayer] = useState<"all" | FindingLayer>("all");
  const [show, setShow] = useState<"all" | "open">("all");

  const counts = useMemo(() => {
    const c = { A: 0, B: 0, C: 0, open: 0 };
    findings.forEach((f) => {
      c[f.layer] += 1;
      if (!f.response) c.open += 1;
    });
    return c;
  }, [findings]);

  const visible = findings.filter((f) => (layer === "all" || f.layer === layer) && (show === "all" || !f.response));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{findings.length} things to look at</span>
        <span className="text-stone-500">
          · <strong className="text-stone-800">{counts.open} still need a response</strong>
        </span>
        <div className="ml-auto flex gap-2">
          <NativeSelect value={layer} onChange={(e) => setLayer(e.target.value as typeof layer)} aria-label="Filter by layer">
            <option value="all">Everything</option>
            <option value="A">Brand rules</option>
            <option value="B">Claims vs evidence</option>
            <option value="C">Claims that drifted</option>
          </NativeSelect>
          <NativeSelect value={show} onChange={(e) => setShow(e.target.value as typeof show)} aria-label="Filter by response">
            <option value="all">Answered and open</option>
            <option value="open">Still open</option>
          </NativeSelect>
        </div>
      </div>
      {visible.length === 0 && <p className="text-sm text-stone-500">Nothing here with these filters.</p>}
      {visible.map((f) => (
        <FindingCard
          key={f.id}
          finding={f}
          active={f.id === activeId}
          canRespond={canRespond}
          onSelect={() => onSelect(f.id)}
          onRespond={(d, r, m) => onRespond(f.id, d, r, m)}
        />
      ))}
    </div>
  );
}
