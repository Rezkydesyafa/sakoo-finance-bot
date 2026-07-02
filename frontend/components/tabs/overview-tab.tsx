import type { Transaction, ChatMessage } from "@/app/(dashboard)/types";

type OverviewTabProps = {
  userName: string;
  totalBalance: number;
  totalIncome: number;
  totalExpense: number;
  formatCurrency: (val: number) => string;
  handleDownloadPDF: () => void;
  isExporting: boolean;
  chatMessages: ChatMessage[];
  chatInput: string;
  setChatInput: (val: string) => void;
  handleSendChatMessage: () => void;
  filteredTransactions: Transaction[];
};

const CategoryIcon = ({ name }: { name: string }) => {
  let iconName = "payments";
  const cleanName = name?.toLowerCase() || "";
  if (cleanName === "makanan") iconName = "restaurant";
  else if (cleanName === "belanja") iconName = "shopping_bag";
  else if (cleanName === "transportasi") iconName = "directions_car";
  else if (cleanName === "gaji") iconName = "payments";
  else if (cleanName === "hiburan") iconName = "sports_esports";
  
  return <span className="material-symbols-outlined text-lg leading-none">{iconName}</span>;
};

export function OverviewTab({
  userName,
  totalBalance,
  totalIncome,
  totalExpense,
  formatCurrency,
  handleDownloadPDF,
  isExporting,
  chatMessages,
  chatInput,
  setChatInput,
  handleSendChatMessage,
  filteredTransactions,
}: OverviewTabProps) {
  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Left Area (8 cols) */}
      <div className="col-span-12 lg:col-span-8 flex flex-col gap-8">
        {/* Greeting Header */}
        <div className="flex justify-between items-end">
          <div>
            <h2 className="font-bold text-3xl text-[#1a1c1b] mb-2">Hello, {userName} 👋</h2>
            <p className="text-sm text-[#6F6F6F]">Your financial assistant is ready to help today.</p>
          </div>
        </div>
        
        {/* Hero Grid: Balance + Actions */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 lg:h-64">
          {/* Balance Card */}
          <div className="md:col-span-7 bg-[#2A2A2A] rounded-[24px] p-6 hero-shadow flex flex-col justify-between relative overflow-hidden text-white min-h-[200px]">
            <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 100% 0%, #C7FF00 0%, transparent 50%)", pointerEvents: "none" }}></div>
            <div className="flex justify-between items-start relative z-10">
              <span className="text-sm text-gray-300">Total Balance</span>
              <span className="bg-[#c7ff00] text-[#151f00] text-[13px] font-semibold px-3 py-1 rounded-full flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">trending_up</span> +12.4%
              </span>
            </div>
            <div className="relative z-10">
              <div className="font-extrabold text-4xl">{formatCurrency(totalBalance)}</div>
            </div>
            <div className="flex justify-between items-end relative z-10 text-sm text-gray-400">
              <div>
                <span className="block text-xs uppercase tracking-wider mb-1">Account ID</span>
                SAKO-992-104
              </div>
              <div className="flex -space-x-2">
                <div className="w-6 h-6 rounded-full bg-gray-400 opacity-80"></div>
                <div className="w-6 h-6 rounded-full bg-[#c7ff00]"></div>
              </div>
            </div>
          </div>
          
          {/* Quick Actions Grid */}
          <div className="md:col-span-5 grid grid-cols-2 grid-rows-2 gap-2 h-full min-h-[200px]">
            <button className="bg-[#c7ff00] rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover:opacity-90 transition-opacity">
              <span className="material-symbols-outlined text-3xl">send_money</span>
              <span className="text-[13px] font-semibold text-[#151f00]">Add Expense</span>
            </button>
            <button className="bg-white card-shadow rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover-lift">
              <span className="material-symbols-outlined text-3xl text-[#6F6F6F]">account_balance_wallet</span>
              <span className="text-[13px] font-semibold text-[#191919]">Add Income</span>
            </button>
            <button className="bg-white card-shadow rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover-lift">
              <span className="material-symbols-outlined text-3xl text-[#6F6F6F]">document_scanner</span>
              <span className="text-[13px] font-semibold text-[#191919]">Scan Receipt</span>
            </button>
            <button onClick={handleDownloadPDF} disabled={isExporting} className="bg-white card-shadow rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover-lift">
              <span className="material-symbols-outlined text-3xl text-[#6F6F6F]">picture_as_pdf</span>
              <span className="text-[13px] font-semibold text-[#191919]">{isExporting ? "Exporting..." : "Export PDF"}</span>
            </button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-white rounded-[24px] p-4 card-shadow flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-[#5FCF6A]/10 flex items-center justify-center text-[#5FCF6A]">
              <span className="material-symbols-outlined">arrow_upward</span>
            </div>
            <div>
              <p className="text-xs text-[#6F6F6F]">Total Income</p>
              <p className="text-[15px] font-semibold text-[#1a1c1b]">{formatCurrency(totalIncome)}</p>
            </div>
          </div>
          <div className="bg-white rounded-[24px] p-4 card-shadow flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-[#EF6B6B]/10 flex items-center justify-center text-[#EF6B6B]">
              <span className="material-symbols-outlined">arrow_downward</span>
            </div>
            <div>
              <p className="text-xs text-[#6F6F6F]">Total Expense</p>
              <p className="text-[15px] font-semibold text-[#1a1c1b]">{formatCurrency(totalExpense)}</p>
            </div>
          </div>
        </div>

        {/* Money Flow Chart */}
        <div className="bg-white rounded-[28px] p-6 card-shadow h-[400px] flex flex-col">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="text-[15px] font-semibold text-[#1a1c1b] mb-1">Money Flow</h3>
              <p className="text-xs text-[#6F6F6F]">Activity over the last 30 days</p>
            </div>
            <div className="bg-[#F1F2F0] rounded-full p-1 flex">
              <button className="px-4 py-1.5 rounded-full bg-white card-shadow text-[13px] font-semibold text-[#191919]">Income</button>
              <button className="px-4 py-1.5 rounded-full text-[13px] font-semibold text-[#6F6F6F] hover:text-[#191919] transition-colors">Expense</button>
            </div>
          </div>
          <div className="flex-1 flex items-end justify-between px-4 pb-4">
            <div className="w-8 sm:w-12 h-[30%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[60%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
            <div className="w-8 sm:w-12 h-[40%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[70%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
            <div className="w-8 sm:w-12 h-[70%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[50%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
            <div className="w-8 sm:w-12 h-[100%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center">
              <div className="absolute w-full h-[85%] bg-[#c7ff00] rounded-t-full bottom-0"></div>
              <div className="absolute -top-8 bg-[#2A2A2A] text-white text-[10px] sm:text-xs px-2 py-1 rounded-md">Rp14m</div>
            </div>
            <div className="w-8 sm:w-12 h-[50%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[65%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
            <div className="w-8 sm:w-12 h-[35%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[80%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
            <div className="w-8 sm:w-12 h-[45%] bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"><div className="absolute w-full h-[90%] bg-[#E0F682] rounded-t-full bottom-0"></div></div>
          </div>
          <div className="flex justify-between px-2 sm:px-6 text-[10px] sm:text-xs text-[#6F6F6F] uppercase tracking-wider mt-4">
            <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
          </div>
        </div>
      </div>

      {/* Right Column (4 cols) */}
      <div className="col-span-12 lg:col-span-4 flex flex-col gap-8 lg:mt-[72px]">
        
        {/* Connected Bot Channels */}
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

        {/* Chat Simulator Widget */}
        <div className="bg-white rounded-[28px] p-6 card-shadow flex flex-col h-[320px]">
          <div className="border-b border-[#E8E8E8] pb-3 mb-4 flex items-center justify-between">
            <div>
              <h4 className="text-[15px] font-semibold text-[#1a1c1b]">AI Assistant Chat</h4>
              <p className="text-[10px] text-[#6F6F6F] font-medium">Test bot parsing here</p>
            </div>
            <span className="h-2 w-2 rounded-full bg-[#5FCF6A] animate-pulse" />
          </div>
          <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 mb-4 pr-1 text-xs font-semibold leading-relaxed">
            {chatMessages.slice(-3).map((msg) => (
              <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}>
                <div className={`p-2.5 rounded-2xl ${
                  msg.sender === "user" ? "bg-[#4e6700] text-white rounded-tr-none" : "bg-[#F1F2F0] text-[#191919] rounded-tl-none border border-[#E8E8E8]"
                }`}>
                  {msg.text}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 border-t border-[#E8E8E8] pt-3">
            <input
              type="text"
              placeholder="e.g. 'beli bensin 25rb'..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendChatMessage()}
              className="flex-1 bg-[#F1F2F0] border-none rounded-xl px-3 py-2 text-xs text-[#191919] placeholder-[#6F6F6F] focus:ring-1 focus:ring-[#c7ff00]"
            />
            <button onClick={handleSendChatMessage} className="bg-[#c7ff00] hover:bg-[#bff500] text-[#151f00] text-[13px] font-semibold px-3 py-2 rounded-xl text-xs transition" type="button">
              Send
            </button>
          </div>
        </div>

        {/* Recent Transactions */}
        <div className="bg-white rounded-[24px] p-6 card-shadow flex-1">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Recent Transactions</h3>
            <button className="text-[#4e6700] text-xs font-semibold hover:underline">View All</button>
          </div>
          <div className="flex flex-col gap-4">
            {filteredTransactions.slice(0, 5).map(t => (
              <div key={t.id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F]">
                    <CategoryIcon name={t.category_name} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#1a1c1b]">{t.description}</p>
                    <p className="text-xs text-[#6F6F6F]">{t.category_name} • {new Date(t.transaction_date).toLocaleDateString("id-ID")}</p>
                  </div>
                </div>
                <span className={`text-sm font-semibold ${t.type === "income" ? "text-[#4e6700]" : "text-[#1a1c1b]"}`}>
                  {t.type === "income" ? "+" : "-"}{formatCurrency(t.amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
