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
  chatMessages: ChatMessage[];
  chatInput: string;
  setChatInput: (val: string) => void;
  handleSendChatMessage: () => void;
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
  chatMessages,
  chatInput,
  setChatInput,
  handleSendChatMessage,
  handleQuickAddIncome,
  handleQuickAddExpense,
  quickActionLoading,
  quickActionStatus,
  filteredTransactions,
}: OverviewTabProps) {
  const moneyFlow = buildMoneyFlow(transactions);
  const maxMoneyFlow = Math.max(
    ...moneyFlow.map((item) => item.income + item.expense),
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
              <span className="text-sm text-gray-300">Total Balance</span>
              <span className="bg-[#c7ff00] text-[#151f00] text-[13px] font-semibold px-3 py-1 rounded-full flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">receipt_long</span> {transactions.length} tx
              </span>
            </div>
            <div className="relative z-10">
              <div className="font-extrabold text-4xl">{formatCurrency(totalBalance)}</div>
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
              <button 
                onClick={() => setFlowType("income")}
                className={`px-4 py-1.5 rounded-full text-[13px] font-semibold transition-colors cursor-pointer border-none ${
                  flowType === "income" 
                    ? "bg-white shadow-sm text-[#191919]" 
                    : "bg-transparent text-[#6F6F6F] hover:text-[#191919]"
                }`}
              >Income</button>
              <button 
                onClick={() => setFlowType("expense")}
                className={`px-4 py-1.5 rounded-full text-[13px] font-semibold transition-colors cursor-pointer border-none ${
                  flowType === "expense" 
                    ? "bg-white shadow-sm text-[#191919]" 
                    : "bg-transparent text-[#6F6F6F] hover:text-[#191919]"
                }`}
              >Expense</button>
            </div>
          </div>
          <div className="flex-1 flex items-end justify-between px-4 pb-4">
            {moneyFlow.map((item) => (
              <div
                key={item.key}
                className="w-8 sm:w-12 bg-[#eeeeec] rounded-t-full relative flex items-end justify-center"
                style={{ height: `${heightPercent(item.income + item.expense, maxMoneyFlow)}%` }}
              >
                <div
                  className="absolute w-full bg-[#E0F682] rounded-t-full bottom-0"
                  style={{ height: `${heightPercent(item.income, item.income + item.expense || 1)}%` }}
                />
                {(item.income > 0 || item.expense > 0) && (
                  <div className="absolute -top-8 bg-[#2A2A2A] text-white text-[10px] sm:text-xs px-2 py-1 rounded-md">
                    {formatCurrency(item.income - item.expense)}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-between px-2 sm:px-6 text-[10px] sm:text-xs text-[#6F6F6F] uppercase tracking-wider mt-4">
            {moneyFlow.map((item) => <span key={item.key}>{item.label}</span>)}
          </div>
        </div>
      </div>

      {/* Right Column (4 cols) */}
      <div className="col-span-12 lg:col-span-4 flex flex-col gap-8 lg:mt-[72px]">
        
        {/* Connected Bot Channels */}
        <ConnectedBots />

        {/* Chat Simulator Widget */}
        <ChatSimulator 
          chatMessages={chatMessages}
          chatInput={chatInput}
          setChatInput={setChatInput}
          handleSendChatMessage={handleSendChatMessage}
        />

        {/* Recent Transactions */}
        <div className="bg-white rounded-[24px] p-6 card-shadow flex-1">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Recent Transactions</h3>
            <Link href="/?tab=transactions" className="text-[#4e6700] text-xs font-semibold hover:underline">View All</Link>
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
