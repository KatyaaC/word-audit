"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ErrorNote } from "@/components/ui/primitives";
import { PassportCard } from "@/components/passport/passport-card";
import { TamperDemo } from "@/components/passport/tamper-demo";
import { api } from "@/lib/api";
import type { Passport } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

export default function PassportPage() {
  const { id } = useParams<{ id: string }>();
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPassport(id).then(setPassport).catch((e) => setError(errorMessage(e)));
  }, [id]);

  if (error) return <ErrorNote message={error} />;
  if (!passport) return <p className="text-sm text-stone-500">Loading…</p>;

  return (
    <div className="space-y-5">
      <Link href={`/content/${passport.content_id}`} className="text-sm text-emerald-800 hover:underline">
        ← Back to {passport.content_title}
      </Link>
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <PassportCard passport={passport} />
        <TamperDemo passport={passport} />
      </div>
    </div>
  );
}
