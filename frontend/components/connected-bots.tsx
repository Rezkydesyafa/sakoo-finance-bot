"use client";

import { useEffect, useState } from "react";
import { getStoredAuthToken } from "@/lib/auth-storage";
import { apiClient } from "@/lib/api";
import type { PlatformAccountResponse } from "@/lib/api";

type BotChannel = "Telegram" | "WhatsApp";
type Platform = PlatformAccountResponse["platform"];

const channels: Array<{
  name: BotChannel;
  platform: Platform;
  label: string;
  icon: string;
  iconClassName: string;
}> = [
  {
    name: "Telegram",
    platform: "telegram",
    label: "Telegram Bot",
    icon: "send",
    iconClassName: "text-blue-500",
  },
  {
    name: "WhatsApp",
    platform: "whatsapp",
    label: "WhatsApp Bot",
    icon: "chat",
    iconClassName: "text-green-500",
  },
];

export function ConnectedBots({ displayMode = "all" }: { displayMode?: "all" | "connectedOnly" }) {
  const [accounts, setAccounts] = useState<PlatformAccountResponse[]>([]);
  const [command, setCommand] = useState<string | null>(null);
  const [target, setTarget] = useState<BotChannel | null>(null);
  const [loadingTarget, setLoadingTarget] = useState<BotChannel | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    refreshAccounts();
  }, []);

  async function refreshAccounts() {
    const token = getStoredAuthToken();
    if (!token) return;

    try {
      setAccounts(await apiClient.auth.platformAccounts(token));
    } catch {
      setMessage("Gagal memuat status bot.");
    }
  }

  async function createLinkingCode(channel: BotChannel) {
    const token = getStoredAuthToken();
    if (!token) {
      setMessage("Silakan login ulang untuk membuat kode linking.");
      return;
    }

    setLoadingTarget(channel);
    setMessage(null);

    try {
      const response = await apiClient.auth.linkingCode(token);
      setCommand(response.command);
      setTarget(channel);
      await refreshAccounts();
    } catch {
      setMessage("Gagal membuat kode linking. Coba lagi.");
    } finally {
      setLoadingTarget(null);
    }
  }

  async function copyCommand() {
    if (!command) return;
    await navigator.clipboard.writeText(command);
    setMessage("Command disalin.");
  }

  const linkedAccounts = accounts.filter((a) => a.is_active);
  const isConnectedOnly = displayMode === "connectedOnly";

  if (isConnectedOnly && linkedAccounts.length === 0) {
    return (
      <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 bg-[#F1F2F0] rounded-full flex items-center justify-center mb-3">
          <span className="material-symbols-outlined text-[#6F6F6F]">link_off</span>
        </div>
        <h3 className="text-[15px] font-semibold text-[#1a1c1b] mb-1">Belum Terhubung</h3>
        <p className="text-xs text-[#6F6F6F] mb-4">Anda belum menghubungkan bot AI.</p>
        <button 
          onClick={() => {
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.set("tab", "integrations");
            window.location.search = currentParams.toString();
          }}
          className="bg-[#c7ff00] text-[#151f00] px-4 py-2 rounded-full text-xs font-bold hover:bg-[#bff500] border-none cursor-pointer"
        >
          Hubungkan Bot
        </button>
      </div>
    );
  }

  if (!isConnectedOnly) {
    return (
      <div className="w-full">
        <div className="hidden md:block">
          <BotChannelsGrid 
            accounts={accounts} 
            command={command} 
            target={target} 
            loadingTarget={loadingTarget} 
            createLinkingCode={createLinkingCode} 
            copyCommand={copyCommand} 
            message={message} 
            refreshAccounts={refreshAccounts}
          />
        </div>
        <div className="block md:hidden">
          <BotChannelsMobileList 
            accounts={accounts}
            command={command}
            target={target}
            loadingTarget={loadingTarget}
            createLinkingCode={createLinkingCode}
            copyCommand={copyCommand}
            refreshAccounts={refreshAccounts}
          />
        </div>
      </div>
    );
  }

  const channelsToShow = channels.filter(c => accounts.some(a => a.platform === c.platform && a.is_active));

  return (
    <div className={`bg-white rounded-[24px] p-6 card-shadow`}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Connected Bots</h3>
        <button 
          onClick={() => {
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.set("tab", "integrations");
            window.location.search = currentParams.toString();
          }}
          className="text-[#4e6700] text-xs font-semibold hover:underline border-none bg-transparent cursor-pointer"
        >
          Show All
        </button>
      </div>
      <div className="flex flex-col gap-3">
        {channelsToShow.map((channel) => {
          const account = accounts.find((item) => item.platform === channel.platform);
          return (
            <BotRow
              key={channel.platform}
              name={channel.label}
              detail={formatAccountDetail(account)}
              icon={channel.icon}
              iconClassName={channel.iconClassName}
              isLinked={Boolean(account?.is_active)}
              isLoading={loadingTarget === channel.name}
              onConnect={() => createLinkingCode(channel.name)}
              onRefresh={refreshAccounts}
            />
          );
        })}
      </div>
    </div>
  );
}

