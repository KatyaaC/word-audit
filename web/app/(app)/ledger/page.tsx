"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ExternalLink, Pencil } from "lucide-react";
import { Badge, Button, Card, CardContent, ErrorNote, Input, Label, NativeSelect } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Fact, FactPatch, FactStatus } from "@/lib/types";
import { cn, errorMessage, formatDate } from "@/lib/utils";

function ExpiryBadge({ fact }: { fact: Fact }) {
  if (fact.status === "expired") return <Badge variant="high">Expired</Badge>;
  if (fact.status === "superseded") return <Badge variant="muted">Replaced</Badge>;
  if (fact.days_left === null) return <Badge variant="success">Live · no expiry</Badge>;
  if (fact.days_left < 0) return <Badge variant="high">Past its expiry date</Badge>;
  if (fact.days_left <= 7) return <Badge variant="high">Expires in {fact.days_left} days</Badge>;
  if (fact.days_left <= 30) return <Badge variant="warning">Expires in {fact.days_left} days</Badge>;
  return <Badge variant="success">Live · {fact.days_left} days left</Badge>;
}

function atRisk(f: Fact): boolean {
  return f.status !== "active" || (f.days_left !== null && f.days_left <= 30);
}

function EditForm({ fact, onSave, onCancel }: { fact: Fact; onSave: (p: FactPatch) => Promise<void>; onCancel: () => void }) {
  const [statement, setStatement] = useState(fact.statement);
  const [value, setValue] = useState(fact.value === null ? "" : String(fact.value));
  const [qualifier, setQualifier] = useState(fact.qualifier ?? "");
  const [scope, setScope] = useState(fact.scope ?? "");
  const [period, setPeriod] = useState(fact.period ?? "");
  const [expires, setExpires] = useState(fact.expires_on ?? "");
  const [status, setStatus] = useState<FactStatus>(fact.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const patch: FactPatch = {};
    if (statement.trim() !== fact.statement) patch.statement = statement.trim();
    const v = value.trim() === "" ? null : Number(value);
    if (v !== null && Number.isNaN(v)) return setError("The value must be a number.");
    if (v !== fact.value) patch.value = v;
    if (qualifier !== (fact.qualifier ?? "")) patch.qualifier = qualifier || null;
    if (scope !== (fact.scope ?? "")) patch.scope = scope || null;
    if (period !== (fact.period ?? "")) patch.period = period || null;
    if (expires !== (fact.expires_on ?? "")) patch.expires_on = expires || null;
    if (status !== fact.status) patch.status = status;
    if (Object.keys(patch).length === 0) return onCancel();
    setBusy(true);
    setError(null);
    try {
      await onSave(patch);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-3 rounded-md border border-stone-200 bg-stone-50 p-3">
      <div className="space-y-1">
        <Label htmlFor={`st-${fact.id}`}>Approved wording</Label>
        <Input id={`st-${fact.id}`} value={statement} onChange={(e) => setStatement(e.target.value)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor={`v-${fact.id}`}>Value{fact.unit ? ` (${fact.unit})` : ""}</Label>
          <Input id={`v-${fact.id}`} value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal" />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`q-${fact.id}`}>Wording limit</Label>
          <Input id={`q-${fact.id}`} value={qualifier} onChange={(e) => setQualifier(e.target.value)} placeholder="e.g. up to" />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`s-${fact.id}`}>Applies to</Label>
          <Input id={`s-${fact.id}`} value={scope} onChange={(e) => setScope(e.target.value)} placeholder="e.g. pilot participants" />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`p-${fact.id}`}>Time period</Label>
          <Input id={`p-${fact.id}`} value={period} onChange={(e) => setPeriod(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`e-${fact.id}`}>Expires on</Label>
          <Input id={`e-${fact.id}`} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`x-${fact.id}`}>Status</Label>
          <NativeSelect id={`x-${fact.id}`} value={status} onChange={(e) => setStatus(e.target.value as FactStatus)} className="w-full">
            <option value="active">Live</option>
            <option value="expired">Expired</option>
            <option value="superseded">Replaced</option>
          </NativeSelect>
        </div>
      </div>
      <p className="text-xs text-stone-500">
        Changing the wording, value, limits, period, expiry or status flags every piece of content and Passport that uses this fact.
      </p>
      <div className="flex gap-2">
        <Button size="sm" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <ErrorNote message={error} />
    </div>
  );
}

