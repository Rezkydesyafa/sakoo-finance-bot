import { useState } from "react";
import type { Transaction } from "@/app/(dashboard)/types";

type TransactionsTabProps = {
  transactions: Transaction[];
  filteredTransactions: Transaction[];
  expenseFilterType: "all" | "income" | "expense";
  setExpenseFilterType: (val: "all" | "income" | "expense") => void;
  formatCurrency: (val: number) => string;
  handleDeleteTransaction: (id: number) => void;
  handleEditTransaction: (id: number) => void;
  handleQuickAddIncome: () => void;
  handleQuickAddExpense: () => void;
  quickActionLoading: "income" | "expense" | null;
  quickActionStatus: string | null;
  handleDownloadPDF: () => void;
  isExporting: boolean;
  totalBalance: number;
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

export function TransactionsTab({
  transactions,
  filteredTransactions,
  expenseFilterType,
  setExpenseFilterType,
  formatCurrency,
  handleDeleteTransaction,
  handleEditTransaction,
  handleQuickAddIncome,
  handleQuickAddExpense,
  quickActionLoading,
  quickActionStatus,
  handleDownloadPDF,
  isExporting,
  totalBalance,
}: TransactionsTabProps) {
  const [isFilterDropdownOpen, setIsFilterDropdownOpen] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);

  const todayStr = new Date().toISOString().split("T")[0];
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = yesterday.toISOString().split("T")[0];

  const grouped = {
    Today: filteredTransactions.filter(t => t.transaction_date.split("T")[0] === todayStr),
    Yesterday: filteredTransactions.filter(t => t.transaction_date.split("T")[0] === yesterdayStr),
    Earlier: filteredTransactions.filter(t => {
      const dateStr = t.transaction_date.split("T")[0];
      return dateStr !== todayStr && dateStr !== yesterdayStr;
    })
  };

  const thisMonthSpending = transactions
    .filter(t => t.type === "expense")
    .reduce((sum, t) => sum + t.amount, 0);

  const totalSavings = totalBalance > 0 ? totalBalance : 32100000;

  const renderTransactionRow = (t: Transaction) => {
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
            <div className={`font-semibold text-sm ${isIncome ? "text-[#4e6700]" : "text-[#1a1c1b]"}`}>
              {isIncome ? "+" : "-"} {formatCurrency(t.amount)}
            </div>
          </div>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${sourceBg}`} title={sourceTitle}>
            <span className="material-symbols-outlined text-[16px]">{sourceIcon}</span>
          </div>
          
          <div className="relative">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setOpenDropdownId(openDropdownId === t.id ? null : t.id);
              }}
              className="w-8 h-8 rounded-full hover:bg-neutral-100 flex items-center justify-center text-[#6F6F6F] transition-colors border-none bg-transparent cursor-pointer ml-1"
            >
              <span className="material-symbols-outlined text-[18px]">more_vert</span>
            </button>

            {openDropdownId === t.id && (
              <>
                <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setOpenDropdownId(null); }}></div>
                <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-[#E8E8E8] py-1 z-50 animate-in fade-in slide-in-from-top-1 duration-200">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenDropdownId(null);
                      handleEditTransaction(t.id);
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-[#1a1c1b] font-medium hover:bg-[#F1F2F0] transition-colors flex items-center gap-2 border-none bg-transparent cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px] text-[#6F6F6F]">edit</span>
                    Edit
                  </button>
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenDropdownId(null);
                      handleDeleteTransaction(t.id);
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 font-medium hover:bg-red-50 transition-colors flex items-center gap-2 border-none bg-transparent cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">delete</span>
                    Hapus
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Left Column */}
      <div className="col-span-12 xl:col-span-8 space-y-6 min-w-0">
        <div className="flex flex-row items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-[#1a1c1b]">Daftar Transaksi</h2>
          <div className="flex gap-2">
            <div className="relative">
              <button 
                onClick={() => setIsFilterDropdownOpen(!isFilterDropdownOpen)}
                className="flex items-center gap-1 bg-[#F1F2F0] border-none rounded-full py-2 pl-4 pr-3 text-xs font-semibold text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] cursor-pointer"
              >
                {expenseFilterType === "all" ? "This Month" : expenseFilterType === "income" ? "Income" : "Expense"}
                <span className={`material-symbols-outlined text-[16px] text-[#6F6F6F] transition-transform ${isFilterDropdownOpen ? 'rotate-180' : ''}`}>
                  expand_more
                </span>
              </button>
              
              {isFilterDropdownOpen && (
                <div className="absolute right-0 top-full mt-2 w-32 bg-white rounded-[24px] shadow-lg border border-[#E8E8E8] py-2 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                  {[
                    { value: "all", label: "This Month" },
                    { value: "income", label: "Income" },
                    { value: "expense", label: "Expense" }
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => {
                        setExpenseFilterType(opt.value as "all" | "income" | "expense");
                        setIsFilterDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2.5 text-xs font-semibold hover:bg-[#F1F2F0] transition-colors cursor-pointer border-none bg-transparent ${expenseFilterType === opt.value ? 'text-[#4e6700]' : 'text-[#1a1c1b]'}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            <button className="flex flex-none items-center gap-1 bg-[#F1F2F0] py-2 px-4 rounded-full text-xs font-semibold text-[#1a1c1b] hover:bg-[#E8E8E8] transition-colors border-none cursor-pointer">
              <span className="material-symbols-outlined text-[16px]">filter_list</span>
              <span className="hidden sm:inline">Filter</span>
            </button>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="bg-white p-6 rounded-[24px] card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                <span className="material-symbols-outlined text-[20px]">trending_down</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">This Month&apos;s Spending</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">{formatCurrency(thisMonthSpending)}</div>
          </div>

          <div className="bg-white p-6 rounded-[24px] card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#c7ff00]/20 flex items-center justify-center text-[#4e6700]">
                <span className="material-symbols-outlined text-[20px]">savings</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">Total Savings</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">{formatCurrency(totalSavings)}</div>
          </div>
        </div>

        {/* Transactions List Grouped */}
        <div className="bg-white rounded-[24px] card-shadow overflow-hidden">
          {grouped.Today.length > 0 && (
            <>
              <div className="px-6 py-5 bg-white border-b border-[#E8E8E8]">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Today</h3>
              </div>
              <div className="px-6 divide-y divide-[#E8E8E8]/50">
                {grouped.Today.map(t => renderTransactionRow(t))}
              </div>
            </>
          )}

          {grouped.Yesterday.length > 0 && (
            <>
              <div className="px-6 py-5 bg-white border-y border-[#E8E8E8]">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Yesterday</h3>
              </div>
              <div className="px-6 divide-y divide-[#E8E8E8]/50">
                {grouped.Yesterday.map(t => renderTransactionRow(t))}
              </div>
            </>
          )}

          {grouped.Earlier.length > 0 && (
            <>
              <div className="px-6 py-5 bg-white border-y border-[#E8E8E8]">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Earlier</h3>
              </div>
              <div className="px-6 divide-y divide-[#E8E8E8]/50">
                {grouped.Earlier.map(t => renderTransactionRow(t))}
              </div>
            </>
          )}

          {filteredTransactions.length === 0 && (
            <div className="p-8 text-center text-[#6F6F6F]">No transactions recorded.</div>
          )}

          <div className="p-4 border-t border-[#E8E8E8] text-center">
            <button className="text-[13px] font-semibold text-[#4e6700] hover:text-[#587300] transition-colors py-2 px-6 rounded-full hover:bg-[#c7ff00]/10 border-none cursor-pointer">
              Load More Transactions
            </button>
          </div>
        </div>
      </div>

      {/* Right Column */}
      <div className="col-span-12 xl:col-span-4 space-y-6 min-w-0">
        {/* Quick Action Card */}
        <div className="bg-white p-6 rounded-[24px] card-shadow">
          <h3 className="text-base font-bold text-[#1a1c1b] mb-4">Quick Action</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <button onClick={handleQuickAddIncome} disabled={quickActionLoading !== null} className="bg-[#c7ff00] text-[#151f00] py-3 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity border-none cursor-pointer disabled:opacity-50">
              <span className="material-symbols-outlined text-[18px]">add</span> Income
            </button>
            <button onClick={handleQuickAddExpense} disabled={quickActionLoading !== null} className="bg-[#2A2A2A] text-white py-3 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity border-none cursor-pointer disabled:opacity-50">
              <span className="material-symbols-outlined text-[18px]">remove</span> Expense
            </button>
          </div>
          {quickActionStatus && (
            <div className="mb-4 rounded-xl bg-[#F1F2F0] px-3 py-2 text-center text-xs font-semibold text-[#4e6700]">
              {quickActionStatus}
            </div>
          )}
          <div className="text-center">
            <span className="text-xs text-[#6F6F6F]">Or send a message via <a className="text-[#4e6700] hover:underline" href="#">Telegram</a></span>
          </div>
        </div>

        {/* Budget Progress Card */}
        <div className="bg-white p-6 rounded-[24px] card-shadow">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-base font-bold text-[#1a1c1b]">Budget Progress</h3>
            <button className="w-8 h-8 rounded-full hover:bg-[#F1F2F0] flex items-center justify-center transition-colors border-none cursor-pointer">
              <span className="material-symbols-outlined text-[#5f5e5e] text-[20px]">more_horiz</span>
            </button>
          </div>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between text-sm font-semibold text-[#1a1c1b] mb-2">
                <span>Makan</span>
                <span>Rp 2.5M / 3M</span>
              </div>
              <div className="h-3 w-full bg-[#F1F2F0] rounded-full overflow-hidden">
                <div className="h-full bg-[#c7ff00] rounded-full w-[83%]"></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm font-semibold text-[#1a1c1b] mb-2">
                <span>Transportasi</span>
                <span>Rp 800k / 1M</span>
              </div>
              <div className="h-3 w-full bg-[#F1F2F0] rounded-full overflow-hidden">
                <div className="h-full bg-[#4e6700]/60 rounded-full w-[80%]"></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm font-semibold text-[#1a1c1b] mb-2">
                <span>Belanja</span>
                <span className="text-[#EF6B6B]">Rp 1.2M / 1M</span>
              </div>
              <div className="h-3 w-full bg-[#F1F2F0] rounded-full overflow-hidden">
                <div className="h-full bg-[#EF6B6B] rounded-full w-[100%]"></div>
              </div>
              <div className="text-xs text-[#EF6B6B] mt-1 text-right">Over budget</div>
            </div>
          </div>
        </div>

        {/* Export Data Card */}
        <div className="bg-white p-6 rounded-[24px] card-shadow">
          <h3 className="text-base font-bold text-[#1a1c1b] mb-4">Export Data</h3>
          <p className="text-sm text-[#6F6F6F] mb-4">Download your transaction history for accounting purposes.</p>
          <div className="flex gap-3">
            <button onClick={handleDownloadPDF} disabled={isExporting} className="flex-1 border border-[#E8E8E8] text-[#1a1c1b] py-2 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-[#F1F2F0] transition-colors border-solid bg-transparent cursor-pointer">
              <span className="material-symbols-outlined text-[18px]">picture_as_pdf</span> {isExporting ? "PDF..." : "PDF"}
            </button>
            <button onClick={() => alert("CSV export is coming soon.")} className="flex-1 border border-[#E8E8E8] text-[#1a1c1b] py-2 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-[#F1F2F0] transition-colors border-solid bg-transparent cursor-pointer">
              <span className="material-symbols-outlined text-[18px]">table_view</span> CSV
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
