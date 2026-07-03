import { useState } from "react";
import Link from "next/link";

export function IntegrationsTab() {
  // Toggle states
  const [autoCategorization, setAutoCategorization] = useState(true);
  const [dailySummary, setDailySummary] = useState(true);
  const [receiptOcr, setReceiptOcr] = useState(false);
  const [alertThresholds, setAlertThresholds] = useState(false);

  // Reset helper
  const handleReset = () => {
    setAutoCategorization(true);
    setDailySummary(true);
    setReceiptOcr(false);
    setAlertThresholds(false);
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-6xl mx-auto">
      {/* ========================================================================= */}
      {/* 🖥️ DESKTOP VIEW (Visible on lg and above) */}
      {/* ========================================================================= */}
      <div className="hidden lg:block space-y-8">
        {/* Page Header */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-[#1a1c1b] mb-1">Bot Channels</h2>
          <p className="text-sm text-[#6F6F6F]">Manage your smart assistant integrations.</p>
        </div>

        {/* Active Integrations Grid */}
        <div className="grid grid-cols-3 gap-6">
          {/* Telegram Card */}
          <div className="bg-white rounded-[24px] p-6 card-shadow border border-[#E8E8E8] relative overflow-hidden group hover:scale-[1.02] transition-all duration-300">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#0088cc]/5 rounded-bl-full pointer-events-none"></div>
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-[#0088cc]/10 text-[#0088cc] rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-2xl">send</span>
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[#1a1c1b]">Telegram</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="w-2 h-2 rounded-full bg-[#5FCF6A]"></span>
                    <span className="text-[11px] text-[#5FCF6A] font-semibold">Connected</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4 mb-8">
              <div className="flex items-center justify-between text-xs border-b border-[#E8E8E8]/50 pb-2.5">
                <span className="text-[#6F6F6F] font-semibold">Bot ID</span>
                <span className="text-[#1a1c1b] font-bold">@SakooFinanceBot</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6F6F6F] font-semibold">Last Activity</span>
                <span className="text-[#1a1c1b] font-bold">2 mins ago</span>
              </div>
            </div>

            <button type="button" className="w-full py-3 bg-[#F1F2F0] hover:bg-[#E8E8E8] text-xs font-bold text-[#1a1c1b] rounded-full transition-colors border-none cursor-pointer">
              Manage
            </button>
          </div>

          {/* WhatsApp Card */}
          <div className="bg-white rounded-[24px] p-6 card-shadow border border-[#E8E8E8] relative overflow-hidden group hover:scale-[1.02] transition-all duration-300">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#25D366]/5 rounded-bl-full pointer-events-none"></div>
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-[#25D366]/10 text-[#25D366] rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-2xl">chat</span>
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[#1a1c1b]">WhatsApp</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="w-2 h-2 rounded-full bg-[#5FCF6A]"></span>
                    <span className="text-[11px] text-[#5FCF6A] font-semibold">Connected</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4 mb-8">
              <div className="flex items-center justify-between text-xs border-b border-[#E8E8E8]/50 pb-2.5">
                <span className="text-[#6F6F6F] font-semibold">Phone</span>
                <span className="text-[#1a1c1b] font-bold">+62 812-3456-7890</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6F6F6F] font-semibold">Last Activity</span>
                <span className="text-[#1a1c1b] font-bold">1 hr ago</span>
              </div>
            </div>

            <button type="button" className="w-full py-3 bg-[#F1F2F0] hover:bg-[#E8E8E8] text-xs font-bold text-[#1a1c1b] rounded-full transition-colors border-none cursor-pointer">
              Manage
            </button>
          </div>

          {/* Discord Card */}
          <div className="bg-white rounded-[24px] p-6 card-shadow border border-[#E8E8E8] relative overflow-hidden group hover:scale-[1.02] transition-all duration-300">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#5865F2]/5 rounded-bl-full pointer-events-none"></div>
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-neutral-100 text-[#5865F2] rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-2xl">sports_esports</span>
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[#1a1c1b]">Discord</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="w-2 h-2 rounded-full bg-neutral-300"></span>
                    <span className="text-[11px] text-[#6F6F6F] font-semibold">Disconnected</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4 mb-8">
              <div className="flex items-center justify-between text-xs border-b border-[#E8E8E8]/50 pb-2.5">
                <span className="text-[#6F6F6F] font-semibold">Server ID</span>
                <span className="text-[#6F6F6F] italic">--</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6F6F6F] font-semibold">Last Activity</span>
                <span className="text-[#6F6F6F] italic">--</span>
              </div>
            </div>

            <button type="button" className="w-full py-3 bg-[#c7ff00] hover:bg-[#bff500] text-xs font-bold text-[#151f00] rounded-full transition-colors border-none cursor-pointer flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-sm font-bold">add</span> Connect
            </button>
          </div>
        </div>

        {/* Command Settings */}
        <div className="bg-white rounded-[24px] p-6 card-shadow border border-[#E8E8E8] mt-8">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#E8E8E8]">
            <div>
              <h3 className="text-base font-bold text-[#1a1c1b]">Command Settings</h3>
              <p className="text-xs text-[#6F6F6F] mt-1">Configure global bot behavior across all active channels.</p>
            </div>
            <button 
              onClick={handleReset}
              type="button" 
              className="text-xs font-bold text-[#4e6700] hover:text-[#c7ff00] bg-transparent border-none cursor-pointer"
            >
              Reset to Default
            </button>
          </div>

          <div className="space-y-6">
            {/* Auto-categorization */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Auto-categorization</h4>
                <p className="text-xs text-[#6F6F6F] mt-0.5">Automatically assign categories to transactions parsed from chat messages.</p>
              </div>
              <button 
                onClick={() => setAutoCategorization(!autoCategorization)}
                className={`w-11 h-6 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  autoCategorization ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  autoCategorization ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>

            {/* Daily Summary */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Daily Summary</h4>
                <p className="text-xs text-[#6F6F6F] mt-0.5">Receive a concise financial summary every morning at 08:00 AM.</p>
              </div>
              <button 
                onClick={() => setDailySummary(!dailySummary)}
                className={`w-11 h-6 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  dailySummary ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  dailySummary ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>

            {/* Receipt OCR via Chat */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Receipt OCR via Chat</h4>
                <p className="text-xs text-[#6F6F6F] mt-0.5">Allow the bot to read and extract data from receipt images sent in chat.</p>
              </div>
              <button 
                onClick={() => setReceiptOcr(!receiptOcr)}
                className={`w-11 h-6 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  receiptOcr ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  receiptOcr ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 📱 MOBILE VIEW (Visible below lg) */}
      {/* ========================================================================= */}
      <div className="block lg:hidden space-y-6 px-1">
        {/* Mobile Header with back arrow */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/?tab=overview" className="w-8 h-8 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#1a1c1b] no-underline">
            <span className="material-symbols-outlined text-lg">arrow_back</span>
          </Link>
          <h2 className="text-lg font-bold text-[#1a1c1b]">Bot Channels</h2>
        </div>

        {/* Section: Active Integrations */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-[#6F6F6F] px-1 uppercase tracking-wider">Active Integrations</h3>

          {/* Telegram Card (Dark Forest Green/Grey style exactly matching mockup) */}
          <div className="bg-[#20221E] text-white rounded-[24px] p-5 shadow-sm relative overflow-hidden flex items-center justify-between border border-[#3E423A]/30">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/10 text-[#0088cc] rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-xl text-[#c7ff00]">send</span>
              </div>
              <div>
                <h4 className="font-bold text-sm text-white">Telegram</h4>
                <p className="text-[10px] text-neutral-400 mt-0.5">@SakooFinanceBot</p>
              </div>
            </div>
            <span className="text-[10px] bg-[#c7ff00]/25 text-[#c7ff00] font-bold px-3 py-1 rounded-full flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#c7ff00]"></span> Connected
            </span>
          </div>

          {/* WhatsApp Card (Light style exactly matching mockup) */}
          <div className="bg-white text-[#1a1c1b] rounded-[24px] p-5 shadow-sm relative overflow-hidden flex items-center justify-between border border-[#E8E8E8]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-neutral-100 text-[#25D366] rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-xl">chat</span>
              </div>
              <div>
                <h4 className="font-bold text-sm text-[#1a1c1b]">WhatsApp</h4>
                <p className="text-[10px] text-[#6F6F6F] mt-0.5">+62 812-3456-7890</p>
              </div>
            </div>
            <span className="text-[10px] bg-[#5FCF6A]/10 text-[#5FCF6A] font-bold px-3 py-1 rounded-full flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#5FCF6A]"></span> Connected
            </span>
          </div>

          {/* Discord Card (Light style exactly matching mockup) */}
          <div className="bg-white text-[#1a1c1b] rounded-[24px] p-5 shadow-sm relative overflow-hidden flex items-center justify-between border border-[#E8E8E8]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-neutral-100 text-neutral-400 rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-xl">sports_esports</span>
              </div>
              <div>
                <h4 className="font-bold text-sm text-[#1a1c1b]">Discord</h4>
                <p className="text-[10px] text-[#6F6F6F] mt-0.5">Not linked</p>
              </div>
            </div>
            <button type="button" className="text-xs font-bold text-white bg-[#20221E] px-4 py-2 rounded-full border-none cursor-pointer hover:opacity-90">
              Connect
            </button>
          </div>
        </div>

        {/* Section: Bot Features */}
        <div className="space-y-4 pt-2">
          <h3 className="text-xs font-semibold text-[#6F6F6F] px-1 uppercase tracking-wider">Bot Features</h3>

          <div className="bg-white rounded-[24px] p-4 shadow-sm border border-[#E8E8E8] space-y-5">
            {/* Auto-categorization toggle */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Auto-categorization</h4>
                <p className="text-[10px] text-[#6F6F6F] mt-0.5">AI labels new expenses</p>
              </div>
              <button 
                onClick={() => setAutoCategorization(!autoCategorization)}
                className={`w-9 h-5 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  autoCategorization ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  autoCategorization ? "translate-x-4" : "translate-x-0"
                }`} />
              </button>
            </div>

            {/* Daily Summaries toggle */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Daily Summaries</h4>
                <p className="text-[10px] text-[#6F6F6F] mt-0.5">Receive a morning brief</p>
              </div>
              <button 
                onClick={() => setDailySummary(!dailySummary)}
                className={`w-9 h-5 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  dailySummary ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  dailySummary ? "translate-x-4" : "translate-x-0"
                }`} />
              </button>
            </div>

            {/* Alert Thresholds toggle */}
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#1a1c1b]">Alert Thresholds</h4>
                <p className="text-[10px] text-[#6F6F6F] mt-0.5">Notify on large transfers</p>
              </div>
              <button 
                onClick={() => setAlertThresholds(!alertThresholds)}
                className={`w-9 h-5 rounded-full transition-colors relative border-none cursor-pointer focus:outline-none ${
                  alertThresholds ? "bg-[#c7ff00]" : "bg-neutral-200"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  alertThresholds ? "translate-x-4" : "translate-x-0"
                }`} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
