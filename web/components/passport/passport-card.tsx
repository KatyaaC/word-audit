"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/primitives";
import { PassportStatusBadge } from "@/components/labels";
import type { Passport } from "@/lib/types";
import { formatDate, shortHash } from "@/lib/utils";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 border-t border-stone-100 py-2 text-sm first:border-t-0">
      <dt className="text-stone-500">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

/** The Brand Passport record with its QR verification link. */
export function PassportCard({ passport: p }: { passport: Passport }) {
  const [origin, setOrigin] = useState("");
  useEffect(() => setOrigin(window.location.origin), []);
  const verifyUrl = `${origin}/verify/${p.id}`;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Brand Passport {p.id}</CardTitle>
          <PassportStatusBadge status={p.current_status} />
        </div>
        <CardDescription>
          A signed record of what was approved for “{p.content_title}” (version {p.content_version}), when, and by whom. If even one
          character of the content changes, it won’t verify.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-[1fr_auto]">
        <dl>
          <Row label="Approved as of">{formatDate(p.compliant_as_of)} (this never changes)</Row>
          <Row label="Today">
            {p.current_status === "valid" ? "Still valid" : "Needs another look"}
            {p.current_status_reason && <span className="block text-xs text-red-700">{p.current_status_reason}</span>}
          </Row>
          <Row label="Fingerprint">
            <code className="text-xs" title={p.fingerprint}>
              {p.hash_algorithm} {shortHash(p.fingerprint, 24)}
            </code>
          </Row>
          <Row label="Signature">
            <code className="text-xs" title={p.signature}>
              {p.signature_algorithm} {shortHash(p.signature, 28)}
            </code>
          </Row>
          <Row label="Brand rules version">{p.guideline_version}</Row>
          <Row label="Created by">{p.creator}</Row>
          <Row label="Approved by">
            {p.approved_by} on {formatDate(p.approved_at)} · {p.mode === "strict" ? "a different person from the creator" : "self-approved (Solo mode)"}
          </Row>
          <Row label="How it was checked">{p.automation_disclosure}</Row>
          <Row label="Evidence used">
            {p.evidence.length === 0 ? (
              <span className="text-stone-500">No facts from the ledger were needed.</span>
            ) : (
              <ul className="space-y-1">
                {p.evidence.map((e) => (
                  <li key={e.fact_id}>
                    <span className="font-mono text-xs">{e.fact_id}</span> {e.text}{" "}
                    <span className="text-xs text-stone-500">(expires {new Date(e.expires_at).toLocaleDateString("en-IN")})</span>
                  </li>
                ))}
              </ul>
            )}
          </Row>
        </dl>
        <div className="flex flex-col items-center gap-2">
          <div className="rounded-lg border border-stone-200 bg-white p-3">{origin && <QRCodeSVG value={verifyUrl} size={150} level="M" />}</div>
          <a href={`/verify/${p.id}`} className="text-xs text-emerald-800 underline" target="_blank" rel="noreferrer">
            Anyone can check it here
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
