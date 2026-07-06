"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import type { CategoryResponse } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";

const ICON_MAP: Record<string, string> = {
  "Makanan": "restaurant",
  "Transportasi": "directions_car",
  "Tagihan": "receipt",
  "Belanja": "shopping_bag",
  "Hiburan": "movie",
  "Kesehatan": "medical_services",
  "Pendidikan": "school",
  "Gaji": "payments",
  "Uang Saku": "wallet",
  "Tabungan": "savings",
  "Lainnya": "more_horiz",
};

const COLOR_MAP: Record<string, string> = {
  "Makanan": "#FF6B6B",
  "Transportasi": "#F0B27A",
  "Tagihan": "#45B7D1",
  "Belanja": "#DDA0DD",
  "Hiburan": "#FFEAA7",
  "Kesehatan": "#82E0AA",
  "Pendidikan": "#AED6F1",
  "Gaji": "#96CEB4",
  "Uang Saku": "#BB8FCE",
  "Tabungan": "#4ECDC4",
  "Lainnya": "#D5D8DC",
};

const PALETTE_COLORS = [
  "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
  "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
  "#F0B27A", "#82E0AA", "#F1948A", "#AED6F1", "#D7BDE2",
];

const TYPE_LABELS: Record<string, string> = {
  expense: "Pengeluaran",
  income: "Pemasukan",
  both: "Keduanya",
};

function getCategoryIcon(cat: CategoryResponse): string {
  return cat.icon || ICON_MAP[cat.name] || "label";
}

function getCategoryColor(cat: CategoryResponse): string {
  return cat.color || COLOR_MAP[cat.name] || "#6F6F6F";
}

