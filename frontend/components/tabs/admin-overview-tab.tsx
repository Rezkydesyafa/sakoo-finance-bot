"use client";

import Link from "next/link";

export function AdminOverviewTab() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6F6F6F]">Sakoo Admin</p>
        <h1 className="text-3xl font-semibold text-[#1a1c1b] mt-2">Admin Dashboard</h1>
        <p className="text-sm text-[#6F6F6F] mt-2">
          Kelola konfigurasi sistem yang hanya tersedia untuk administrator.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/?tab=llm-providers"
          className="bg-white rounded-[28px] p-6 card-shadow transition-transform hover:-translate-y-1"
        >
          <div className="w-12 h-12 rounded-2xl bg-[#c7ff00] text-[#151f00] flex items-center justify-center mb-5">
            <span className="material-symbols-outlined">neurology</span>
          </div>
          <h2 className="text-lg font-semibold text-[#1a1c1b]">LLM Providers</h2>
          <p className="text-sm text-[#6F6F6F] mt-2">
            Atur gateway, model, API key terenkripsi, status aktif, dan urutan fallback.
          </p>
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#4e6700] mt-5">
            Buka pengaturan <span className="material-symbols-outlined text-base">arrow_forward</span>
          </span>
        </Link>
      </div>
    </div>
  );
}