export default function LedgerPage() {
  const { user } = useAuth();
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ id: string; text: string } | null>(null);
  const [onlyRisk, setOnlyRisk] = useState(false);

  const load = useCallback(() => {
    api.listFacts().then(setFacts).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  const isManager = user?.role === "brand_manager";

  async function save(fact: Fact, patch: FactPatch) {
    const res = await api.updateFact(fact.id, patch);
    const c = res.flagged_content.length;
    const p = res.flagged_passports.length;
    setNotice({
      id: fact.id,
      text:
        c + p === 0
          ? "Saved. Nothing else needed to change."
          : `Saved. ${c} piece${c === 1 ? "" : "s"} of content and ${p} Passport${p === 1 ? "" : "s"} now need another look.`,
    });
    setEditing(null);
    load();
  }

  if (error) return <ErrorNote message={error} />;
  if (!facts) return <p className="text-sm text-stone-500">Loading…</p>;

  const risky = facts.filter(atRisk);
  const shown = onlyRisk ? risky : facts;
  const exposure = risky.reduce((n, f) => n + f.used_by_content.length, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="text-xl font-semibold">Approved facts</h1>
          <p className="text-sm text-stone-500">
            The facts your content is allowed to state. When one changes or expires, everything that uses it is flagged automatically.
          </p>
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyRisk} onChange={(e) => setOnlyRisk(e.target.checked)} /> Only show facts at risk
        </label>
      </div>

      {risky.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {risky.length} fact{risky.length === 1 ? " is" : "s are"} expired or expiring within 30 days, used by {exposure} piece
            {exposure === 1 ? "" : "s"} of content. Update the evidence before they go stale.
          </span>
        </div>
      )}

      {shown.length === 0 && <p className="text-sm text-stone-500">Nothing at risk right now.</p>}

      <div className="space-y-3">
        {shown.map((f) => (
          <Card key={f.id} className={cn(f.status === "expired" && "border-red-200")}>
            <CardContent className="pt-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-stone-500">{f.id}</span>
                <ExpiryBadge fact={f} />
                {f.version > 1 && <Badge variant="outline">Version {f.version}</Badge>}
                {isManager && editing !== f.id && (
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setEditing(f.id)}>
                    <Pencil className="h-3.5 w-3.5" /> Edit
                  </Button>
                )}
              </div>
              <p className="mt-2 font-medium">{f.statement}</p>
              <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-stone-500">Value</dt>
                  <dd>
                    {f.qualifier ? `${f.qualifier} ` : ""}
                    {f.value ?? "—"}
                    {f.unit === "%" ? "%" : f.unit ? ` ${f.unit}` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-stone-500">Applies to</dt>
                  <dd>{f.scope || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-stone-500">Period</dt>
                  <dd>{f.period || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-stone-500">Expires</dt>
                  <dd>{f.expires_on ? new Date(f.expires_on).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "—"}</dd>
                </div>
              </dl>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <span className="text-stone-600">
                  Used by {f.used_by_content.length} piece{f.used_by_content.length === 1 ? "" : "s"} of content
                  {f.used_by_passports.length > 0 && ` and ${f.used_by_passports.length} Passport${f.used_by_passports.length === 1 ? "" : "s"}`}
                </span>
                {f.used_by_content.map((cid) => (
                  <Link key={cid} href={`/content/${cid}`} className="text-emerald-800 underline">
                    #{cid}
                  </Link>
                ))}
                {f.evidence_url && (
                  <a href={f.evidence_url} target="_blank" rel="noreferrer" className="ml-auto flex items-center gap-1 text-xs text-stone-500 hover:underline">
                    Evidence <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              {notice?.id === f.id && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-900">{notice.text}</p>}
              {editing === f.id && <EditForm fact={f} onSave={(p) => save(f, p)} onCancel={() => setEditing(null)} />}
              <p className="mt-2 text-xs text-stone-400">Last changed {formatDate(f.updated_at)} · owner {f.owner || "unassigned"}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
