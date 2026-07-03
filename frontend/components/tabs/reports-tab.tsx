import { useState } from "react";
import type { Transaction } from "@/app/(dashboard)/types";

type ReportsTabProps = {
  transactions: Transaction[];
  categoryStats: { name: string; value: number; color: string }[];
  totalIncome: number;
  totalExpense: number;
  totalBalance: number;
  formatCurrency: (val: number) => string;
  handleDownloadPDF: () => void;
  isExporting: boolean;
};

export function ReportsTab({
  transactions,
  categoryStats,
  totalIncome,
  totalExpense,
  totalBalance,
  formatCurrency,
  handleDownloadPDF,
  isExporting,
}: ReportsTabProps) {
  const [isTimeDropdownOpen, setIsTimeDropdownOpen] = useState(false);
  const [selectedTime, setSelectedTime] = useState("Bulan Ini");
  const timeOptions = ["Hari Ini", "Minggu Ini", "Bulan Ini", "Custom"];

  const displayIncome = totalIncome;
  const displayExpense = totalExpense;
  const displayBalance = totalBalance;

  const savingRate = totalIncome > 0 ? Math.round((totalBalance / totalIncome) * 100) : 0;
  const savingRateClamped = Math.max(0, Math.min(100, savingRate));
  const strokeDash = `${(savingRateClamped / 100) * 100} 100`;

  const weeklyData = buildWeeklyData(transactions, formatCurrency);

  const categoryReportsList = transactions.length > 0 && categoryStats.length > 0
    ? categoryStats.map((c, i) => {
        const maxVal = Math.max(...categoryStats.map(x => x.value), 1);
        return {
          name: c.name,
          displayValue: formatCurrency(c.value),
          widthPercent: Math.round((c.value / maxVal) * 100),
          icon: c.name.toLowerCase() === "makanan" ? "restaurant" : c.name.toLowerCase() === "transportasi" ? "commute" : c.name.toLowerCase() === "tagihan" ? "receipt" : "shopping_bag",
          colorClass: i === 0 ? "bg-[#c7ff00]" : i === 1 ? "bg-[#2A2A2A]" : "bg-neutral-300"
        };
      })
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-row justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-[#1a1c1b]">Financial Report</h2>
        <div className="relative">
          <button 
            onClick={() => setIsTimeDropdownOpen(!isTimeDropdownOpen)}
            className="flex items-center gap-2 bg-white border-none shadow-sm text-[#1a1c1b] font-semibold py-2.5 pl-4 pr-3 rounded-full focus:ring-1 focus:ring-[#c7ff00] cursor-pointer transition-shadow hover:shadow-md text-xs"
          >
            {selectedTime}
            <span className={`material-symbols-outlined text-[#6F6F6F] text-base transition-transform ${isTimeDropdownOpen ? 'rotate-180' : ''}`}>
              expand_more
            </span>
          </button>
          
          {isTimeDropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-36 bg-white rounded-2xl shadow-lg border border-[#E8E8E8] py-2 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
              {timeOptions.map((opt) => (
                <button
                  key={opt}
                  onClick={() => {
                    setSelectedTime(opt);
                    setIsTimeDropdownOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2.5 text-xs font-semibold hover:bg-[#F1F2F0] transition-colors cursor-pointer border-none bg-transparent ${selectedTime === opt ? 'text-[#4e6700]' : 'text-[#1a1c1b]'}`}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-6 items-stretch">
            <div className="bg-white rounded-[24px] p-4 sm:p-6 card-shadow hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 mb-2 sm:mb-4">
                <div className="w-8 h-8 sm:w-10 sm:h-10 shrink-0 rounded-full bg-[#5FCF6A]/10 flex items-center justify-center text-[#5FCF6A]">
                  <span className="material-symbols-outlined text-[16px] sm:text-[20px]">arrow_downward</span>
                </div>
                <span className="text-[11px] sm:text-sm font-semibold text-[#6F6F6F] leading-tight">Total Pemasukan</span>
              </div>
              <div className="text-[15px] sm:text-2xl font-bold text-[#1a1c1b] mb-2 truncate">{formatCurrency(displayIncome)}</div>
              <div className="inline-flex items-center gap-1 bg-[#5FCF6A]/10 text-[#5FCF6A] px-2 py-0.5 rounded-full text-[10px] sm:text-[11px] font-semibold w-fit">
                <span className="material-symbols-outlined text-[11px] sm:text-[13px]">trending_up</span> +12%
              </div>
            </div>

            <div className="bg-white rounded-[24px] p-4 sm:p-6 card-shadow hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 mb-2 sm:mb-4">
                <div className="w-8 h-8 sm:w-10 sm:h-10 shrink-0 rounded-full bg-[#EF6B6B]/10 flex items-center justify-center text-[#EF6B6B]">
                  <span className="material-symbols-outlined text-[16px] sm:text-[20px]">arrow_upward</span>
                </div>
                <span className="text-[11px] sm:text-sm font-semibold text-[#6F6F6F] leading-tight">Total Pengeluaran</span>
              </div>
              <div className="text-[15px] sm:text-2xl font-bold text-[#1a1c1b] mb-2 truncate">{formatCurrency(displayExpense)}</div>
              <div className="inline-flex items-center gap-1 bg-[#5FCF6A]/10 text-[#5FCF6A] px-2 py-0.5 rounded-full text-[10px] sm:text-[11px] font-semibold w-fit">
                <span className="material-symbols-outlined text-[11px] sm:text-[13px]">trending_down</span> -5%
              </div>
            </div>

            <div className="col-span-2 md:col-span-1 bg-[#2A2A2A] rounded-[28px] p-5 sm:p-6 card-shadow text-white relative overflow-hidden group flex flex-col justify-between min-h-[160px] sm:min-h-[180px]">
              <div className="absolute -right-10 -top-10 w-32 h-32 bg-[#c7ff00]/10 rounded-full blur-2xl group-hover:scale-150 transition-transform duration-700"></div>
              <span className="text-[11px] sm:text-xs text-neutral-300 opacity-80 block mb-1">Sisa Saldo (Tabungan)</span>
              <div className="text-xl sm:text-2xl font-extrabold text-[#c7ff00] mb-3 tracking-tight truncate">{formatCurrency(displayBalance)}</div>
              
              <div className="flex items-center gap-2 sm:gap-3 bg-[#1A1A1A] rounded-2xl p-2 sm:p-2.5 border border-white/5 relative z-10 w-full mt-auto">
                <div className="relative w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center flex-shrink-0">
                  <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                    <circle className="text-neutral-700" cx="18" cy="18" r="16" fill="transparent" stroke="currentColor" strokeWidth="3" />
                    <circle className="text-[#c7ff00]" cx="18" cy="18" r="16" fill="transparent" stroke="currentColor" strokeWidth="3" strokeDasharray={strokeDash} strokeLinecap="round" />
                  </svg>
                  <span className="absolute text-[9px] sm:text-[10px] font-bold text-white">{savingRateClamped}%</span>
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] sm:text-[11px] font-semibold text-white truncate">Saving Rate</div>
                  <div className="text-[8px] sm:text-[9px] text-neutral-400 truncate">Dari data transaksi</div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[24px] p-6 card-shadow">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-sm font-bold text-[#1a1c1b]">Money Flow</h3>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded-full bg-[#c7ff00]" /><span className="text-xs text-[#6F6F6F]">Income</span></div>
                <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded-full bg-neutral-300" /><span className="text-xs text-[#6F6F6F]">Expense</span></div>
              </div>
            </div>

            <div className="h-60 flex items-end justify-between px-2 gap-2 mt-4 border-b border-[#E8E8E8] pb-2 relative">
              <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-[10px] text-[#6F6F6F] opacity-50 pb-2 pointer-events-none">
                <span>20M</span>
                <span>15M</span>
                <span>10M</span>
                <span>5M</span>
                <span>0</span>
              </div>

              <div className="w-full h-full flex items-end justify-around ml-8">
                {weeklyData.map((w, idx) => (
                  <div key={idx} className="flex items-end gap-1.5 group h-full">
                    <div className="w-6 md:w-8 rounded-t-lg bg-[#c7ff00] hover:opacity-90 transition-opacity relative" style={{ height: `${w.incomeHeight}%` }}>
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-[#2A2A2A] text-white text-[9px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">{w.income}</div>
                    </div>
                    <div className="w-6 md:w-8 rounded-t-lg bg-neutral-200 hover:bg-neutral-300 transition-colors relative" style={{ height: `${w.expenseHeight}%` }}>
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-[#2A2A2A] text-white text-[9px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">{w.expense}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-around ml-8 mt-3 text-xs text-[#6F6F6F] font-semibold">
              {weeklyData.map((w, idx) => (
                <span key={idx}>{w.label}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-4 space-y-6">
          <div className="bg-[#F1F2F0] rounded-[24px] p-5 border border-white relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#c7ff00]/10 rounded-bl-full pointer-events-none"></div>
            <div className="flex items-start gap-4 relative z-10">
              <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center shrink-0 shadow-sm relative">
                <span className="material-symbols-outlined text-[#4e6700] text-[24px]">smart_toy</span>
                <div className="absolute top-0 right-0 w-3 h-3 bg-[#c7ff00] rounded-full border-2 border-white animate-pulse"></div>
              </div>
              <div>
                <h4 className="text-sm font-bold text-[#1a1c1b] mb-1">Sakoo Insight</h4>
                <p className="text-xs text-[#6F6F6F] leading-relaxed">
                  {categoryStats[0]
                    ? <>Kategori pengeluaran terbesar: <strong className="text-[#1a1c1b]">{categoryStats[0].name}</strong>.</>
                    : "Belum ada transaksi untuk dibuat insight."}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[24px] card-shadow flex flex-col justify-between overflow-hidden">
            <div>
              <div className="px-6 py-5 border-b border-[#E8E8E8]">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Spending by Category</h3>
              </div>
              <div className="divide-y divide-[#E8E8E8]/50">
                {categoryReportsList.map((c, i) => (
                  <div key={i} className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group">
                    <div className="flex justify-between items-center mb-3">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F] transition-all group-hover:bg-white group-hover:shadow-sm">
                          <span className="material-symbols-outlined text-[20px]">{c.icon}</span>
                        </div>
                        <div>
                          <span className="text-sm font-semibold text-[#1a1c1b] block">{c.name}</span>
                          <span className="text-xs text-[#6F6F6F] mt-0.5 block">{c.widthPercent}% of total</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[15px] font-bold text-[#1a1c1b]">{c.displayValue}</span>
                      </div>
                    </div>
                    <div className="w-full bg-[#F1F2F0] rounded-full h-2">
                      <div className={`${c.colorClass} h-2 rounded-full`} style={{ width: `${c.widthPercent}%` }}></div>
                    </div>
                  </div>
                ))}
                {categoryReportsList.length === 0 && (
                  <p className="text-xs text-[#6F6F6F]">Belum ada pengeluaran.</p>
                )}
              </div>
            </div>

            <div className="p-6 pt-2">
              <button className="w-full py-2.5 border border-[#E8E8E8] text-[#1a1c1b] text-xs font-semibold rounded-full hover:bg-[#F1F2F0] transition-colors border-solid bg-transparent cursor-pointer">
                View All Categories
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="w-full">
        <h3 className="text-sm font-bold text-[#1a1c1b] mb-4 text-center md:text-left">Export Options</h3>
        <div className="flex flex-wrap justify-center md:justify-start gap-3">
          <button onClick={handleDownloadPDF} disabled={isExporting} className="bg-[#2A2A2A] text-white px-5 py-2.5 rounded-full text-xs font-semibold flex items-center gap-1.5 hover:opacity-90 transition-opacity border-none cursor-pointer">
            <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
            {isExporting ? "Export PDF..." : "Export PDF"}
          </button>
          <button onClick={() => alert("CSV export is coming soon.")} className="bg-white border border-[#E8E8E8] text-[#1a1c1b] px-5 py-2.5 rounded-full text-xs font-semibold flex items-center gap-1.5 hover:bg-[#F1F2F0] transition-colors border-solid bg-transparent cursor-pointer">
            <span className="material-symbols-outlined text-[16px]">download</span>
            CSV
          </button>
          <button onClick={() => alert("Share option coming soon.")} className="bg-[#c7ff00] text-[#151f00] px-5 py-2.5 rounded-full text-xs font-semibold flex items-center gap-1.5 hover:opacity-95 transition-opacity border-none cursor-pointer">
            <span className="material-symbols-outlined text-[16px]">share</span>
            Share
          </button>
        </div>
      </div>
    </div>
  );
}

function buildWeeklyData(
  transactions: Transaction[],
  formatCurrency: (val: number) => string,
) {
  const weeks = Array.from({ length: 4 }, (_, index) => ({
    label: `W${index + 1}`,
    incomeValue: 0,
    expenseValue: 0,
  }));
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();

  transactions.forEach((transaction) => {
    const date = new Date(transaction.transaction_date);
    if (date.getMonth() !== currentMonth || date.getFullYear() !== currentYear) {
      return;
    }

    const weekIndex = Math.min(3, Math.floor((date.getDate() - 1) / 7));
    if (transaction.type === "income") {
      weeks[weekIndex].incomeValue += transaction.amount;
    } else {
      weeks[weekIndex].expenseValue += transaction.amount;
    }
  });

  const max = Math.max(
    ...weeks.map((week) => Math.max(week.incomeValue, week.expenseValue)),
    1,
  );

  return weeks.map((week) => ({
    label: week.label,
    income: formatCurrency(week.incomeValue),
    expense: formatCurrency(week.expenseValue),
    incomeHeight: barHeight(week.incomeValue, max),
    expenseHeight: barHeight(week.expenseValue, max),
  }));
}

function barHeight(value: number, max: number): number {
  if (value <= 0) return 4;
  return Math.max(8, Math.round((value / max) * 100));
}
