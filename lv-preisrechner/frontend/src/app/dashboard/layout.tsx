"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  FileStack,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Settings,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api, clearToken, hasToken, User } from "@/lib/api";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Übersicht", icon: LayoutDashboard },
  { href: "/dashboard/preislisten", label: "Preislisten", icon: FileStack },
  {
    href: "/dashboard/pricing",
    label: "Lieferanten-Preise",
    icon: Package,
    beta: true,
  },
  { href: "/dashboard/lvs", label: "Leistungsverzeichnisse", icon: FolderOpen },
  { href: "/dashboard/einstellungen", label: "Einstellungen", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

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

  // Schließe Mobile-Menü bei Navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

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
      {/* Mobile Top-Bar */}
      <header className="fixed top-0 inset-x-0 h-14 bg-white border-b border-slate-200 flex items-center justify-between px-4 md:hidden z-30">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold text-sm">
            LC
          </div>
          <span className="font-semibold text-slate-900 text-sm">LV-Preisrechner</span>
        </Link>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Menü schließen" : "Menü öffnen"}
          className="w-11 h-11 grid place-items-center rounded-lg hover:bg-slate-100"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </header>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <button
          aria-label="Menü-Hintergrund"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
        />
      )}

      {/* Sidebar (Desktop: fixed; Mobile: drawer) */}
      <aside
        className={cn(
          "fixed md:sticky top-0 left-0 h-screen w-64 bg-white border-r border-slate-200 flex flex-col z-50",
          "transition-transform duration-200",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
      >
        <Link href="/" className="hidden md:flex items-center gap-2 px-6 h-16 border-b border-slate-200">
          <div className="w-8 h-8 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold text-sm">
            LC
          </div>
          <span className="font-semibold text-slate-900 text-sm">LV-Preisrechner</span>
        </Link>

        <div className="md:hidden h-14 flex items-center justify-end px-4 border-b border-slate-200">
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Menü schließen"
            className="w-10 h-10 grid place-items-center rounded-lg hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV.map(({ href, label, icon: Icon, beta }) => {
            const active =
              pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 min-h-[44px] rounded-lg text-sm transition-colors",
                  active
                    ? "bg-bauplan-50 text-bauplan-700 font-medium"
                    : "text-slate-700 hover:bg-slate-100",
                )}
              >
                <Icon className="w-5 h-5 shrink-0" />
                <span className="flex-1 truncate">{label}</span>
                {beta && (
                  <span className="text-[10px] uppercase font-semibold tracking-wide px-1.5 py-0.5 rounded bg-accent-500/10 text-accent-600 border border-accent-500/20">
                    Beta
                  </span>
                )}
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
            className="w-full mt-1 flex items-center gap-3 px-3 min-h-[44px] text-sm rounded-lg text-slate-700 hover:bg-slate-100"
          >
            <LogOut className="w-5 h-5 shrink-0" />
            Abmelden
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto pt-14 md:pt-0">
        <div className="max-w-6xl mx-auto px-4 py-6 md:px-8 md:py-8">{children}</div>
      </main>
    </div>
  );
}
