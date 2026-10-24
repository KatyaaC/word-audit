"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote, Input, Button } from "@/components/ui/primitives";
import { BrandEditor, type EditorHandle, type EditorSnapshot } from "@/components/editor/brand-editor";
import { ColourPairs } from "@/components/editor/colour-pairs";
import { LiveFindings } from "@/components/editor/live-findings";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DEFAULT_RULE_PACK } from "@/lib/layer-a";
import type { ColourPair, Finding } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

const STARTER = `<h2>Close your books faster</h2><p>PaisaLeaf Ledger guarantees 60% faster reconciliation for every customer. Get a free trial today!!</p>`;

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const textToHtml = (t: string) => t.split("\n").map((l) => `<p>${escapeHtml(l)}</p>`).join("");

function EditorPage() {
  const params = useSearchParams();
  const editId = params.get("id");
  const router = useRouter();
  const { user } = useAuth();

  const [title, setTitle] = useState("");
  const [initialHtml, setInitialHtml] = useState<string | null>(editId ? null : STARTER);
  const [snap, setSnap] = useState<EditorSnapshot>({ text: "", html: "", images: [] });
  const [findings, setFindings] = useState<Finding[]>([]);
  const [pairs, setPairs] = useState<ColourPair[]>([
    { element: "Primary button", foreground: "#ffffff", background: "#16a34a", large_text: false },
  ]);
  const [active, setActive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<EditorHandle>(null);

  useEffect(() => {
    if (!editId) return;
    api
      .getContent(editId)
      .then((item) => {
        const v = item.versions[item.versions.length - 1];
        setTitle(item.title);
        setInitialHtml(v.html || textToHtml(v.text));
      })
      .catch((e) => setError(errorMessage(e)));
  }, [editId]);

  const onChange = useCallback((s: EditorSnapshot, f: Finding[]) => {
    setSnap(s);
    setFindings(f);
  }, []);

  function select(f: Finding) {
    setActive(f.id);
    if (f.span) editorRef.current?.focusSpan(f.span);
  }

  function apply(f: Finding) {
    if (f.fix_type === "replace" && f.span && f.suggestion !== null && f.suggestion !== undefined) {
      editorRef.current?.replaceSpan(f.span, f.suggestion);
    } else if (f.fix_type === "insert" && f.suggestion) {
      editorRef.current?.appendText(f.suggestion);
    }
    setActive(null);
  }

  async function runFullReview() {
    setBusy(true);
    setError(null);
    try {
      const sub = { title: title.trim() || "Untitled draft", text: snap.text, html: snap.html, colour_pairs: pairs, images: snap.images };
      const item = editId ? await api.saveVersion(editId, sub) : await api.createContent(sub);
      router.push(`/content/${item.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  if (user?.role !== "creator") {
    return <p className="text-sm text-stone-600">Drafts are written by creators. Sign in as the Creator to try the editor.</p>;
  }

  const high = findings.filter((f) => f.severity === "high").length;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Give this piece a title" className="max-w-md text-base" aria-label="Title" />
          <span className="text-xs text-stone-500">Brand rules {DEFAULT_RULE_PACK.version}</span>
          <Button className="ml-auto" onClick={runFullReview} disabled={busy || !snap.text.trim()}>
            {busy ? "Checking your claims…" : editId ? "Save and check again" : "Check"}
          </Button>
        </div>
        <ErrorNote message={error} />
        {initialHtml === null ? (
          <p className="text-sm text-stone-500">Opening your draft…</p>
        ) : (
          <BrandEditor
            ref={editorRef}
            initialHtml={initialHtml}
            colourPairs={pairs}
            activeFindingId={active}
            onChange={onChange}
            onFindingClick={(id) => setActive(id)}
          />
        )}
        <Card>
          <CardHeader>
            <CardTitle>Colours in this piece</CardTitle>
            <CardDescription>Add each text and background colour pair, and we'll tell you if it's easy enough to read.</CardDescription>
          </CardHeader>
          <CardContent>
            <ColourPairs pairs={pairs} onChange={setPairs} />
          </CardContent>
        </Card>
      </div>

      <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
        <div>
          <h2 className="font-semibold">As you write</h2>
          <p className="text-xs text-stone-500">
            We check wording, tone, contrast and image descriptions as you type
            {findings.length > 0 && <> ({findings.length} to look at{high ? `, ${high} important` : ""})</>}. Your claims get checked against
            the evidence when you click “Check everything”.
          </p>
        </div>
        <div className="max-h-[70vh] overflow-y-auto pr-1">
          <LiveFindings findings={findings} activeId={active} onSelect={select} onApply={apply} />
        </div>
      </aside>
    </div>
  );
}

export default function EditorRoute() {
  return (
    <Suspense fallback={<p className="text-sm text-stone-500">Loading editor…</p>}>
      <EditorPage />
    </Suspense>
  );
}
