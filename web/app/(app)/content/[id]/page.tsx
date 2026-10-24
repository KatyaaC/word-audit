"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { BadgeCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, ErrorNote, Tabs, buttonVariants } from "@/components/ui/primitives";
import { StateBadge } from "@/components/labels";
import { FindingsPanel } from "@/components/findings/findings-panel";
import { HighlightedText } from "@/components/findings/highlighted-text";
import { ClaimDiffView } from "@/components/claims/claim-diff";
import { VersionCompare } from "@/components/versions/version-compare";
import { AuditLog, CommentsPanel } from "@/components/comments-panel";
import { WorkflowActions } from "@/components/workflow-actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ContentItem } from "@/lib/types";
import { errorMessage, formatDate } from "@/lib/utils";

type Tab = "findings" | "claims" | "versions" | "comments";

export default function ContentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [item, setItem] = useState<ContentItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("findings");
  const [active, setActive] = useState<string | null>(null);

  const load = useCallback(() => {
    api.getContent(id).then(setItem).catch((e) => setError(errorMessage(e)));
  }, [id]);
  useEffect(load, [load]);

  if (error && !item) return <ErrorNote message={error} />;
  if (!item || !user) return <p className="text-sm text-stone-500">Loading…</p>;

  const latest = item.versions[item.versions.length - 1];
  const canRespond = user.id === item.author_id && ["draft", "changes_requested"].includes(item.state);
  const open = item.findings.filter((f) => !f.response).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{item.title}</h1>
            <StateBadge state={item.state} />
          </div>
          <p className="text-sm text-stone-500">
            Version {latest.version} by {item.author_name}, {formatDate(latest.created_at)} · checked against brand rules{" "}
            {latest.rule_pack_version}
          </p>
        </div>
        {item.passport_id && (
          <Link href={`/passport/${item.passport_id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
            <BadgeCheck className="h-4 w-4 text-emerald-700" /> View Passport
          </Link>
        )}
      </div>

      <WorkflowActions
        item={item}
        onAction={async (a, r) => {
          setItem(await api.transition(item.id, a, r));
        }}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card className="lg:sticky lg:top-20 lg:self-start">
          <CardHeader>
            <CardTitle>Version {latest.version}</CardTitle>
          </CardHeader>
          <CardContent>
            <HighlightedText
              text={latest.text}
              findings={item.findings}
              activeId={active}
              onSelect={(fid) => {
                setActive(fid);
                setTab("findings");
              }}
            />
            {canRespond && open > 0 && (
              <p className="mt-4 rounded-md bg-amber-50 p-2 text-xs text-amber-900">
                Go through each item and accept, edit or reject it with a short note. Nothing in your text changes unless you choose to.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { value: "findings", label: `To review (${item.findings.length})` },
              { value: "claims", label: `Claims (${item.claims.length})` },
              { value: "versions", label: `Versions (${item.versions.length})` },
              { value: "comments", label: `Comments (${item.comments.length})` },
            ]}
          />
          {tab === "findings" && (
            <FindingsPanel
              findings={item.findings}
              activeId={active}
              canRespond={canRespond}
              onSelect={setActive}
              onRespond={async (fid, decision, reason, modified) => {
                setItem(await api.respondToFinding(item.id, fid, { decision, reason, modified_text: modified ?? null }));
              }}
            />
          )}
          {tab === "claims" && <ClaimDiffView claims={item.claims} />}
          {tab === "versions" && <VersionCompare versions={item.versions} />}
          {tab === "comments" && (
            <div className="space-y-6">
              <CommentsPanel comments={item.comments} onAdd={async (b) => setItem(await api.addComment(item.id, b))} />
              <div>
                <h3 className="mb-2 text-sm font-semibold">History</h3>
                <AuditLog events={item.audit} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
