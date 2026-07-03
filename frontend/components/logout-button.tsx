"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { clearAuthToken } from "@/lib/auth-storage";

export function LogoutButton({ className }: { className?: string }) {
  const router = useRouter();
  const [showModal, setShowModal] = useState(false);

  function handleLogout() {
    clearAuthToken();
    router.replace("/login");
    router.refresh();
  }

  return (
    <>
      <button
        className={className || "rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 cursor-pointer bg-transparent"}
        onClick={() => setShowModal(true)}
        type="button"
      >
        Sign Out
      </button>

      {showModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" style={{ margin: 0 }}>
          <div className="bg-white rounded-3xl p-8 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 mx-auto bg-neutral-100 text-[#1a1c1b]">
              <span className="material-symbols-outlined text-2xl">
                logout
              </span>
            </div>
            
            <h3 className="text-lg font-bold text-center text-[#1a1c1b] mb-2">
              Keluar dari Akun?
            </h3>
            <p className="text-sm text-center text-[#6F6F6F] mb-8">
              Anda harus login kembali untuk mengakses data Anda. Lanjutkan?
            </p>
            
            <div className="flex flex-col gap-3">
              <button onClick={handleLogout} className="w-full py-3 rounded-full text-sm font-bold border-none cursor-pointer transition-colors bg-[#1a1c1b] hover:bg-black text-white">
                Ya, Sign Out
              </button>
              <button onClick={() => setShowModal(false)} className="w-full py-3 bg-white border border-[#E8E8E8] text-[#1a1c1b] rounded-full text-sm font-bold hover:bg-[#F1F2F0] transition-colors cursor-pointer">
                Batal
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