function BotChannelsGrid({
  accounts,
  command,
  target,
  loadingTarget,
  createLinkingCode,
  copyCommand,
  message,
  refreshAccounts,
}: {
  accounts: PlatformAccountResponse[];
  command: string | null;
  target: BotChannel | null;
  loadingTarget: BotChannel | null;
  createLinkingCode: (c: BotChannel) => void;
  copyCommand: () => void;
  message: string | null;
  refreshAccounts: () => void;
}) {
  const telegramAcc = accounts.find(a => a.platform === "telegram");
  const whatsappAcc = accounts.find(a => a.platform === "whatsapp");

  return (
    <div className="flex flex-col gap-8 w-full">
      {/* Channel Grid */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* Telegram Card */}
        <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col gap-4 relative overflow-hidden group border border-[#E8E8E8]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#c7ff00] opacity-10 rounded-bl-full transform translate-x-4 -translate-y-4 group-hover:scale-110 transition-transform"></div>
          <div className="flex items-start justify-between z-10">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#E0F0FA] flex items-center justify-center text-[#2AABEE]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.18-.08-.05-.19-.02-.27 0-.11.03-1.84 1.18-5.18 3.44-.49.34-.93.5-1.33.49-.44-.01-1.28-.25-1.9-.45-.76-.25-1.36-.38-1.31-.8.02-.22.32-.45.9-.69 3.53-1.54 5.88-2.55 7.05-3.04 3.36-1.4 4.06-1.64 4.52-1.65.1 0 .33.02.48.13.12.1.16.24.17.34-.01.05-.01.17-.03.27z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Telegram</h3>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-2 h-2 rounded-full ${telegramAcc?.is_active ? "bg-[#c7ff00] animate-pulse" : "bg-neutral-300"}`}></span>
                  <span className="text-[12px] text-[#6F6F6F]">{telegramAcc?.is_active ? "Connected" : "Disconnected"}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-1 z-10 mt-2">
            <div className="flex justify-between items-center py-2 border-b border-[#F1F2F0]">
              <span className="text-[12px] text-[#6F6F6F]">User ID</span>
              <span className="text-[14px] font-semibold text-[#1a1c1b]">{telegramAcc?.platform_user_id || "--"}</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-[12px] text-[#6F6F6F]">Status</span>
              <span className="text-[14px] text-[#1a1c1b]">{telegramAcc?.is_active ? "Active" : "Pending"}</span>
            </div>
          </div>
          <div className="mt-auto pt-2 z-10">
            <button 
              onClick={telegramAcc?.is_active ? refreshAccounts : () => createLinkingCode("Telegram")}
              disabled={loadingTarget === "Telegram"}
              className={`w-full py-2.5 rounded-full font-semibold text-[13px] transition-colors border-none cursor-pointer flex items-center justify-center gap-2 ${
                telegramAcc?.is_active ? "bg-[#F1F2F0] text-[#1a1c1b] hover:bg-[#E8E8E8]" : "bg-[#c7ff00] text-[#151f00] hover:bg-[#bff500]"
              }`}
            >
              {loadingTarget === "Telegram" ? "Memproses..." : telegramAcc?.is_active ? "Manage" : <><span className="material-symbols-outlined text-[18px]">add_link</span> Connect</>}
            </button>
          </div>
        </div>

        {/* WhatsApp Card */}
        <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col gap-4 relative overflow-hidden group border border-[#E8E8E8]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#5FCF6A] opacity-10 rounded-bl-full transform translate-x-4 -translate-y-4 group-hover:scale-110 transition-transform"></div>
          <div className="flex items-start justify-between z-10">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#E3F5E7] flex items-center justify-center text-[#25D366]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">WhatsApp</h3>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-2 h-2 rounded-full ${whatsappAcc?.is_active ? "bg-[#c7ff00] animate-pulse" : "bg-neutral-300"}`}></span>
                  <span className="text-[12px] text-[#6F6F6F]">{whatsappAcc?.is_active ? "Connected" : "Disconnected"}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-1 z-10 mt-2">
            <div className="flex justify-between items-center py-2 border-b border-[#F1F2F0]">
              <span className="text-[12px] text-[#6F6F6F]">Phone</span>
              <span className="text-[14px] font-semibold text-[#1a1c1b]">{whatsappAcc?.phone_number || "--"}</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-[12px] text-[#6F6F6F]">Status</span>
              <span className="text-[14px] text-[#1a1c1b]">{whatsappAcc?.is_active ? "Active" : "Pending"}</span>
            </div>
          </div>
          <div className="mt-auto pt-2 z-10">
            <button 
              onClick={whatsappAcc?.is_active ? refreshAccounts : () => createLinkingCode("WhatsApp")}
              disabled={loadingTarget === "WhatsApp"}
              className={`w-full py-2.5 rounded-full font-semibold text-[13px] transition-colors border-none cursor-pointer flex items-center justify-center gap-2 ${
                whatsappAcc?.is_active ? "bg-[#F1F2F0] text-[#1a1c1b] hover:bg-[#E8E8E8]" : "bg-[#c7ff00] text-[#151f00] hover:bg-[#bff500]"
              }`}
            >
              {loadingTarget === "WhatsApp" ? "Memproses..." : whatsappAcc?.is_active ? "Manage" : <><span className="material-symbols-outlined text-[18px]">add_link</span> Connect</>}
            </button>
          </div>
        </div>

        {/* Discord Card (Disconnected) */}
        <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col gap-4 relative overflow-hidden group border border-[#E8E8E8]">
          <div className="flex items-start justify-between z-10">
            <div className="flex items-center gap-3 opacity-70">
              <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Discord</h3>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="w-2 h-2 rounded-full bg-neutral-300"></span>
                  <span className="text-[12px] text-[#6F6F6F]">Coming Soon</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-1 z-10 mt-2 opacity-50">
            <div className="flex justify-between items-center py-2 border-b border-[#F1F2F0]">
              <span className="text-[12px] text-[#6F6F6F]">Server ID</span>
              <span className="text-[14px] font-semibold text-[#1a1c1b]">--</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-[12px] text-[#6F6F6F]">Status</span>
              <span className="text-[14px] text-[#1a1c1b]">--</span>
            </div>
          </div>
          <div className="mt-auto pt-2 z-10">
            <button 
              disabled
              className="w-full py-2.5 rounded-full font-semibold text-[13px] bg-[#F1F2F0] text-[#6F6F6F] border-none flex items-center justify-center gap-2 opacity-70 cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[18px]">add_link</span> Connect
            </button>
          </div>
        </div>

      </section>

      {/* Linking Action Code Prompt */}
      {command && (
        <div className="rounded-2xl bg-[#c7ff00]/20 p-6 border border-[#c7ff00]/50 animate-fade-in shadow-sm">
          <p className="text-sm font-semibold text-[#151f00]">
            Untuk menghubungkan ke {target}, salin kode berikut dan kirim ke bot:
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <code className="min-w-0 flex-1 rounded-xl bg-white px-4 py-3 text-sm font-bold text-[#1a1c1b] border border-[#E8E8E8]">
              {command}
            </code>
            <button
              type="button"
              onClick={copyCommand}
              className="rounded-xl bg-[#c7ff00] px-6 py-3 text-[13px] font-bold text-[#151f00] hover:bg-[#bff500] border-none cursor-pointer shadow-sm active:scale-95 transition-transform"
            >
              Copy Code
            </button>
          </div>
          <p className="mt-3 text-[12px] text-[#587300] font-medium">
            * Kode ini hanya berlaku 10 menit dan hanya bisa dipakai sekali.
          </p>
        </div>
      )}
      
      {message && (
        <p className="text-sm font-semibold text-[#4e6700] p-4 bg-[#c7ff00]/10 rounded-xl">{message}</p>
      )}

      {/* Configuration Section */}
      <section className="mt-4">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E8E8E8]">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-[20px] font-bold text-[#1a1c1b]">Command Settings</h2>
              <p className="text-[14px] text-[#6F6F6F] mt-1">Configure global bot behavior across all active channels.</p>
            </div>
            <button className="px-4 py-2 rounded-full border border-[#E8E8E8] bg-transparent text-[#1a1c1b] font-semibold text-[13px] hover:bg-[#F1F2F0] transition-colors whitespace-nowrap cursor-pointer">
              Reset to Default
            </button>
          </div>

          <div className="flex flex-col divide-y divide-[#E8E8E8]">
            {/* Toggle Item 1 */}
            <div className="py-5 flex items-start sm:items-center justify-between group">
              <div className="flex flex-col gap-1 pr-4">
                <span className="font-semibold text-[14px] text-[#1a1c1b] group-hover:text-[#4e6700] transition-colors">Auto-categorization</span>
                <span className="text-[12px] text-[#6F6F6F] max-w-sm">Automatically assign categories to transactions parsed from chat messages.</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 mt-2 sm:mt-0">
                <input defaultChecked type="checkbox" className="sr-only peer" />
                <div className="w-11 h-6 bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#c7ff00]"></div>
              </label>
            </div>

            {/* Toggle Item 2 */}
            <div className="py-5 flex items-start sm:items-center justify-between group">
              <div className="flex flex-col gap-1 pr-4">
                <span className="font-semibold text-[14px] text-[#1a1c1b] group-hover:text-[#4e6700] transition-colors">Daily Summary</span>
                <span className="text-[12px] text-[#6F6F6F] max-w-sm">Receive a concise financial summary every morning at 08:00 AM.</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 mt-2 sm:mt-0">
                <input defaultChecked type="checkbox" className="sr-only peer" />
                <div className="w-11 h-6 bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#c7ff00]"></div>
              </label>
            </div>

            {/* Toggle Item 3 */}
            <div className="py-5 flex items-start sm:items-center justify-between group">
              <div className="flex flex-col gap-1 pr-4">
                <span className="font-semibold text-[14px] text-[#1a1c1b] group-hover:text-[#4e6700] transition-colors">Receipt OCR via Chat</span>
                <span className="text-[12px] text-[#6F6F6F] max-w-sm">Allow the bot to read and extract data from receipt images sent in chat.</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 mt-2 sm:mt-0">
                <input type="checkbox" className="sr-only peer" />
                <div className="w-11 h-6 bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#c7ff00]"></div>
              </label>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

type BotRowProps = {
  name: string;
  detail: string;
  icon: string;
  iconClassName: string;
  isLinked: boolean;
  isLoading: boolean;
  onConnect: () => void;
  onRefresh: () => void;
};

function BotRow({
  name,
  detail,
  icon,
  iconClassName,
  isLinked,
  isLoading,
  onConnect,
  onRefresh,
}: BotRowProps) {
  if (name === "Telegram Bot") {
    return (
      <div 
        onClick={isLinked ? onRefresh : onConnect}
        className="flex items-center justify-between p-4 rounded-3xl bg-[#2B2D27] cursor-pointer shadow-sm hover:opacity-90 transition-opacity"
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-[#c7ff00]/10 flex items-center justify-center text-[#c7ff00]">
            <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.18-.08-.05-.19-.02-.27 0-.11.03-1.84 1.18-5.18 3.44-.49.34-.93.5-1.33.49-.44-.01-1.28-.25-1.9-.45-.76-.25-1.36-.38-1.31-.8.02-.22.32-.45.9-.69 3.53-1.54 5.88-2.55 7.05-3.04 3.36-1.4 4.06-1.64 4.52-1.65.1 0 .33.02.48.13.12.1.16.24.17.34-.01.05-.01.17-.03.27z"></path>
            </svg>
          </div>
          <div className="flex flex-col">
            <span className="text-[15px] font-bold text-white leading-tight">Telegram</span>
            <span className="text-[12px] text-[#A0A29C] leading-tight mt-0.5">{detail}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isLinked ? "bg-[#c7ff00]" : "bg-neutral-500"}`}></span>
          <span className={`text-[12px] font-bold ${isLinked ? "text-[#c7ff00]" : "text-neutral-400"}`}>
            {isLoading ? "..." : isLinked ? "Connected" : "Connect"}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div 
      onClick={isLinked ? onRefresh : onConnect}
      className="flex items-center justify-between p-4 rounded-3xl bg-white cursor-pointer shadow-[0_2px_10px_rgba(0,0,0,0.03)] hover:bg-[#F9F9F7] transition-colors border border-[#E8E8E8]"
    >
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-[#E3F5E7] flex items-center justify-center text-[#25D366]">
          <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"></path>
          </svg>
        </div>
        <div className="flex flex-col">
          <span className="text-[15px] font-bold text-[#1a1c1b] leading-tight">WhatsApp</span>
          <span className="text-[12px] text-[#6F6F6F] leading-tight mt-0.5">{detail}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${isLinked ? "bg-[#5FCF6A]" : "bg-neutral-300"}`}></span>
        <span className={`text-[12px] font-semibold ${isLinked ? "text-[#5FCF6A]" : "text-[#6F6F6F]"}`}>
          {isLoading ? "..." : isLinked ? "Connected" : "Connect"}
        </span>
      </div>
    </div>
  );
}

function formatAccountDetail(account: PlatformAccountResponse | undefined): string {
  if (!account?.is_active) return "Belum terhubung";
  if (account.phone_number) return account.phone_number;
  if (account.platform_user_id) return `ID ${account.platform_user_id}`;
  return "Terhubung";
}

function BotChannelsMobileList({
  accounts,
  command,
  target,
  loadingTarget,
  createLinkingCode,
  copyCommand,
  refreshAccounts,
}: {
  accounts: PlatformAccountResponse[];
  command: string | null;
  target: BotChannel | null;
  loadingTarget: BotChannel | null;
  createLinkingCode: (c: BotChannel) => void;
  copyCommand: () => void;
  refreshAccounts: () => void;
}) {
  const telegramAcc = accounts.find(a => a.platform === "telegram");
  const whatsappAcc = accounts.find(a => a.platform === "whatsapp");

  return (
    <div className="flex flex-col gap-6 w-full pb-8 animate-fade-in">
      
      {/* Integrations List */}
      <div>
        <h2 className="text-[13px] text-[#6F6F6F] font-semibold mb-3">Active Integrations</h2>
        <div className="flex flex-col gap-3">
          
          {/* Telegram */}
          <div 
            onClick={telegramAcc?.is_active ? refreshAccounts : () => createLinkingCode("Telegram")}
            className="flex items-center justify-between p-4 rounded-3xl bg-[#2B2D27] cursor-pointer shadow-sm hover:opacity-90 transition-opacity"
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-[#c7ff00]/10 flex items-center justify-center text-[#c7ff00]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.18-.08-.05-.19-.02-.27 0-.11.03-1.84 1.18-5.18 3.44-.49.34-.93.5-1.33.49-.44-.01-1.28-.25-1.9-.45-.76-.25-1.36-.38-1.31-.8.02-.22.32-.45.9-.69 3.53-1.54 5.88-2.55 7.05-3.04 3.36-1.4 4.06-1.64 4.52-1.65.1 0 .33.02.48.13.12.1.16.24.17.34-.01.05-.01.17-.03.27z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <span className="text-[15px] font-bold text-white leading-tight">Telegram</span>
                <span className="text-[12px] text-[#A0A29C] leading-tight mt-0.5">{telegramAcc?.platform_user_id ? `@${telegramAcc.platform_user_id}` : "@SakooFinanceBot"}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${telegramAcc?.is_active ? "bg-[#c7ff00]" : "bg-neutral-500"}`}></span>
              <span className={`text-[12px] font-bold ${telegramAcc?.is_active ? "text-[#c7ff00]" : "text-neutral-400"}`}>
                {loadingTarget === "Telegram" ? "..." : telegramAcc?.is_active ? "Connected" : "Connect"}
              </span>
            </div>
          </div>

          {/* WhatsApp */}
          <div 
            onClick={whatsappAcc?.is_active ? refreshAccounts : () => createLinkingCode("WhatsApp")}
            className="flex items-center justify-between p-4 rounded-3xl bg-white cursor-pointer shadow-[0_2px_10px_rgba(0,0,0,0.03)] hover:bg-[#F9F9F7] transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#E3F5E7] flex items-center justify-center text-[#25D366]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <span className="text-[15px] font-bold text-[#1a1c1b] leading-tight">WhatsApp</span>
                <span className="text-[12px] text-[#6F6F6F] leading-tight mt-0.5">{whatsappAcc?.phone_number || "+1 (555) 012-3456"}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${whatsappAcc?.is_active ? "bg-[#5FCF6A]" : "bg-neutral-300"}`}></span>
              <span className={`text-[12px] font-semibold ${whatsappAcc?.is_active ? "text-[#5FCF6A]" : "text-[#6F6F6F]"}`}>
                {loadingTarget === "WhatsApp" ? "..." : whatsappAcc?.is_active ? "Connected" : "Connect"}
              </span>
            </div>
          </div>

          {/* Discord */}
          <div className="flex items-center justify-between p-4 rounded-3xl bg-white shadow-[0_2px_10px_rgba(0,0,0,0.03)]">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F]">
                <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"></path>
                </svg>
              </div>
              <div className="flex flex-col">
                <span className="text-[15px] font-bold text-[#1a1c1b] leading-tight">Discord</span>
                <span className="text-[12px] text-[#6F6F6F] leading-tight mt-0.5">Not linked</span>
              </div>
            </div>
            <button disabled className="px-4 py-2 rounded-full bg-[#6F6F6F] text-white text-[12px] font-bold border-none opacity-90">
              Connect
            </button>
          </div>

        </div>
      </div>

      {command && (
        <div className="rounded-2xl bg-[#c7ff00]/20 p-5 border border-[#c7ff00]/50 mt-2">
          <p className="text-[13px] font-semibold text-[#151f00] mb-3">
            Kirim kode ke {target}:
          </p>
          <div className="flex items-center gap-3">
            <code className="flex-1 rounded-xl bg-white px-3 py-2 text-[13px] font-bold text-[#1a1c1b] border border-[#E8E8E8]">
              {command}
            </code>
            <button
              onClick={copyCommand}
              className="rounded-xl bg-[#c7ff00] px-4 py-2 text-[12px] font-bold text-[#151f00] border-none active:scale-95 transition-transform"
            >
              Copy
            </button>
          </div>
        </div>
      )}

      {/* Bot Features */}
      <div className="mt-2">
        <h2 className="text-[13px] text-[#6F6F6F] font-semibold mb-3">Bot Features</h2>
        <div className="bg-white rounded-[24px] shadow-[0_2px_10px_rgba(0,0,0,0.03)] flex flex-col divide-y divide-[#F1F2F0] px-5 py-2">
          
          <div className="py-4 flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="text-[14px] font-bold text-[#1a1c1b]">Auto-categorization</span>
              <span className="text-[12px] text-[#6F6F6F]">AI labels new expenses</span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
              <input defaultChecked type="checkbox" className="sr-only peer" />
              <div className="w-10 h-[22px] bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-[18px] peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-[18px] after:w-[18px] after:transition-all peer-checked:bg-[#c7ff00]"></div>
            </label>
          </div>

          <div className="py-4 flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="text-[14px] font-bold text-[#1a1c1b]">Daily Summaries</span>
              <span className="text-[12px] text-[#6F6F6F]">Receive a morning brief</span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
              <input defaultChecked type="checkbox" className="sr-only peer" />
              <div className="w-10 h-[22px] bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-[18px] peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-[18px] after:w-[18px] after:transition-all peer-checked:bg-[#c7ff00]"></div>
            </label>
          </div>

          <div className="py-4 flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="text-[14px] font-bold text-[#1a1c1b]">Alert Thresholds</span>
              <span className="text-[12px] text-[#6F6F6F]">Notify on large transfers</span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
              <input type="checkbox" className="sr-only peer" />
              <div className="w-10 h-[22px] bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-[18px] peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-[18px] after:w-[18px] after:transition-all peer-checked:bg-[#c7ff00]"></div>
            </label>
          </div>

        </div>
      </div>
      
    </div>
  );
}
