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

export function ConnectedBots() {
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

  return (
    <div className="bg-white rounded-[28px] p-6 card-shadow">
      <h3 className="text-[15px] font-semibold text-[#1a1c1b] mb-4">Connected Bots</h3>
      <div className="flex flex-col gap-3">
        {channels.map((channel) => {
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

      {command && (
        <div className="mt-4 rounded-2xl bg-[#F1F2F0] p-4">
          <p className="text-xs font-semibold text-[#1a1c1b]">Kirim ke {target}:</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 rounded-xl bg-white px-3 py-2 text-xs font-bold text-[#1a1c1b]">
              {command}
            </code>
            <button
              type="button"
              onClick={copyCommand}
              className="rounded-xl bg-[#c7ff00] px-3 py-2 text-xs font-bold text-[#151f00] hover:bg-[#bff500]"
            >
              Copy
            </button>
          </div>
          <p className="mt-2 text-[11px] text-[#6F6F6F]">
            Kode berlaku 10 menit dan hanya bisa dipakai sekali.
          </p>
        </div>
      )}

      {message && (
        <p className="mt-3 text-xs font-semibold text-[#4e6700]">{message}</p>
      )}
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
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-[#F1F2F0] p-3">
      <div className="flex min-w-0 items-center gap-3">
        <span className={`material-symbols-outlined ${iconClassName}`}>{icon}</span>
        <div className="min-w-0">
          <span className="block truncate text-sm font-semibold">{name}</span>
          <span className="block truncate text-[11px] text-[#6F6F6F]">{detail}</span>
        </div>
      </div>
      <button
        type="button"
        onClick={isLinked ? onRefresh : onConnect}
        disabled={isLoading}
        className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-bold disabled:opacity-60 ${
          isLinked
            ? "bg-white text-[#4e6700]"
            : "bg-[#c7ff00] text-[#151f00] hover:bg-[#bff500]"
        }`}
      >
        {isLoading ? "..." : isLinked ? "Linked" : "Link"}
      </button>
    </div>
  );
}

function formatAccountDetail(account: PlatformAccountResponse | undefined): string {
  if (!account?.is_active) return "Belum terhubung";
  if (account.phone_number) return account.phone_number;
  if (account.platform_user_id) return `ID ${account.platform_user_id}`;
  return "Terhubung";
}
