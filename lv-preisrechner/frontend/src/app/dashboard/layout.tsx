"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  FileText,
  FileStack,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Settings,
} from "lucide-react";
import { toast } from "sonner";
import { api, clearToken, hasToken, User } from "@/lib/api";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Übersicht", icon: LayoutDashboard },
  { href: "/dashboard/preislisten", label: "Preislisten", icon: FileStack },
  { href: "/dashboard/lvs", label: "Leistungsverzeichnisse", icon: FolderOpen },
  { href: "/dashboard/einstellungen", label: "Einstellungen", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      if (!hasToken()) {
        router.replace("/login");
        return;
      }
      try {
        const me = await api<User>("/auth/me");
        if (active) setUser(me);
      } catch {
        clearToken();
        router.replace("/login");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [router]);

  function logout() {
    clearToken();
    toast.info("Abgemeldet.");
    router.replace("/login");
  }

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-slate-50">
        <div className="text-slate-500">Lade Dashboard…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col">
        <Link href="/" className="flex items-center gap-2 px-6 h-16 border-b border-slate-200">
          <div className="w-8 h-8 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold text-sm">
            LC
          </div>
          <span className="font-semibold text-slate-900 text-sm">LV-Preisrechner</span>
        </Link>

        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                  active
                    ? "bg-bauplan-50 text-bauplan-700 font-medium"
                    : "text-slate-700 hover:bg-slate-100",
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-slate-200">
          <div className="px-3 py-2 text-sm">
            <div className="font-medium text-slate-900 truncate">{user?.firma}</div>
            <div className="text-xs text-slate-500 truncate">{user?.email}</div>
          </div>
          <button
            onClick={logout}
            className="w-full mt-1 flex items-center gap-3 px-3 py-2 text-sm rounded-lg text-slate-700 hover:bg-slate-100"
          >
            <LogOut className="w-4 h-4" />
            Abmelden
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
