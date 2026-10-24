import { Card, CardContent, CardHeader } from "@/components/ui/primitives";
import { ClaimStatusBadge } from "@/components/labels";
import type { ClaimDiff, ClaimParts } from "@/lib/types";
import { cn } from "@/lib/utils";
import { StrengthMeter } from "./strength-meter";

const FIELDS: { key: keyof ClaimParts; label: string }[] = [
  { key: "metric", label: "What's measured" },
  { key: "value", label: "Value" },
  { key: "population", label: "Applies to" },
  { key: "conditions", label: "Wording" },
  { key: "period", label: "Time period" },
];

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9%]/g, "");

/** Side-by-side Claim Diff: the draft claim next to the closest approved ledger fact, field by field. */
export function ClaimDiffView({ claims }: { claims: ClaimDiff[] }) {
  if (claims.length === 0) return <p className="text-sm text-stone-500">We didn't spot any numbers or factual claims in this version.</p>;

  return (
    <div className="space-y-4">
      {claims.map((c) => (
        <Card key={c.claim_id}>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <ClaimStatusBadge status={c.status} />
              <span className="font-mono text-xs text-stone-500">{c.claim_id}</span>
              {c.ledger_fact_id && <span className="ml-auto font-mono text-xs text-stone-500">Ledger {c.ledger_fact_id}</span>}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-stone-200 p-3">
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-stone-500">Draft says</div>
                <p className="text-sm">“{c.draft_text}”</p>
              </div>
              <div className={cn("rounded-md border p-3", c.ledger_text ? "border-emerald-200 bg-emerald-50/50" : "border-dashed border-orange-300 bg-orange-50/50")}>
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-stone-500">Approved evidence</div>
                <p className="text-sm">{c.ledger_text ?? "We couldn't find an approved fact for this. That doesn't make it false. It just needs a source before it goes out."}</p>
              </div>
            </div>

            {c.ledger && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-stone-500">
                      <th className="py-1 pr-3 font-medium">Field</th>
                      <th className="py-1 pr-3 font-medium">Draft</th>
                      <th className="py-1 font-medium">Ledger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {FIELDS.map(({ key, label }) => {
                      const differs = norm(c.draft[key]) !== norm(c.ledger![key]);
                      return (
                        <tr key={key} className="border-t border-stone-100">
                          <td className="py-1.5 pr-3 text-stone-500">{label}</td>
                          <td className={cn("py-1.5 pr-3", differs && "font-medium text-red-800")}>
                            {differs && <span className="mr-1 rounded bg-red-100 px-1 text-[10px]">differs</span>}
                            {c.draft[key]}
                          </td>
                          <td className="py-1.5">{c.ledger![key]}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {c.ladders.length > 0 && (
              <div className="space-y-4 rounded-md bg-stone-50 p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-stone-500">How strong is the claim?</div>
                {c.ladders.map((l) => (
                  <StrengthMeter key={l.name} ladder={l} />
                ))}
              </div>
            )}

            <p className="text-sm text-stone-600">{c.explanation}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
