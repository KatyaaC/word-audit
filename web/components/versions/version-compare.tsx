"use client";

import { useMemo, useState } from "react";
import DiffMatchPatch from "diff-match-patch";
import { NativeSelect } from "@/components/ui/primitives";
import type { ContentVersion } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const dmp = new DiffMatchPatch();

/** Compare any two versions with an inline word-level diff (diff-match-patch, semantic cleanup). */
export function VersionCompare({ versions }: { versions: ContentVersion[] }) {
  const last = versions.length;
  const [from, setFrom] = useState(Math.max(1, last - 1));
  const [to, setTo] = useState(last);

  const diffs = useMemo(() => {
    const a = versions.find((v) => v.version === from)?.text ?? "";
    const b = versions.find((v) => v.version === to)?.text ?? "";
    const d = dmp.diff_main(a, b);
    dmp.diff_cleanupSemantic(d);
    return d;
  }, [versions, from, to]);

  if (versions.length < 2) return <p className="text-sm text-stone-500">Only one version exists so far.</p>;

  const opts = versions.map((v) => (
    <option key={v.version} value={v.version}>
      v{v.version} · {formatDate(v.created_at)}
    </option>
  ));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        Compare
        <NativeSelect value={from} onChange={(e) => setFrom(Number(e.target.value))} aria-label="From version">
          {opts}
        </NativeSelect>
        with
        <NativeSelect value={to} onChange={(e) => setTo(Number(e.target.value))} aria-label="To version">
          {opts}
        </NativeSelect>
      </div>
      <div className="whitespace-pre-wrap rounded-md border border-stone-200 bg-white p-4 text-sm leading-7">
        {diffs.map(([op, text], i) =>
          op === 1 ? (
            <ins key={i} className="diff-ins">
              {text}
            </ins>
          ) : op === -1 ? (
            <del key={i} className="diff-del">
              {text}
            </del>
          ) : (
            <span key={i}>{text}</span>
          ),
        )}
      </div>
      <p className="text-xs text-stone-500">
        Green text was added, red text was removed. Each version is checked against the rule pack version shown in its history.
      </p>
    </div>
  );
}
