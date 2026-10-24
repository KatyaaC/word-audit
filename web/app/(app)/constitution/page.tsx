"use client";

import { useEffect, useRef, useState } from "react";
import { Check, FileUp, Lock, X } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorNote,
  Input,
  Label,
  NativeSelect,
} from "@/components/ui/primitives";
import { SeverityBadge } from "@/components/labels";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Classification, Constitution, Rule } from "@/lib/types";
import { errorMessage, formatDate } from "@/lib/utils";

const ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function RuleCard({ rule, canDecide, onDecide }: { rule: Rule; canDecide: boolean; onDecide: (d: "approve" | "reject", reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (d: "approve" | "reject") => {
    setBusy(true);
    setError(null);
    try {
      await onDecide(d, reason.trim());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-md border border-stone-200 p-3 text-sm">
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-stone-500">{rule.id}</span>
        <span className="font-medium">{rule.title}</span>
        <SeverityBadge severity={rule.severity} />
        <Badge variant="outline">{rule.kind.replace("_", " ")}</Badge>
        {rule.status === "draft" && <Badge variant="warning">Waiting for approval</Badge>}
        {rule.status === "active" && <Badge variant="success">Live</Badge>}
        {rule.status === "rejected" && <Badge variant="high">Rejected</Badge>}
        {rule.drafted_by === "software" && <Badge variant="violet">Suggested automatically</Badge>}
      </div>
      <blockquote className="my-2 border-l-2 border-stone-300 pl-3 text-stone-600">
        “{rule.source_passage}”
        <span className="block text-xs text-stone-500">
          {rule.source_doc}
          {rule.source_page ? `, page ${rule.source_page}` : ""} · owner {rule.owner} · v{rule.version}
        </span>
      </blockquote>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded bg-emerald-50 p-2 text-xs">
          <div className="font-medium text-emerald-900">OK to say</div>
          {rule.pass_examples.map((x) => (
            <div key={x}>{x}</div>
          ))}
        </div>
        <div className="rounded bg-red-50 p-2 text-xs">
          <div className="font-medium text-red-900">Not OK</div>
          {rule.fail_examples.map((x) => (
            <div key={x}>{x}</div>
          ))}
        </div>
      </div>
      {rule.decision_reason && <p className="mt-2 text-xs text-stone-600">Note: {rule.decision_reason}</p>}
      {rule.decided_by && <p className="mt-1 text-xs text-stone-500">Decided by {rule.decided_by}</p>}
      {canDecide && rule.status === "draft" && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Add a note (optional)" className="h-8 max-w-xs" />
          <Button size="sm" disabled={busy} onClick={() => decide("approve")}>
            <Check className="h-3.5 w-3.5" /> Approve
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => decide("reject")}>
            <X className="h-3.5 w-3.5" /> Reject
          </Button>
        </div>
      )}
      <ErrorNote message={error} />
    </div>
  );
}

export default function ConstitutionPage() {
  const { user } = useAuth();
  const [data, setData] = useState<Constitution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [classification, setClassification] = useState<Classification>("internal");
  const [uploading, setUploading] = useState(false);
  const [onlyDrafts, setOnlyDrafts] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getConstitution().then(setData).catch((e) => setError(errorMessage(e)));
  }, []);

  const isManager = user?.role === "brand_manager";

  async function upload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadConstitution(file, classification);
      setData(await api.getConstitution());
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setUploading(false);
    }
  }

  if (!data) return error ? <ErrorNote message={error} /> : <p className="text-sm text-stone-500">Loading…</p>;
  const drafts = data.documents.flatMap((d) => d.rules).filter((r) => r.status === "draft").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-xl font-semibold">Brand rules</h1>
          <p className="text-sm text-stone-500">
            Version {data.version} · {drafts} new rule{drafts === 1 ? "" : "s"} waiting for your OK
          </p>
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyDrafts} onChange={(e) => setOnlyDrafts(e.target.checked)} /> Only show new rules
        </label>
      </div>

      {isManager ? (
        <Card>
          <CardHeader>
            <CardTitle>Add your brand guidelines</CardTitle>
            <CardDescription>Upload a PDF or Word file. We'll suggest rules from it, and none of them go live until you approve them.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="file">File</Label>
              <input
                id="file"
                ref={fileInput}
                type="file"
                accept={ACCEPT}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block text-sm file:mr-3 file:rounded-md file:border-0 file:bg-stone-200 file:px-3 file:py-1.5 file:text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cls">Classification</Label>
              <NativeSelect id="cls" value={classification} onChange={(e) => setClassification(e.target.value as Classification)}>
                <option value="public">Public</option>
                <option value="internal">Internal</option>
                <option value="restricted">Restricted</option>
              </NativeSelect>
            </div>
            <Button onClick={upload} disabled={!file || uploading}>
              <FileUp className="h-4 w-4" /> {uploading ? "Reading your guidelines…" : "Upload"}
            </Button>
            {classification === "restricted" && (
              <p className="flex w-full items-center gap-1.5 text-xs text-stone-600">
                <Lock className="h-3.5 w-3.5" /> Restricted files are read only by our in-house model. They never leave the system.
              </p>
            )}
          </CardContent>
        </Card>
      ) : (
        <p className="rounded-md bg-stone-100 p-3 text-sm text-stone-600">You can browse the rules here. Only the Brand Manager can add or approve them.</p>
      )}
      <ErrorNote message={error} />

      {data.documents.map((doc) => {
        const rules = doc.rules.filter((r) => !onlyDrafts || r.status === "draft");
        if (onlyDrafts && rules.length === 0) return null;
        return (
          <Card key={doc.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>{doc.filename}</CardTitle>
                <Badge variant={doc.classification === "restricted" ? "high" : "muted"}>{doc.classification}</Badge>
              </div>
              <CardDescription>
                Uploaded by {doc.uploaded_by} on {formatDate(doc.uploaded_at)} · {doc.rules.length} rules
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {rules.map((r) => (
                <RuleCard
                  key={r.id}
                  rule={r}
                  canDecide={isManager}
                  onDecide={async (d, reason) => setData(await api.decideRule(r.id, d, reason))}
                />
              ))}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
