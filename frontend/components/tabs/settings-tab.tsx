export function SettingsTab() {
  return (
    <div className="bg-white rounded-[28px] p-6 card-shadow text-center py-12 flex flex-col items-center">
      <span className="material-symbols-outlined text-5xl text-[#6F6F6F] mb-4">settings</span>
      <h3 className="text-lg font-semibold text-[#1a1c1b] mb-2">Settings</h3>
      <p className="text-sm text-[#6F6F6F] max-w-sm">
        Configure profile, notifications, and bot credentials here soon. You will be able to manage connected channels and Telegram tokens.
      </p>
    </div>
  );
}
