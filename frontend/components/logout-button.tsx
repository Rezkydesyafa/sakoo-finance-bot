"use client";

import { useRouter } from "next/navigation";
import { clearAuthToken } from "@/lib/auth-storage";

export function LogoutButton() {
  const router = useRouter();

  function handleLogout() {
    clearAuthToken();
    router.replace("/login");
    router.refresh();
  }

  return (
    <button
      className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
      onClick={handleLogout}
      type="button"
    >
      Keluar
    </button>
  );
}
