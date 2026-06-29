"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { LogoutButton } from "@/components/logout-button";

const navigationItems = [
  { label: "Ringkasan", href: "/?tab=overview", id: "overview" },
  { label: "Transaksi", href: "/?tab=transactions", id: "transactions" },
  { label: "Laporan", href: "/?tab=reports", id: "reports" },
  { label: "Integrasi", href: "/?tab=integrations", id: "integrations" },
];

function DashboardShellContent({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab") || "overview";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col lg:flex-row">
      {/* Sidebar - Widescreen */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-[#0b3d2e] bg-[#062A1F] text-slate-100 lg:block z-20 shadow-lg">
        <div className="flex h-full flex-col">
          {/* Logo / Header */}
          <div className="border-b border-[#0b3d2e] px-6 py-6 flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-[#A1F02D] flex items-center justify-center font-semibold text-[#062A1F] shadow-md animate-pulse-glow">
              S
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#A1F02D]">
                Sakoo
              </p>
              <p className="text-base font-semibold text-white leading-tight">
                Finance Assistant
              </p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex flex-1 flex-col gap-1.5 px-4 py-6">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Menu Utama
            </p>
            {navigationItems.map((item) => {
              const isActive = currentTab === item.id;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`flex items-center px-4 py-3 text-sm font-medium rounded-xl transition duration-150 ${
                    isActive
                      ? "bg-[#A1F02D] text-[#062A1F] font-semibold shadow-md"
                      : "text-slate-300 hover:bg-[#0a382a] hover:text-white"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* User Workspace Info */}
          <div className="border-t border-[#0b3d2e] bg-[#041d15] px-6 py-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#A1F02D]">
                Workspace
              </p>
              <p className="text-sm font-semibold text-white">
                Local MVP
              </p>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[#A1F02D]/10 text-[#A1F02D] border border-[#A1F02D]/20">
              Active
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen">
        {/* Header */}
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur-md px-4 py-4 sm:px-6 lg:px-8 shadow-sm">
          <div className="mx-auto flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#A1F02D] animate-pulse" />
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Dashboard
                </p>
              </div>
              <h1 className="mt-0.5 text-lg font-semibold text-slate-900 tracking-tight">
                Personal Finance Bot
              </h1>
            </div>

            {/* Profile & Logout */}
            <div className="flex items-center gap-4">
              <div className="hidden sm:block text-right">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#062A1F]">
                  Production
                </p>
                <p className="text-xs text-slate-500 font-medium">
                  Ready
                </p>
              </div>
              <div className="border-l border-slate-200 pl-4">
                <LogoutButton />
              </div>
            </div>
          </div>

          {/* Navigation - Mobile Screen */}
          <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 mt-3 pt-2 lg:hidden no-scrollbar">
            {navigationItems.map((item) => {
              const isActive = currentTab === item.id;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`whitespace-nowrap px-3 py-1.5 text-xs font-semibold rounded-lg transition duration-150 ${
                    isActive
                      ? "bg-[#062A1F] text-white"
                      : "text-slate-600 hover:text-[#062A1F] hover:bg-slate-100"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-[#062A1F] flex items-center justify-center font-semibold text-[#A1F02D] animate-spin">
            S
          </div>
          <p className="text-sm font-semibold text-slate-500">Memuat Sakoo...</p>
        </div>
      </div>
    }>
      <DashboardShellContent>{children}</DashboardShellContent>
    </Suspense>
  );
}


