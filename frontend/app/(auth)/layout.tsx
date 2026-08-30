import type { ReactNode } from "react";
import Link from "next/link";
import { BrandMark } from "@/components/brand-mark";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[#f7f7f0] font-sans text-[#191919]">
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-32 -top-36 h-[32rem] w-[32rem] rounded-full bg-[#c7ff00]/20 blur-[120px]" />
        <div className="absolute -bottom-56 -right-36 h-[34rem] w-[34rem] rounded-full bg-[#202020]/8 blur-[130px]" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#202020]/15 to-transparent" />
      </div>

      <header className="relative z-10 border-b border-[#202020]/8 bg-[#f7f7f0]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-20 w-full max-w-[1440px] items-center justify-between px-5 md:px-8">
          <Link href="/" className="flex items-center gap-2.5 text-xl font-extrabold tracking-tight transition-opacity hover:opacity-70" aria-label="Sakoo home">
            <BrandMark priority className="h-9 w-9 drop-shadow-[0_5px_10px_rgba(0,0,0,0.12)]" />
            <span>Sakoo.</span>
          </Link>
          <Link href="/" className="hidden items-center gap-1.5 text-sm font-bold text-[#6f6f6f] transition-colors hover:text-[#191919] sm:flex">
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            Back to home
          </Link>
        </div>
      </header>

      <main className="relative z-10 flex flex-1 items-center justify-center px-5 py-12 sm:px-8 sm:py-16">
        {children}
      </main>

      <footer className="relative z-10 border-t border-[#202020]/8 px-5 py-5 sm:px-8">
        <div className="mx-auto flex max-w-[1440px] flex-col items-center justify-between gap-2 text-center text-xs font-medium text-[#6f6f6f] sm:flex-row sm:text-left">
          <span>© 2026 Sakoo Finance Bot. Securely encrypted.</span>
          <span className="flex items-center gap-1.5">
            <BrandMark className="h-4 w-4" />
            Personal finance, made simple.
          </span>
        </div>
      </footer>
    </div>
  );
}
