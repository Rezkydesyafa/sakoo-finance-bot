import { ConnectedBots } from "@/components/connected-bots";

import { useRouter } from "next/navigation";

export function IntegrationsTab() {
  const router = useRouter();

  return (
    <div className="flex-1 flex flex-col h-[100dvh] lg:h-[calc(100vh-32px)] bg-[#f9f9f7] relative overflow-hidden">
      {/* Top AppBar (Mobile Only) */}
      <header className="md:hidden flex-none bg-[#f9f9f7] z-20 px-4 py-4 flex items-center sticky top-0">
        <button 
          onClick={() => router.push("/?tab=overview")}
          className="flex items-center justify-center w-8 h-8 text-[#1a1c1b] mr-3 active:scale-95 transition-transform cursor-pointer border-none bg-transparent"
        >
          <span className="material-symbols-outlined text-[20px]">arrow_back</span>
        </button>
        <h1 className="font-bold text-[18px] text-[#1a1c1b] tracking-tight">Bot Channels</h1>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-8 animate-fade-in">
          {/* Desktop Hero Header */}
          <section className="hidden md:flex flex-col gap-2 mb-2">
            <h1 className="text-[32px] font-bold text-[#1a1c1b] leading-tight tracking-tight">Bot Channels</h1>
            <p className="text-sm text-[#6F6F6F]">Manage your smart assistant integrations.</p>
          </section>

          <ConnectedBots />
        </div>
      </div>
    </div>
  );
}
