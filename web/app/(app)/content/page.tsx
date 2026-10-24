"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PenLine } from "lucide-react";
import { Card, ErrorNote, Tabs, buttonVariants } from "@/components/ui/primitives";
import { StateBadge } from "@/components/labels";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ContentItem, User } from "@/lib/types";
import { errorMessage, formatDate } from "@/lib/utils";

function needsMyAction(item: ContentItem, user: User): boolean {
  switch (user.role) {
    case "creator":
      return item.author_id === user.id && ["draft", "changes_requested", "needs_rereview"].includes(item.state);
    case "reviewer":
      return item.state === "in_review";
    case "approver":
      return item.state === "awaiting_approval";
    case "brand_manager":
      return item.state === "needs_rereview";
  }
}

export default function ContentListPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ContentItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"mine" | "all">("mine");

  useEffect(() => {
    api.listContent().then(setItems).catch((e) => setError(errorMessage(e)));
  }, []);

  if (!user) return null;
  const shown = (items ?? []).filter((i) => filter === "all" || needsMyAction(i, user));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Content</h1>
        <div className="w-64">
          <Tabs
            value={filter}
            onChange={setFilter}
            items={[
              { value: "mine", label: "Waiting on me" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
        {user.role === "creator" && (
          <Link href="/editor" className={`${buttonVariants()} ml-auto`}>
            <PenLine className="h-4 w-4" /> New draft
          </Link>
        )}
      </div>
      <ErrorNote message={error} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-left text-xs text-stone-500">
            <tr>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">State</th>
              <th className="px-4 py-2 font-medium">To review</th>
              <th className="px-4 py-2 font-medium">Version</th>
              <th className="px-4 py-2 font-medium">Author</th>
              <th className="px-4 py-2 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {items === null && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-stone-500">
                  Loading…
                </td>
              </tr>
            )}
            {items && shown.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-stone-500">
                  You're all caught up. Nothing is waiting on you.
                </td>
              </tr>
            )}
            {shown.map((i) => {
              const open = i.findings.filter((f) => !f.response).length;
              const high = i.findings.filter((f) => !f.response && f.severity === "high").length;
              return (
                <tr key={i.id} className="border-t border-stone-100 hover:bg-stone-50">
                  <td className="px-4 py-2.5">
                    <Link href={`/content/${i.id}`} className="font-medium text-emerald-900 hover:underline">
                      {i.title}
                    </Link>
                    <div className="font-mono text-xs text-stone-500">{i.id}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <StateBadge state={i.state} />
                  </td>
                  <td className="px-4 py-2.5">
                    {open} {high > 0 && <span className="text-xs text-red-700">({high} important)</span>}
                  </td>
                  <td className="px-4 py-2.5">v{i.versions.length}</td>
                  <td className="px-4 py-2.5">{i.author_name}</td>
                  <td className="px-4 py-2.5 text-stone-500">{formatDate(i.updated_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