function formatRupiah(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function BudgetsTab() {
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryResponse | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState<"expense" | "income" | "both">("expense");
  const [formColor, setFormColor] = useState(PALETTE_COLORS[0]);
  const [formKeywords, setFormKeywords] = useState("");
  const [formBudgetLimit, setFormBudgetLimit] = useState("");
  const [formSaving, setFormSaving] = useState(false);

  useEffect(() => {
    loadCategories();
  }, []);

  async function loadCategories() {
    const token = getStoredAuthToken();
    if (!token) return;
    setLoading(true);
    try {
      const res = await apiClient.categories.list(token);
      setCategories(res.items);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }

  function openCreateModal() {
    setEditingCategory(null);
    setFormName("");
    setFormType("expense");
    setFormColor(PALETTE_COLORS[Math.floor(Math.random() * PALETTE_COLORS.length)]);
    setFormKeywords("");
    setFormBudgetLimit("");
    setIsModalOpen(true);
  }

  function openEditModal(cat: CategoryResponse) {
    if (cat.is_default) return;
    setEditingCategory(cat);
    setFormName(cat.name);
    setFormType(cat.type as "expense" | "income" | "both");
    setFormColor(getCategoryColor(cat));
    setFormKeywords((cat.keywords || []).join(", "));
    setFormBudgetLimit(cat.budget_limit ? String(cat.budget_limit) : "");
    setIsModalOpen(true);
  }

  async function handleSave() {
    const token = getStoredAuthToken();
    if (!token || !formName.trim()) return;
    setFormSaving(true);
    const keywords = formKeywords.split(",").map((k) => k.trim().toLowerCase()).filter(Boolean);
    const budgetLimitNum = formBudgetLimit ? parseFloat(formBudgetLimit) : null;

    try {
      if (editingCategory) {
        await apiClient.categories.update(token, editingCategory.id, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          keywords: keywords.length > 0 ? keywords : null,
          budget_limit: budgetLimitNum,
        });
      } else {
        await apiClient.categories.create(token, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          keywords: keywords.length > 0 ? keywords : null,
          budget_limit: budgetLimitNum,
        });
      }
      setIsModalOpen(false);
      await loadCategories();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        alert("Kategori dengan nama ini sudah ada.");
      } else {
        alert("Gagal menyimpan kategori.");
      }
    } finally {
      setFormSaving(false);
    }
  }

  async function handleDelete(cat: CategoryResponse) {
    const token = getStoredAuthToken();
    if (!token) return;
    try {
      await apiClient.categories.delete(token, cat.id);
      setDeleteConfirmId(null);
      await loadCategories();
    } catch {
      alert("Gagal menghapus kategori.");
    }
  }

  // Calculate totals
  const totalBudgeted = categories.reduce((sum, cat) => sum + (cat.budget_limit || 0), 0);
  const totalSpent = categories.reduce((sum, cat) => sum + (cat.spent_this_month || 0), 0);
  const totalRemaining = totalBudgeted - totalSpent;
  const isHealthy = totalRemaining >= 0;

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="max-w-[1200px] mx-auto">
        {/* Header Section */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h2 className="font-headline-hero text-[26px] md:text-[32px] font-bold text-[#191919] dark:text-white mb-2 tracking-[-0.02em]">
              Manage Your Budgets
            </h2>
            <p className="font-body-main text-[14px] text-[#5f5e5e] dark:text-[#9A9A9A]">
              Stay on track with your monthly spending limits.
            </p>
          </div>
          <button
            onClick={openCreateModal}
            className="hidden md:flex bg-[#c7ff00] text-[#191919] font-bold text-[13px] px-6 py-3 rounded-full hover:bg-opacity-90 transition-all active:scale-95 items-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            Set New Budget
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-white dark:bg-[#1a1c1b] rounded-[24px] p-6 shadow-sm hover:-translate-y-1 hover:shadow-md transition-all duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] dark:bg-[#2A2A2A] flex items-center justify-center text-[#5f5e5e] dark:text-[#c7ff00]">
                <span className="material-symbols-outlined">account_balance_wallet</span>
              </div>
              <span className="font-semibold text-[14px] text-[#5f5e5e] dark:text-[#9A9A9A]">Total Budgeted</span>
            </div>
            <div className="text-[32px] md:text-[42px] font-extrabold tracking-[-0.04em] text-[#191919] dark:text-white">
              {loading ? "..." : formatRupiah(totalBudgeted)}
            </div>
          </div>

          <div className="bg-[#191919] rounded-[28px] p-6 shadow-lg hover:-translate-y-1 hover:shadow-xl transition-all duration-300 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#c7ff00] opacity-10 rounded-full blur-2xl transform translate-x-1/2 -translate-y-1/2"></div>
            <div className="flex items-center justify-between mb-4 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#2A2A2A] flex items-center justify-center text-white">
                  <span className="material-symbols-outlined">savings</span>
                </div>
                <span className="font-semibold text-[14px] text-white opacity-80">Remaining</span>
              </div>
              <div className={`text-[12px] font-bold px-3 py-1 rounded-full ${isHealthy ? 'bg-[#c7ff00] text-[#587300]' : 'bg-[#EF6B6B] text-white'}`}>
                {isHealthy ? "Healthy" : "Overbudget"}
              </div>
            </div>
            <div className="text-[32px] md:text-[42px] font-extrabold tracking-[-0.04em] text-white relative z-10">
              {loading ? "..." : formatRupiah(totalRemaining)}
            </div>
          </div>

          <div className="bg-white dark:bg-[#1a1c1b] rounded-[24px] p-6 shadow-sm hover:-translate-y-1 hover:shadow-md transition-all duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] dark:bg-[#2A2A2A] flex items-center justify-center text-[#5f5e5e] dark:text-[#EF6B6B]">
                <span className="material-symbols-outlined">payments</span>
              </div>
              <span className="font-semibold text-[14px] text-[#5f5e5e] dark:text-[#9A9A9A]">Total Spent</span>
            </div>
            <div className="text-[32px] md:text-[42px] font-extrabold tracking-[-0.04em] text-[#191919] dark:text-white">
              {loading ? "..." : formatRupiah(totalSpent)}
            </div>
          </div>
        </div>

        {/* Mobile action button */}
        <div className="md:hidden mb-8">
            <button
              onClick={openCreateModal}
              className="w-full bg-[#c7ff00] text-[#191919] font-bold text-[14px] px-6 py-4 rounded-full flex items-center justify-center gap-2 shadow-md active:scale-95 transition-transform"
            >
              <span className="material-symbols-outlined text-[20px]">add</span>
              Set New Budget
            </button>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Budget List (Col 1-2) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-[20px] text-[#191919] dark:text-white">Categories</h3>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-2 border-[#c7ff00] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : categories.length === 0 ? (
               <div className="bg-white dark:bg-[#1a1c1b] rounded-[24px] p-12 text-center text-[#9E9E9E] text-sm shadow-sm">
                  Belum ada kategori. Klik &quot;Set New Budget&quot; untuk menambahkan.
               </div>
            ) : (
              <div className="space-y-4">
                {categories.map((cat) => {
                  const limit = cat.budget_limit || 0;
                  const spent = cat.spent_this_month || 0;
                  
                  let percent = limit > 0 ? Math.round((spent / limit) * 100) : 0;
                  if (percent > 100) percent = 100;

                  // Determine colors based on percent
                  let progressColorText = "text-[#6F6F6F] dark:text-[#9A9A9A]";
                  let progressBg = "bg-[#c7ff00]";
                  
                  if (percent >= 90) {
                      progressColorText = "text-[#EF6B6B]";
                      progressBg = "bg-[#EF6B6B]";
                  } else if (percent >= 75) {
                      progressColorText = "text-[#F6C85F]";
                      progressBg = "bg-[#F6C85F]";
                  }

                  // If no budget limit is set
                  const hasLimit = limit > 0;
                  const displaySpent = formatRupiah(spent);
                  const displayLimit = hasLimit ? `/ ${formatRupiah(limit)}` : "";
                  const displayPercent = hasLimit ? `${percent}% Used` : "No limit set";

                  return (
                    <div
                      key={cat.id}
                      onClick={() => !cat.is_default && openEditModal(cat)}
                      className={`bg-white dark:bg-[#1a1c1b] rounded-[24px] p-6 shadow-sm transition-all duration-300 ${!cat.is_default ? 'hover:-translate-y-1 hover:shadow-md cursor-pointer group' : ''}`}
                    >
                      <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-4">
                          <div
                            className="w-12 h-12 rounded-full flex items-center justify-center transition-transform group-hover:scale-105"
                            style={{ backgroundColor: `${getCategoryColor(cat)}20`, color: getCategoryColor(cat) }}
                          >
                            <span className="material-symbols-outlined icon-fill">{getCategoryIcon(cat)}</span>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                                <h4 className="font-semibold text-[15px] text-[#191919] dark:text-white">{cat.name}</h4>
                                {cat.is_default && (
                                    <span className="px-1.5 py-0.5 text-[9px] font-bold bg-[#F1F2F0] dark:bg-[#2A2A2A] text-[#9E9E9E] rounded-full uppercase tracking-wider">Default</span>
                                )}
                            </div>
                            <p className="text-[12px] font-normal text-[#5f5e5e] dark:text-[#9A9A9A]">{TYPE_LABELS[cat.type]}</p>
                          </div>
                        </div>
                        <div className="text-right flex flex-col items-end">
                          <div className="font-semibold text-[14px] text-[#191919] dark:text-white">
                            {displaySpent} <span className="text-[#5f5e5e] font-normal text-[14px]">{displayLimit}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                              {!cat.is_default && (
                                  <button
                                      onClick={(e) => { e.stopPropagation(); setDeleteConfirmId(cat.id); }}
                                      className="opacity-0 group-hover:opacity-100 p-0.5 text-[#D5D8DC] hover:text-[#EF6B6B] transition-all"
                                  >
                                      <span className="material-symbols-outlined text-[16px]">delete</span>
                                  </button>
                              )}
                              <p className={`text-[12px] font-medium ${progressColorText}`}>
                                {displayPercent}
                              </p>
                          </div>
                        </div>
                      </div>
                      
                      {/* Progress Bar */}
                      {hasLimit && (
                        <div className="w-full h-3 bg-[#F1F2F0] dark:bg-[#2A2A2A] rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${progressBg} transition-all duration-1000 ease-out`} style={{ width: `${percent}%` }}></div>
                        </div>
                      )}
                      
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Insights & Right Col */}
          <div className="space-y-6">
            <h3 className="font-bold text-[20px] text-[#191919] mb-4 opacity-0 hidden lg:block">Insights</h3>
            
            {/* Insight Card */}
            <div className="bg-[#F1F2F0] dark:bg-[#2f3130] rounded-[24px] p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-white dark:bg-black flex flex-shrink-0 items-center justify-center text-[#587300] dark:text-[#c7ff00] shadow-sm">
                  <span className="material-symbols-outlined">lightbulb</span>
                </div>
                <div>
                  <h4 className="font-semibold text-[15px] text-[#191919] dark:text-white mb-2">Budget Insights</h4>
                  <p className="text-[14px] text-[#5f5e5e] dark:text-[#c8c6c5] leading-relaxed">
                    Set a <strong>Budget Limit</strong> untuk kategori custom agar kamu bisa memantau pengeluaran dan mencegah <i>overbudget</i> setiap bulannya.
                  </p>
                </div>
              </div>
            </div>

             {/* Quick Add Card */}
             <div className="bg-white dark:bg-[#1a1c1b] rounded-[24px] p-6 shadow-sm border border-[#E8E8E8] dark:border-transparent">
              <h4 className="font-semibold text-[15px] text-[#191919] dark:text-white mb-4">Quick Action</h4>
              <p className="text-[14px] text-[#5f5e5e] dark:text-[#c8c6c5] mb-4">
                Tambah kategori baru dan atur limit untuk tracker otomatis.
              </p>
              <button
                onClick={openCreateModal}
                className="w-full py-3 bg-[#1a1c1b] dark:bg-white text-white dark:text-[#1a1c1b] rounded-full font-bold text-[13px] hover:bg-black transition-colors flex items-center justify-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">add</span>
                New Category
              </button>
            </div>
            
          </div>
        </div>
      </div>

      {/* ======= CREATE/EDIT MODAL ======= */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
          style={{ margin: 0 }}
          onClick={(e) => { if (e.target === e.currentTarget) setIsModalOpen(false); }}
        >
          <div className="bg-white dark:bg-[#1a1c1b] rounded-[28px] p-6 sm:p-8 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-[#1a1c1b] dark:text-white">
                {editingCategory ? "Edit Category" : "Set New Budget"}
              </h2>
              <button onClick={() => setIsModalOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#F1F2F0] dark:hover:bg-[#2A2A2A] transition-colors border-none bg-transparent cursor-pointer">
                <span className="material-symbols-outlined text-[#6F6F6F] dark:text-[#9A9A9A]">close</span>
              </button>
            </div>

            <div className="space-y-5">
              {/* Name */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] dark:text-[#9A9A9A] mb-1.5">Category Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="contoh: Pendidikan"
                  className="w-full bg-[#F1F2F0] dark:bg-[#2A2A2A] dark:text-white border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] outline-none"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] dark:text-[#9A9A9A] mb-1.5">Type</label>
                <div className="flex gap-2">
                  {(["expense", "income", "both"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFormType(t)}
                      className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border-none cursor-pointer ${
                        formType === t
                          ? "bg-[#1a1c1b] dark:bg-white text-white dark:text-[#1a1c1b]"
                          : "bg-[#F1F2F0] dark:bg-[#2A2A2A] text-[#6F6F6F] dark:text-[#9A9A9A] hover:bg-[#E8E8E8] dark:hover:bg-[#3f3f3f]"
                      }`}
                    >
                      {TYPE_LABELS[t]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Color */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] dark:text-[#9A9A9A] mb-1.5">Color</label>
                <div className="flex gap-2 flex-wrap">
                  {PALETTE_COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => setFormColor(c)}
                      className={`w-8 h-8 rounded-full transition-all border-none cursor-pointer ${
                        formColor === c ? "ring-2 ring-offset-2 ring-[#1a1c1b] dark:ring-white scale-110" : "hover:scale-105"
                      }`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
              
              {/* Budget Limit */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] dark:text-[#9A9A9A] mb-1.5">
                  Budget Limit <span className="font-normal text-[#BDBDBD]">(Opsional)</span>
                </label>
                <div className="relative">
                    <span className="absolute left-4 top-3 text-[14px] font-semibold text-[#BDBDBD]">Rp</span>
                    <input
                    type="number"
                    value={formBudgetLimit}
                    onChange={(e) => setFormBudgetLimit(e.target.value)}
                    placeholder="0"
                    min="0"
                    className="w-full bg-[#F1F2F0] dark:bg-[#2A2A2A] dark:text-white border-none rounded-xl py-3 pl-10 pr-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] outline-none"
                    />
                </div>
              </div>

              {/* Keywords */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] dark:text-[#9A9A9A] mb-1.5">
                  Auto-detect Keywords <span className="font-normal text-[#BDBDBD]">(pisah dengan koma)</span>
                </label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  placeholder="contoh: kuliah, tugas, kampus"
                  className="w-full bg-[#F1F2F0] dark:bg-[#2A2A2A] dark:text-white border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] outline-none"
                />
                <p className="text-[11px] text-[#BDBDBD] mt-1.5">
                  Bot akan otomatis mendeteksi kategori berdasarkan keyword ini
                </p>
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={!formName.trim() || formSaving}
              className="w-full mt-6 bg-[#1a1c1b] dark:bg-white hover:bg-black text-white dark:text-[#1a1c1b] py-3.5 rounded-full text-sm font-bold transition-colors border-none cursor-pointer shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {formSaving ? "Saving..." : editingCategory ? "Save Changes" : "Create Category"}
            </button>
          </div>
        </div>
      )}

      {/* ======= DELETE CONFIRM MODAL ======= */}
      {deleteConfirmId !== null && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" style={{ margin: 0 }}>
          <div className="bg-white dark:bg-[#1a1c1b] rounded-3xl p-8 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 mx-auto bg-red-100 text-[#EF6B6B]">
              <span className="material-symbols-outlined text-2xl">delete</span>
            </div>
            <h3 className="text-lg font-bold text-center text-[#1a1c1b] dark:text-white mb-2">Hapus Kategori?</h3>
            <p className="text-sm text-center text-[#6F6F6F] dark:text-[#9A9A9A] mb-8">
              Kategori &quot;{categories.find((c) => c.id === deleteConfirmId)?.name}&quot; akan dihapus. Transaksi yang sudah tercatat tidak akan berubah.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 py-3 rounded-full text-sm font-semibold bg-[#F1F2F0] dark:bg-[#2A2A2A] text-[#1a1c1b] dark:text-white hover:bg-[#E8E8E8] dark:hover:bg-[#3f3f3f] transition-colors border-none cursor-pointer"
              >
                Batal
              </button>
              <button
                onClick={() => {
                  const cat = categories.find((c) => c.id === deleteConfirmId);
                  if (cat) handleDelete(cat);
                }}
                className="flex-1 py-3 rounded-full text-sm font-semibold bg-[#EF6B6B] text-white hover:bg-red-600 transition-colors border-none cursor-pointer"
              >
                Hapus
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
