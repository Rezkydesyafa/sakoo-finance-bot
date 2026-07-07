"use client";

import { useState, useEffect } from "react";
import { apiClient, BudgetListResponse, BudgetItemResponse } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";
import { SetBudgetModal } from "@/components/set-budget-modal";

export function BudgetsTab() {
  const [budgetData, setBudgetData] = useState<BudgetListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<{ categoryId: number; amount: number } | null>(null);

  const fetchBudgets = async () => {
    setIsLoading(true);
    const token = getStoredAuthToken();
    if (token) {
      try {
        const data = await apiClient.budgets.list(token);
        setBudgetData(data);
      } catch (err) {
        console.error("Failed to fetch budgets:", err);
      }
    }
    setIsLoading(false);
  };

  useEffect(() => {
    fetchBudgets();
  }, []);

  const handleOpenNewBudget = () => {
    setEditingBudget(null);
    setIsModalOpen(true);
  };

  const handleOpenEditBudget = (item: BudgetItemResponse) => {
    setEditingBudget({
      categoryId: item.category_id,
      amount: Number(item.monthly_limit),
    });
    setIsModalOpen(true);
  };

  const handleDeleteBudget = async (categoryId: number) => {
    if (confirm("Apakah Anda yakin ingin menghapus limit budget ini?")) {
      const token = getStoredAuthToken();
      if (token) {
        try {
          await apiClient.budgets.remove(token, categoryId);
          fetchBudgets();
        } catch (err) {
          console.error(err);
          alert("Gagal menghapus budget.");
        }
      }
    }
  };

  const handleModalSave = () => {
    setIsModalOpen(false);
    fetchBudgets();
  };

  function formatCurrency(val: number | string) {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(Number(val));
  }

  function getCategoryIcon(name: string) {
    const n = name.toLowerCase();
    if (n.includes("makan")) return "restaurant";
    if (n.includes("transport")) return "directions_car";
    if (n.includes("belanja")) return "shopping_bag";
    if (n.includes("hiburan")) return "movie";
    if (n.includes("tagihan") || n.includes("listrik") || n.includes("internet")) return "receipt";
    if (n.includes("kesehatan")) return "medical_services";
    return "category";
  }

  const getStatusColor = (status: string) => {
    if (status === "exceeded") return "bg-danger-red";
    if (status === "warning") return "bg-warning-amber";
    return "bg-[#c7ff00]"; // healthy
  };

  const getStatusTextColor = (status: string) => {
    if (status === "exceeded") return "text-danger-red";
    if (status === "warning") return "text-warning-amber";
    return "text-[#6F6F6F]"; // healthy text (fallback)
  };

  // Find worst status for insights
  const worstStatusItem = budgetData?.items?.slice().sort((a, b) => Number(b.usage_percentage) - Number(a.usage_percentage))[0];

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="hidden md:block max-w-container-max mx-auto">
        {/* Header Section */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h2 className="font-headline-hero text-headline-hero text-text-primary mb-2 dark:text-white">Manage Your Budgets</h2>
            <p className="font-body-main text-body-main text-text-muted">Stay on track with your monthly spending limits.</p>
          </div>
          <button onClick={handleOpenNewBudget} className="bg-primary-container text-on-primary-container font-label-button text-label-button px-6 py-3 rounded-full hover:opacity-90 transition-all active:scale-95 flex items-center gap-2 border-none cursor-pointer">
            <span className="material-symbols-outlined text-[18px]">add</span>
            Set New Budget
          </button>
        </div>
        
        {isLoading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 rounded-full border-4 border-[#F1F2F0] border-t-[#c7ff00] animate-spin"></div>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
              <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                    <span className="material-symbols-outlined text-[20px]">account_balance_wallet</span>
                  </div>
                  <span className="text-sm font-semibold text-[#6F6F6F]">Total Budgeted</span>
                </div>
                <div className="text-2xl font-bold text-[#1a1c1b]">
                  {formatCurrency(budgetData?.total_budgeted || 0)}
                </div>
              </div>
              
              <div className="bg-[#2A2A2A] rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-[#c7ff00] opacity-10 rounded-full blur-2xl transform translate-x-1/2 -translate-y-1/2"></div>
                <div className="flex items-center justify-between mb-4 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#1a1c1b] flex items-center justify-center text-white">
                      <span className="material-symbols-outlined text-[20px]">savings</span>
                    </div>
                    <span className="text-sm font-semibold text-white opacity-80">Remaining</span>
                  </div>
                  <div className={`text-[11px] font-bold px-3 py-1 rounded-full ${
                    Number(budgetData?.total_remaining) < 0 ? 'bg-danger-red text-white' : 'bg-[#c7ff00] text-[#151f00]'
                  }`}>
                    {Number(budgetData?.total_remaining) < 0 ? 'Exceeded' : 'Healthy'}
                  </div>
                </div>
                <div className="text-2xl font-bold text-white relative z-10">
                  {formatCurrency(budgetData?.total_remaining || 0)}
                </div>
              </div>
              
              <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                    <span className="material-symbols-outlined text-[20px]">shopping_cart</span>
                  </div>
                  <span className="text-sm font-semibold text-[#6F6F6F]">Total Spent</span>
                </div>
                <div className="text-2xl font-bold text-[#1a1c1b]">
                  {formatCurrency(budgetData?.total_spent || 0)}
                </div>
              </div>
            </div>
            
            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
              {/* Budget List (Col 1-2) */}
              <div className="lg:col-span-2 space-y-stack-md">
                <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4">Categories</h3>
                
                <div className="bg-white rounded-[24px] card-shadow flex flex-col overflow-hidden">
                  <div className="px-6 py-5 bg-white border-b border-[#E8E8E8]">
                    <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Budget Allocation</h3>
                  </div>
                  <div className="divide-y divide-[#E8E8E8]/50">
                    {!budgetData?.items?.length && (
                      <div className="p-8 text-center text-[#6F6F6F]">
                        <span className="material-symbols-outlined text-4xl mb-2 opacity-50">account_balance_wallet</span>
                        <p className="text-sm font-medium mb-4">Anda belum mengatur limit budget untuk kategori apapun.</p>
                        <button onClick={handleOpenNewBudget} className="bg-[#c7ff00] text-[#151f00] px-6 py-2 rounded-full font-bold text-sm border-none cursor-pointer">Set Budget Pertama</button>
                      </div>
                    )}
                    
                    {budgetData?.items?.map(item => (
                      <div key={item.category_id} className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group">
                        <div className="flex justify-between items-center mb-3">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#6F6F6F] transition-all group-hover:bg-white group-hover:shadow-sm">
                              <span className="material-symbols-outlined icon-fill">{getCategoryIcon(item.category_name)}</span>
                            </div>
                            <div>
                              <span className="text-sm font-semibold text-[#1a1c1b] block">{item.category_name}</span>
                              <div className="flex gap-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button onClick={() => handleOpenEditBudget(item)} className="text-xs text-[#1a1c1b] bg-[#E8E8E8] hover:bg-[#D1D1D1] px-2 py-0.5 rounded cursor-pointer border-none flex items-center gap-1">
                                  <span className="material-symbols-outlined text-[14px]">edit</span> Edit
                                </button>
                                <button onClick={() => handleDeleteBudget(item.category_id)} className="text-xs text-danger-red bg-red-50 hover:bg-red-100 px-2 py-0.5 rounded cursor-pointer border-none flex items-center gap-1">
                                  <span className="material-symbols-outlined text-[14px]">delete</span> Delete
                                </button>
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-[15px] font-bold text-[#1a1c1b]">
                              {formatCurrency(item.spent)} <span className="text-text-muted font-normal text-xs">/ {formatCurrency(item.monthly_limit)}</span>
                            </div>
                            <p className={`text-[11px] font-semibold mt-1 ${getStatusTextColor(item.status)}`}>
                              {Number(item.usage_percentage).toFixed(0)}% Used
                            </p>
                          </div>
                        </div>
                        <div className="w-full h-2 bg-[#F1F2F0] rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${getStatusColor(item.status)}`} 
                            style={{ width: `${Math.min(100, Number(item.usage_percentage))}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* Insights & Right Col */}
              <div className="space-y-stack-md">
                <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4 opacity-0 hidden lg:block">Insights</h3>
                
                {/* Insight Card */}
                {worstStatusItem && Number(worstStatusItem.usage_percentage) > 50 && (
                  <div className="bg-surface-muted dark:bg-inverse-surface rounded-[24px] p-6">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-full bg-surface-white dark:bg-black flex flex-shrink-0 items-center justify-center text-primary-container shadow-sm">
                        <span className="material-symbols-outlined">lightbulb</span>
                      </div>
                      <div>
                        <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-2">Budget Insights</h4>
                        <p className="font-body-main text-body-main text-text-muted leading-relaxed">
                          Your <strong>{worstStatusItem.category_name}</strong> budget is {Number(worstStatusItem.usage_percentage).toFixed(0)}% used. Consider slowing down spending in this category to stay on track.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Placeholder Upcoming Bills */}
                <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-6 card-shadow">
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-4">Upcoming Bills</h4>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-[14px] bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                          <span className="material-symbols-outlined">wifi</span>
                        </div>
                        <div>
                          <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Internet</div>
                          <div className="font-label-muted text-label-muted text-text-muted">In 3 days</div>
                        </div>
                      </div>
                      <div className="font-body-strong text-body-strong text-text-primary dark:text-white">Rp350.000</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
      
      {/* =======================
          MOBILE VIEW (md:hidden)
          ======================= */}
      <div className="md:hidden space-y-stack-lg relative w-full pt-4 pb-20">
        <div className="ambient-glow"></div>
        
        {isLoading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 rounded-full border-4 border-[#F1F2F0] border-t-[#c7ff00] animate-spin"></div>
          </div>
        ) : (
          <>
            {/* Header: Total Remaining */}
            <section className="text-center space-y-stack-sm relative z-10">
              <p className="font-label-muted text-label-muted text-text-muted">Total Remaining Budget</p>
              <h2 className="font-headline-hero text-3xl font-bold text-text-primary dark:text-white tracking-tight">
                {formatCurrency(budgetData?.total_remaining || 0)}
              </h2>
              <div className="flex justify-center pt-4">
                <button onClick={handleOpenNewBudget} className="h-14 bg-primary-container rounded-full flex items-center justify-center text-text-primary shadow-lg hover:scale-105 active:scale-95 transition-transform px-8 border-none cursor-pointer">
                  <span className="material-symbols-outlined text-[28px]">add</span>
                </button>
              </div>
            </section>
            
            {/* Quick Stats Grid */}
            <section className="grid grid-cols-2 gap-stack-md">
              <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
                <div className="flex items-center gap-2 text-text-muted">
                  <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                    <span className="material-symbols-outlined text-[14px]">account_balance</span>
                  </div>
                  <span className="font-label-muted text-label-muted">Budget</span>
                </div>
                <p className="font-title-card text-title-card text-text-primary dark:text-white">
                  {formatCurrency(budgetData?.total_budgeted || 0)}
                </p>
              </div>
              
              <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
                <div className="flex items-center gap-2 text-text-muted">
                  <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                    <span className="material-symbols-outlined text-[14px]">shopping_cart</span>
                  </div>
                  <span className="font-label-muted text-label-muted">Spent</span>
                </div>
                <p className="font-title-card text-title-card text-text-primary dark:text-white">
                  {formatCurrency(budgetData?.total_spent || 0)}
                </p>
              </div>
            </section>
            
            {/* Budget Category List */}
            <section className="space-y-stack-md">
              <div className="flex items-center justify-between pb-2">
                <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white">Categories</h3>
              </div>
              
              {!budgetData?.items?.length ? (
                <div className="bg-white rounded-[24px] p-6 card-shadow text-center">
                  <p className="text-sm text-[#6F6F6F]">Belum ada budget diset.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {budgetData.items.map(item => (
                    <div key={item.category_id} onClick={() => handleOpenEditBudget(item)} className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between cursor-pointer">
                      <div className="flex flex-col gap-2 mb-4">
                        <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center text-text-primary dark:text-white">
                          <span className="material-symbols-outlined icon-fill">{getCategoryIcon(item.category_name)}</span>
                        </div>
                        <div>
                          <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">{item.category_name}</h4>
                          <p className={`font-label-muted text-label-muted ${getStatusTextColor(item.status)}`}>
                            {100 - Number(item.usage_percentage)}% left
                          </p>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between items-end">
                          <p className={`font-title-card text-title-card ${item.status === 'exceeded' ? 'text-danger-red' : 'text-text-primary dark:text-white'}`}>
                            Rp{(Number(item.spent) / 1000).toFixed(0)}k
                          </p>
                          <p className="font-label-muted text-label-muted text-text-muted text-[10px]">
                            / {(Number(item.monthly_limit) / 1000).toFixed(0)}k
                          </p>
                        </div>
                        <div className="w-full h-2 bg-surface-muted dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${getStatusColor(item.status)}`} 
                            style={{ width: `${Math.min(100, Number(item.usage_percentage))}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      <SetBudgetModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleModalSave}
        initialCategoryId={editingBudget?.categoryId}
        initialAmount={editingBudget?.amount}
      />
    </div>
  );
}
