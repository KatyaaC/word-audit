"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, Input } from "@/components/ui/primitives";
import { contrastRatio } from "@/lib/layer-a";
import type { ColourPair } from "@/lib/types";

/** Colour pairs used by the content (button, headline, body). Layer A checks their contrast. */
export function ColourPairs({ pairs, onChange }: { pairs: ColourPair[]; onChange: (p: ColourPair[]) => void }) {
  const update = (i: number, patch: Partial<ColourPair>) => onChange(pairs.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  return (
    <div className="space-y-2">
      {pairs.map((p, i) => {
        const ratio = contrastRatio(p.foreground, p.background);
        const need = p.large_text ? 3 : 4.5;
        const pass = ratio !== null && ratio >= need;
        return (
          <div key={i} className="flex flex-wrap items-center gap-2 rounded-md border border-stone-200 p-2">
            <Input className="h-8 w-40" value={p.element} onChange={(e) => update(i, { element: e.target.value })} aria-label="Element name" />
            <label className="flex items-center gap-1 text-xs text-stone-600">
              Text
              <input type="color" value={p.foreground} onChange={(e) => update(i, { foreground: e.target.value })} className="h-7 w-9 cursor-pointer rounded border" />
            </label>
            <label className="flex items-center gap-1 text-xs text-stone-600">
              Background
              <input type="color" value={p.background} onChange={(e) => update(i, { background: e.target.value })} className="h-7 w-9 cursor-pointer rounded border" />
            </label>
            <label className="flex items-center gap-1 text-xs text-stone-600">
              <input type="checkbox" checked={p.large_text} onChange={(e) => update(i, { large_text: e.target.checked })} />
              Large text
            </label>
            <span className="rounded px-2 py-1 text-xs font-medium" style={{ color: p.foreground, background: p.background }}>
              Sample
            </span>
            <span className={`text-xs font-medium ${pass ? "text-emerald-700" : "text-red-700"}`}>
              {ratio === null ? "invalid" : `${ratio.toFixed(2)}:1 · ${pass ? "easy to read" : `too faint (needs ${need}:1)`}`}
            </span>
            <Button type="button" variant="ghost" size="icon" aria-label="Remove pair" onClick={() => onChange(pairs.filter((_, j) => j !== i))}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        );
      })}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...pairs, { element: "Headline", foreground: "#1c1917", background: "#ffffff", large_text: true }])}
      >
        <Plus className="h-4 w-4" /> Add a colour pair
      </Button>
    </div>
  );
}
