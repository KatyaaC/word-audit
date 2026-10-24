"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppNav } from "@/components/app-nav";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);

  if (!ready || !user) return null;
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </>
  );
}
