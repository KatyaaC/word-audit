import type { StrengthLadder } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Claim strength meter for one Layer C ladder.
 * The green marker is what the evidence supports; the draft marker turns red when the draft says more.
 */
export function StrengthMeter({ ladder }: { ladder: StrengthLadder }) {
  const over = ladder.draft_index - ladder.ledger_index;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-stone-700">{ladder.name}</span>
        <span className={cn("font-medium", over > 0 ? "text-red-700" : "text-emerald-700")}>
          {over > 0 ? `Says ${over} step${over > 1 ? "s" : ""} more than the evidence` : over < 0 ? "More careful than the evidence (that's fine)" : "Matches the evidence"}
        </span>
      </div>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${ladder.steps.length}, minmax(0, 1fr))` }}>
        {ladder.steps.map((step, i) => {
          const isLedger = i === ladder.ledger_index;
          const isDraft = i === ladder.draft_index;
          const inOver = i > ladder.ledger_index && i <= ladder.draft_index;
          return (
            <div key={step} className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "h-2.5 w-full rounded-full",
                  i <= ladder.ledger_index ? "bg-emerald-500" : inOver ? "bg-red-400" : "bg-stone-200",
                )}
              />
              <span className={cn("text-center text-[11px] leading-tight", isDraft || isLedger ? "font-semibold text-stone-900" : "text-stone-500")}>
                {step}
              </span>
              <div className="flex gap-1">
                {isLedger && <span className="rounded bg-emerald-100 px-1 text-[10px] text-emerald-800">evidence</span>}
                {isDraft && (
                  <span className={cn("rounded px-1 text-[10px]", over > 0 ? "bg-red-100 text-red-800" : "bg-stone-200 text-stone-700")}>
                    draft
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
