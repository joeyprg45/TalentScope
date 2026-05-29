"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  FileText,
  Home,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "ホーム", icon: Home },
  { href: "/members", label: "メンバー", icon: Users },
  { href: "/projects", label: "プロジェクト", icon: Briefcase },
  { href: "/reports", label: "レポート", icon: FileText },
];

export function Sidebar() {
  const path = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-card">
      <div className="border-b p-4">
        <h1 className="text-lg font-bold">🎯 TalentScope</h1>
        <p className="text-xs text-muted-foreground">AI HR Assistant</p>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            path === href || (href !== "/" && path?.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground/80 hover:bg-muted",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
