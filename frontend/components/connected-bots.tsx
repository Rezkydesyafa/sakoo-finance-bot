export function ConnectedBots() {
  return (
    <div className="bg-white rounded-[28px] p-6 card-shadow">
      <h3 className="text-[15px] font-semibold text-[#1a1c1b] mb-4">Connected Bots</h3>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between p-3 rounded-xl bg-[#F1F2F0]">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-blue-500">tram</span>
            <span className="text-sm font-semibold">Telegram Bot</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#5FCF6A] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#5FCF6A]"></span>
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between p-3 rounded-xl bg-[#F1F2F0]">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-green-500">chat</span>
            <span className="text-sm font-semibold">WhatsApp Bot</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#6F6F6F]"></span>
          </div>
        </div>
      </div>
    </div>
  );
}
