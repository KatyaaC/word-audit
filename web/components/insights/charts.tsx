"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/primitives";
import type { Insights } from "@/lib/types";

const AXIS = { fontSize: 12, fill: "#57534e" };

function ChartCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="h-64">{children}</CardContent>
    </Card>
  );
}

export function RepeatedMistakesChart({ data }: { data: Insights["repeated_mistakes"] }) {
  return (
    <ChartCard title="Mistakes that keep coming back" description="How often each rule was flagged">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={AXIS} allowDecimals={false} />
          <YAxis type="category" dataKey="label" tick={AXIS} width={80} />
          <Tooltip />
          <Bar dataKey="count" name="Times flagged" fill="#047857" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function FindingsTrendChart({ data }: { data: Insights["findings_per_week"] }) {
  return (
    <ChartCard title="Are we getting better?" description="Issues flagged each week">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: -16, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={AXIS} />
          <YAxis tick={AXIS} allowDecimals={false} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="layer_a" name="Wording" stroke="#047857" strokeWidth={2} />
          <Line type="monotone" dataKey="layer_b" name="Claims" stroke="#7c3aed" strokeWidth={2} />
          <Line type="monotone" dataKey="layer_c" name="Drift" stroke="#dc2626" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function ConfusingRulesChart({ data }: { data: Insights["confusing_rules"] }) {
  return (
    <ChartCard title="Rules people push back on" description="How often creators reject a rule. A high number usually means the rule needs clearer wording">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -16, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ ...AXIS, fontSize: 11 }} interval={0} />
          <YAxis tick={AXIS} unit="%" domain={[0, 100]} />
          <Tooltip formatter={(v) => `${v}%`} />
          <Bar dataKey="override_rate" name="Rejected" fill="#d97706" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
