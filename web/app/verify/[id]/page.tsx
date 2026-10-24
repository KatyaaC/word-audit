"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote } from "@/components/ui/primitives";
import { PassportStatusBadge } from "@/components/labels";
import { api, USE_MOCKS } from "@/lib/api";
import type { Passport, VerifyResult } from "@/lib/types";
import { errorMessage, formatDate, shortHash } from "@/lib/utils";

/** Public page opened from the Passport QR code. No sign-in needed. */
export default function VerifyPage() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<Passport | null>(null);
  const [r, setR] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getPassport(id), api.verifyPassport(id)])
      .then(([pp, rr]) => {
        setP(pp);
        setR(rr);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [id]);

  const ok = r && r.signature_valid && r.fingerprint_match;

  return (
    <main className="mx-auto max-w-xl p-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle>Is this the approved version?</CardTitle>
          <CardDescription>WordAudit · {id}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {error && (
            <>
              <ErrorNote message={error} />
              {USE_MOCKS && (
                <p className="text-xs text-stone-500">
                  Mock mode keeps data in one browser. Open this link on the device that created the Passport, or run with the backend.
                </p>
              )}
            </>
          )}
          {p && r && (
            <>
              <div className={`flex items-start gap-3 rounded-md border p-3 ${ok ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
                {ok ? <ShieldCheck className="h-6 w-6 text-emerald-700" /> : <ShieldAlert className="h-6 w-6 text-red-700" />}
                <div>
                  <p className="font-semibold">{ok ? "Yes, this is the approved version" : "No, this doesn’t match what was approved"}</p>
                  <p className="text-stone-600">
                    “{p.content_title}”, version {p.content_version}, approved by {p.approved_by}.
                  </p>
                </div>
              </div>
              <PassportStatusBadge status={p.current_status} />
              {p.current_status_reason && <p className="text-red-700">{p.current_status_reason}</p>}
              <dl className="grid grid-cols-[130px_1fr] gap-y-1.5">
                <dt className="text-stone-500">Approved as of</dt>
                <dd>{formatDate(p.compliant_as_of)}</dd>
                <dt className="text-stone-500">Brand rules</dt>
                <dd>{p.guideline_version}</dd>
                <dt className="text-stone-500">Fingerprint</dt>
                <dd className="font-mono text-xs">{shortHash(p.fingerprint, 32)}</dd>
                <dt className="text-stone-500">Checked at</dt>
                <dd>{formatDate(r.checked_at)}</dd>
              </dl>
              <p className="text-xs text-stone-500">
                A Passport shows whether content has been changed since approval. It records an internal brand review. It isn’t legal
                advice or a guarantee of regulatory compliance.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
