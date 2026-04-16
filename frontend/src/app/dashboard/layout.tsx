"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/dashboard/analyse", label: "Bauplan-Analyse", icon: "📐" },
  { href: "/dashboard/preislisten", label: "Preislisten", icon: "💰" },
  { href: "/dashboard/angebote", label: "Angebote", icon: "📋" },
  { href: "/dashboard/projekte", label: "Projekte", icon: "📁" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const currentPage = navItems.find((n) =>
    n.href === "/dashboard"
      ? pathname === "/dashboard"
      : pathname.startsWith(n.href)
  )?.label ?? "Dashboard";

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Mobile Header */}
      <header className="md:hidden flex items-center justify-between bg-gray-900 text-white px-4 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg hover:bg-gray-700 transition-colors"
            aria-label="Menü"
          >
            {sidebarOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
          <h2 className="text-base font-bold">LaneCore AI</h2>
        </div>
        <span className="text-sm text-gray-400">{currentPage}</span>
      </header>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile until toggled */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-50
          w-64 md:w-60 bg-gray-900 text-white flex flex-col
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0
        `}
      >
        <div className="p-6 border-b border-gray-700 hidden md:block">
          <h2 className="text-lg font-bold">LaneCore AI</h2>
          <p className="text-xs text-gray-400 mt-1">Bauunternehmer-Cockpit</p>
        </div>
        {/* Close button for mobile sidebar */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between md:hidden">
          <h2 className="text-base font-bold">Menü</h2>
          <button onClick={() => setSidebarOpen(false)} className="p-1 hover:bg-gray-700 rounded">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const active = item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary-600 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <span className="text-lg">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
          MVP v0.1.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        <header className="h-14 md:h-16 bg-white border-b border-gray-200 items-center px-4 md:px-8 hidden md:flex">
          <h1 className="text-lg font-semibold text-gray-800">{currentPage}</h1>
        </header>
        <div className="p-4 md:p-8">{children}</div>
      </main>
    </div>
  );
}
