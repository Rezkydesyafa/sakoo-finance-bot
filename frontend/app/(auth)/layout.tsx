import type { ReactNode } from "react";
import Link from "next/link";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-surface min-h-screen flex flex-col relative font-body-main text-body-main text-text-primary overflow-x-hidden">
      {/* Atmospheric Glow Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute top-0 left-0 w-[600px] h-[600px] bg-glow-blue rounded-full mix-blend-multiply filter blur-[120px] opacity-70 transform -translate-x-1/4 -translate-y-1/4"></div>
        <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-glow-pink rounded-full mix-blend-multiply filter blur-[120px] opacity-60 transform translate-x-1/4 translate-y-1/4"></div>
        <div className="absolute top-1/2 left-1/2 w-[800px] h-[400px] bg-glow-purple rounded-full mix-blend-multiply filter blur-[150px] opacity-50 transform -translate-x-1/2 -translate-y-1/2"></div>
      </div>

      {/* TopAppBar */}
      <header className="bg-surface/80 backdrop-blur-md sticky top-0 full-width bg-transparent z-50">
        <div className="flex justify-between items-center w-full px-outer-margin py-stack-md max-w-container-max mx-auto">
          <Link href="/" className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity active:scale-95">
            <span className="material-symbols-outlined text-primary text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              finance_chip
            </span>
            <h1 className="font-headline-section text-headline-section font-bold text-primary tracking-tight">
              Sakoo Finance
            </h1>
          </Link>
          <div className="flex items-center">
            <button className="hover:opacity-80 active:scale-95 flex items-center justify-center p-2 rounded-full text-secondary hover:bg-surface-muted transition-colors">
              <span className="material-symbols-outlined">help_outline</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Canvas */}
      <main className="flex-grow flex items-center justify-center p-outer-margin relative z-10 w-full max-w-container-max mx-auto">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-transparent w-full z-10 relative mt-auto">
        <div className="flex flex-col md:flex-row justify-between items-center w-full px-outer-margin py-stack-lg gap-stack-md max-w-container-max mx-auto">
          <div className="font-label-muted text-label-muted text-text-muted text-center md:text-left">
            © 2024 Sakoo Finance Bot. Securely encrypted.
          </div>
          <div className="flex flex-wrap justify-center gap-6">
            <a className="font-label-muted text-label-muted text-text-muted hover:text-primary transition-colors opacity-100 hover:opacity-80" href="#">Privacy Policy</a>
            <a className="font-label-muted text-label-muted text-text-muted hover:text-primary transition-colors opacity-100 hover:opacity-80" href="#">Terms of Service</a>
            <a className="font-label-muted text-label-muted text-text-muted hover:text-primary transition-colors opacity-100 hover:opacity-80" href="#">Security</a>
          </div>
          <div className="font-label-button text-label-button text-text-primary opacity-50 flex items-center gap-1 mt-4 md:mt-0">
            <span className="material-symbols-outlined text-[16px]">finance_chip</span>
            Sakoo
          </div>
        </div>
      </footer>
    </div>
  );
}
