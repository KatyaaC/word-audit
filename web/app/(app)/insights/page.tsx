"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote } from "@/components/ui/primitives";
import { ConfusingRulesChart, FindingsTrendChart, RepeatedMistakesChart } from "@/components/insights/charts";
import { ImpactGraph } from "@/components/insights/impact-graph";
import { api } from "@/lib/api";
import type { Insights } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

export default function InsightsPage() {
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.getInsights().then(setData).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorNote message={error} />;
  if (!data) return <p className="text-sm text-stone-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Insights</h1>
        <p className="text-sm text-stone-500">Which mistakes keep coming back, which facts are about to go stale, and which rules people find confusing.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <RepeatedMistakesChart data={data.repeated_mistakes} />
        <FindingsTrendChart data={data.findings_per_week} />
        <ConfusingRulesChart data={data.confusing_rules} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <ImpactGraph
          nodes={data.impact.nodes}
          edges={data.impact.edges}
          onExpire={async (factId) => {
            const res = await api.expireFact(factId);
            load();
            return `${factId} has expired. These now need another look: ${res.flagged_content.join(", ") || "no content"}, and Passports ${
              res.flagged_passports.join(", ") || "none"
            }.`;
          }}
        />
        <Card>
          <CardHeader>
            <CardTitle>Facts going stale soon</CardTitle>
            <CardDescription>Update these before they're out of date</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {data.expiring_facts.length === 0 && <li className="text-stone-500">Nothing expiring soon.</li>}
              {data.expiring_facts.map((f) => (
                <li key={f.fact_id} className="flex items-center justify-between rounded-md border border-stone-200 px-3 py-2">
                  <span className="font-mono text-xs">{f.label}</span>
                  <span className={f.days_left <= 7 ? "font-medium text-red-700" : f.days_left <= 30 ? "text-amber-700" : "text-stone-600"}>
                    {f.days_left} days left
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
