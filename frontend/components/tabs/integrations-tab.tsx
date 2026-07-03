import { ConnectedBots } from "@/components/connected-bots";

export function IntegrationsTab() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-[#1a1c1b] mb-1">Bot Channels</h2>
        <p className="text-sm text-[#6F6F6F]">Hubungkan Telegram atau WhatsApp ke akun dashboard.</p>
      </div>

      <ConnectedBots />
    </div>
  );
}
