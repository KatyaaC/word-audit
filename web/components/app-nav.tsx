"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileText, LayoutDashboard, LogOut, PenLine, ScrollText, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL, type Role } from "@/lib/types";
import { Button } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const ALL: Role[] = ["creator", "reviewer", "approver", "brand_manager"];

const NAV: { href: string; label: string; icon: typeof FileText; roles: Role[] }[] = [
  { href: "/content", label: "Content", icon: FileText, roles: ALL },
  { href: "/editor", label: "New draft", icon: PenLine, roles: ["creator"] },
  { href: "/insights", label: "Insights", icon: LayoutDashboard, roles: ["reviewer", "approver", "brand_manager"] },
  { href: "/constitution", label: "Brand rules", icon: ScrollText, roles: ALL },
];

export function AppNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  if (!user) return null;

  return (
    <header className="sticky top-0 z-20 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link href="/content" className="flex items-center gap-2 font-semibold">
          <ShieldCheck className="h-5 w-5 text-emerald-700" />
          WordAudit
        </Link>
        <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
          {NAV.filter((n) => n.roles.includes(user.role)).map((n) => {
            const active = pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm",
                  active ? "bg-stone-100 font-medium text-stone-900" : "text-stone-600 hover:text-stone-900",
                )}
              >
                <n.icon className="h-4 w-4" />
                {n.label}
              </Link>
            );
          })}
        </nav>
        
        <div className="hidden text-right text-sm sm:block">
          <div className="font-medium leading-tight">{user.name}</div>
          <div className="text-xs text-stone-500">{ROLE_LABEL[user.role]}</div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          onClick={() => {
            logout();
            router.replace("/login");
          }}
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
