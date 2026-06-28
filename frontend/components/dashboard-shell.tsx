import Link from "next/link";
import type { ReactNode } from "react";
import { LogoutButton } from "@/components/logout-button";

const navigationItems = [
  { label: "Overview", href: "/" },
  { label: "Transaksi", href: "/transactions" },
  { label: "Kategori", href: "/categories" },
  { label: "Laporan", href: "/reports" },
  { label: "Integrasi", href: "/integrations" },
];

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white lg:block">
        <div className="flex h-full flex-col">
          <div className="border-b border-slate-200 px-6 py-5">
            <p className="text-xs font-semibold uppercase text-emerald-700">
              Sakoo
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-950">
              Finance Bot
            </p>
          </div>

          <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
            {navigationItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="border-l-2 border-transparent px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-emerald-500 hover:bg-emerald-50 hover:text-emerald-800"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="border-t border-slate-200 px-6 py-4">
            <p className="text-xs font-medium uppercase text-slate-500">
              Workspace
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-800">
              Local MVP
            </p>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Dashboard
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-950">
                Personal Finance Assistant
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-xs font-medium uppercase text-slate-500">
                  Environment
                </p>
                <p className="mt-1 text-sm font-semibold text-emerald-700">
                  Production Ready
                </p>
              </div>
              <LogoutButton />
            </div>
          </div>

          <nav className="flex gap-1 overflow-x-auto border-t border-slate-200 px-4 py-2 sm:px-6 lg:hidden">
            {navigationItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="whitespace-nowrap border-b-2 border-transparent px-2 py-2 text-sm font-medium text-slate-600 hover:border-emerald-500 hover:text-emerald-800"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
