"use client";

import { useState } from "react";
import type { Transaction, ChatMessage } from "@/app/(dashboard)/types";
import { ConnectedBots } from "@/components/connected-bots";
import { ChatSimulator } from "@/components/chat-simulator";
import Link from "next/link";

type OverviewTabProps = {
  userName: string;
  accountId: string;
  totalBalance: number;
  totalIncome: number;
  totalExpense: number;
  transactions: Transaction[];
  formatCurrency: (val: number) => string;
  handleDownloadPDF: () => void;
  isExporting: boolean;
  handleQuickAddIncome: () => void;
  handleQuickAddExpense: () => void;
  quickActionLoading: "income" | "expense" | null;
  quickActionStatus: string | null;
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
  accountId,
  totalBalance,
  totalIncome,
  totalExpense,
  transactions,
  formatCurrency,
  handleDownloadPDF,
  isExporting,
  handleQuickAddIncome,
  handleQuickAddExpense,
  quickActionLoading,
  quickActionStatus,
  filteredTransactions,
}: OverviewTabProps) {
  const [flowType, setFlowType] = useState<"income" | "expense">("income");
  const moneyFlow = buildMoneyFlow(transactions);
  const maxMoneyFlow = Math.max(
    ...moneyFlow.map((item) => item[flowType]),
    1,
  );

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
              <div>
                <span className="block text-sm text-gray-300 mb-1">Total Balance</span>
                <div className="font-bold text-2xl sm:text-3xl">{formatCurrency(totalBalance)}</div>
              </div>
              <span className="bg-[#c7ff00] text-[#151f00] text-[13px] font-semibold px-3 py-1 rounded-full flex items-center gap-1 shrink-0">
                <span className="material-symbols-outlined text-[14px]">receipt_long</span> {transactions.length} tx
              </span>
            </div>
            <div className="flex justify-between items-end relative z-10 text-sm text-gray-400">
              <div>
                <span className="block text-xs uppercase tracking-wider mb-1">Account ID</span>
                {accountId}
              </div>
              <div className="flex -space-x-2">
                <div className="w-6 h-6 rounded-full bg-gray-400 opacity-80"></div>
                <div className="w-6 h-6 rounded-full bg-[#c7ff00]"></div>
              </div>
            </div>
          </div>
          
          {/* Quick Actions Grid */}
          <div className="md:col-span-5 grid grid-cols-2 gap-2 h-full min-h-[220px]">
            <button onClick={handleQuickAddExpense} disabled={quickActionLoading !== null} type="button" className="bg-[#c7ff00] rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
              <span className="material-symbols-outlined text-3xl">send_money</span>
              <span className="text-[13px] font-semibold text-[#151f00]">Add Expense</span>
            </button>
            <button onClick={handleQuickAddIncome} disabled={quickActionLoading !== null} type="button" className="bg-white card-shadow rounded-[20px] p-4 flex flex-col items-center justify-center gap-2 hover-lift disabled:opacity-50">
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
            {quickActionStatus && (
              <div className="col-span-2 rounded-xl bg-white/90 px-3 py-2 text-center text-xs font-semibold text-[#4e6700] card-shadow">
                {quickActionStatus}
              </div>
            )}
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-3 sm:gap-4">
          <div className="bg-white rounded-[24px] p-3 sm:p-4 card-shadow flex items-center gap-2 sm:gap-4">
            <div className="w-8 h-8 sm:w-10 sm:h-10 shrink-0 rounded-full bg-[#5FCF6A]/10 flex items-center justify-center text-[#5FCF6A]">
              <span className="material-symbols-outlined text-[16px] sm:text-[24px]">arrow_upward</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-[#6F6F6F] truncate">Total Income</p>
              <p className="text-[13px] sm:text-[15px] font-semibold text-[#1a1c1b] truncate">{formatCurrency(totalIncome)}</p>
            </div>
          </div>
          <div className="bg-white rounded-[24px] p-3 sm:p-4 card-shadow flex items-center gap-2 sm:gap-4">
            <div className="w-8 h-8 sm:w-10 sm:h-10 shrink-0 rounded-full bg-[#EF6B6B]/10 flex items-center justify-center text-[#EF6B6B]">
              <span className="material-symbols-outlined text-[16px] sm:text-[24px]">arrow_downward</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-[#6F6F6F] truncate">Total Expense</p>
              <p className="text-[13px] sm:text-[15px] font-semibold text-[#1a1c1b] truncate">{formatCurrency(totalExpense)}</p>
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
              <button
                onClick={() => setFlowType("income")}
                className={`px-3 py-1 rounded-full text-[11px] sm:text-xs font-semibold transition-colors cursor-pointer border-none ${
                  flowType === "income"
                    ? "bg-white shadow-sm text-[#191919]"
                    : "bg-transparent text-[#6F6F6F] hover:text-[#191919]"
                }`}
              >Income</button>
              <button
                onClick={() => setFlowType("expense")}
                className={`px-3 py-1 rounded-full text-[11px] sm:text-xs font-semibold transition-colors cursor-pointer border-none ${
                  flowType === "expense"
                    ? "bg-white shadow-sm text-[#191919]"
                    : "bg-transparent text-[#6F6F6F] hover:text-[#191919]"
                }`}
              >Expense</button>
            </div>
          </div>
          <div className="flex-1 flex flex-col justify-end px-4 sm:px-6 pb-6 relative">
            <div className="relative h-44 mt-4">
              {/* Y-axis grid lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                {[4, 3, 2, 1, 0].map((step) => {
                  const val = maxMoneyFlow * (step / 4);
                  let label = "0";
                  if (val > 0) {
                    if (val >= 1000000) label = (val / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
                    else if (val >= 1000) label = (val / 1000).toFixed(1).replace(/\.0$/, "") + "k";
                    else label = val.toString();
                  }
                  return (
                    <div key={step} className="flex items-center w-full relative h-0">
                      <span className="text-[9px] sm:text-[10px] font-semibold text-[#6F6F6F] opacity-50 absolute left-0 w-6 sm:w-8 text-right pr-2">
                        {label}
                      </span>
                      <div className="w-full border-t border-dashed border-[#E8E8E8] ml-6 sm:ml-8"></div>
                    </div>
                  );
                })}
              </div>

              {/* Bars */}
              <div className="absolute inset-0 flex items-end justify-around ml-6 sm:ml-8">
                {moneyFlow.map((item) => {
                  const value = item[flowType];
                  return (
                    <div
                      key={item.key}
                      className="w-7 sm:w-10 bg-[#eeeeec]/50 rounded-t-full relative flex items-end justify-center group cursor-pointer z-10 transition-all hover:bg-[#eeeeec]"
                      style={{ height: `${heightPercent(value, maxMoneyFlow)}%` }}
                    >
                      <div
                        className={`absolute w-full rounded-t-full bottom-0 transition-all ${flowType === "income" ? "bg-[#c7ff00] shadow-[0_0_15px_rgba(199,255,0,0.4)]" : "bg-[#EF6B6B] shadow-[0_0_15px_rgba(239,107,107,0.4)]"}`}
                        style={{ height: value > 0 ? "100%" : "0%" }}
                      />
                      {value > 0 && (
                        <div className="absolute -top-8 bg-[#2A2A2A] text-white text-[10px] sm:text-[11px] px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none whitespace-nowrap">
                          {formatCurrency(value)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-around mt-3 text-[9px] sm:text-[10px] font-bold text-[#6F6F6F] uppercase tracking-wider ml-6 sm:ml-8">
              {moneyFlow.map((item) => (
                <div key={item.key} className="w-7 sm:w-10 text-center">
                  {item.label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right Column (4 cols) */}
      <div className="col-span-12 lg:col-span-4 flex flex-col gap-8 lg:mt-[72px]">
        
        {/* Connected Bot Channels */}
        <ConnectedBots />

        {/* Recent Transactions */}
        <div className="bg-white rounded-[24px] card-shadow flex-1 overflow-hidden flex flex-col">
          <div className="px-6 py-5 flex justify-between items-center border-b border-[#E8E8E8]">
            <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Recent Transactions</h3>
            <Link href="/?tab=transactions" className="text-[#4e6700] text-xs font-semibold hover:underline">View All</Link>
          </div>
          <div className="px-6 divide-y divide-[#E8E8E8]/50">
            {filteredTransactions.slice(0, 5).map(t => {
              const isIncome = t.type === "income";
              const iconBg = isIncome ? "bg-[#c7ff00]/20 text-[#4e6700]" : "bg-[#F1F2F0] text-[#5f5e5e]";
              
              let sourceIcon = "edit_square";
              let sourceTitle = "Manual Entry";
              let sourceBg = "bg-[#F1F2F0] text-[#6F6F6F]";
              
              if (t.source.includes("telegram")) {
                sourceIcon = "send";
                sourceTitle = "Telegram Bot";
                sourceBg = "bg-[#E3F2FD] text-[#1976D2]";
              } else if (t.source.includes("whatsapp")) {
                sourceIcon = "chat";
                sourceTitle = "WhatsApp Bot";
                sourceBg = "bg-[#E8F5E9] text-[#2E7D32]";
              }

              const dateObj = new Date(t.created_at || t.transaction_date);
              const timeStr = dateObj.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

              return (
                <div key={t.id} className="py-4 flex items-center justify-between hover:bg-[#F1F2F0]/30 transition-colors -mx-6 px-6 group">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-all group-hover:bg-white group-hover:shadow-sm ${iconBg}`}>
                      <CategoryIcon name={t.category_name} />
                    </div>
                    <div>
                      <div className="font-semibold text-sm text-[#1a1c1b] mb-0.5">{t.description}</div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[#6F6F6F]">{t.category_name}</span>
                        <span className="w-1 h-1 rounded-full bg-[#E8E8E8]"></span>
                        <span className="text-xs text-[#6F6F6F]">{timeStr}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex items-center gap-3">
                    <div>
                      <div className={`font-semibold text-[15px] sm:text-sm ${isIncome ? "text-[#4e6700]" : "text-[#1a1c1b]"}`}>
                        {isIncome ? "+" : "-"} {formatCurrency(t.amount)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function buildMoneyFlow(transactions: Transaction[]) {
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setDate(date.getDate() - (6 - index));
    const key = formatDateKey(date);
    return {
      key,
      label: date.toLocaleDateString("id-ID", { weekday: "short" }),
      income: 0,
      expense: 0,
    };
  });
  const byDate = new Map(days.map((day) => [day.key, day]));

  transactions.forEach((transaction) => {
    const day = byDate.get(formatDateKey(new Date(transaction.transaction_date)));
    if (!day) return;
    if (transaction.type === "income") {
      day.income += transaction.amount;
    } else {
      day.expense += transaction.amount;
    }
  });

  return days;
}

function formatDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function heightPercent(value: number, max: number): number {
  if (value <= 0) return 8;
  return Math.max(12, Math.round((value / max) * 100));
}
