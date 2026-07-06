"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import type { CategoryResponse, CategoryCreateRequest } from "@/lib/api";
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
    setIsModalOpen(true);
  }

  function openEditModal(cat: CategoryResponse) {
    if (cat.is_default) return;
    setEditingCategory(cat);
    setFormName(cat.name);
    setFormType(cat.type as "expense" | "income" | "both");
    setFormColor(getCategoryColor(cat));
    setFormKeywords((cat.keywords || []).join(", "));
    setIsModalOpen(true);
  }

  async function handleSave() {
    const token = getStoredAuthToken();
    if (!token || !formName.trim()) return;
    setFormSaving(true);
    const keywords = formKeywords.split(",").map((k) => k.trim().toLowerCase()).filter(Boolean);

    try {
      if (editingCategory) {
        await apiClient.categories.update(token, editingCategory.id, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          keywords: keywords.length > 0 ? keywords : null,
        });
      } else {
        await apiClient.categories.create(token, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          keywords: keywords.length > 0 ? keywords : null,
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

  const expenseCategories = categories.filter((c) => c.type === "expense" || c.type === "both");
  const incomeCategories = categories.filter((c) => c.type === "income" || c.type === "both");
  const customCategories = categories.filter((c) => !c.is_default);

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* ======= DESKTOP ======= */}
      <div className="hidden md:block max-w-container-max mx-auto">
        {/* Header */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h2 className="font-headline-hero text-headline-hero text-text-primary mb-2 dark:text-white">Manage Your Budgets</h2>
            <p className="font-body-main text-body-main text-text-muted">Stay on track with your monthly spending limits.</p>
          </div>
          <button
            onClick={openCreateModal}
            className="bg-primary-container text-on-primary-container font-label-button text-label-button px-6 py-3 rounded-full hover:opacity-90 transition-all active:scale-95 flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            Set New Budget
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                <span className="material-symbols-outlined text-[20px]">category</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">Total Categories</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">{loading ? "..." : categories.length}</div>
          </div>

          <div className="bg-[#2A2A2A] rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#c7ff00] opacity-10 rounded-full blur-2xl transform translate-x-1/2 -translate-y-1/2"></div>
            <div className="flex items-center gap-3 mb-4 relative z-10">
              <div className="w-10 h-10 rounded-full bg-[#1a1c1b] flex items-center justify-center text-white">
                <span className="material-symbols-outlined text-[20px]">trending_down</span>
              </div>
              <span className="text-sm font-semibold text-white opacity-80">Expense Categories</span>
            </div>
            <div className="text-2xl font-bold text-white relative z-10">{loading ? "..." : expenseCategories.length}</div>
          </div>

          <div className="bg-white rounded-[24px] p-6 card-shadow flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center text-[#5f5e5e]">
                <span className="material-symbols-outlined text-[20px]">trending_up</span>
              </div>
              <span className="text-sm font-semibold text-[#6F6F6F]">Income Categories</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1c1b]">{loading ? "..." : incomeCategories.length}</div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
          {/* Category List (Col 1-2) */}
          <div className="lg:col-span-2 space-y-stack-md">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4">Categories</h3>

            {/* Budget Allocation Table */}
            <div className="bg-white rounded-[24px] card-shadow flex flex-col overflow-hidden">
              <div className="px-6 py-5 bg-white border-b border-[#E8E8E8] flex items-center justify-between">
                <h3 className="text-[15px] font-semibold text-[#1a1c1b]">Budget Allocation</h3>
                {customCategories.length > 0 && (
                  <span className="text-xs text-[#9E9E9E]">{customCategories.length} custom</span>
                )}
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-7 h-7 border-2 border-[#c7ff00] border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <div className="divide-y divide-[#E8E8E8]/50">
                  {categories.map((cat) => (
                    <div
                      key={cat.id}
                      className="px-6 py-4 hover:bg-[#F1F2F0]/30 transition-colors group cursor-pointer"
                      onClick={() => !cat.is_default && openEditModal(cat)}
                    >
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4">
                          <div
                            className="w-12 h-12 rounded-full flex items-center justify-center transition-all group-hover:shadow-sm"
                            style={{ backgroundColor: `${getCategoryColor(cat)}20`, color: getCategoryColor(cat) }}
                          >
                            <span className="material-symbols-outlined icon-fill">{getCategoryIcon(cat)}</span>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-[#1a1c1b] block">{cat.name}</span>
                              {cat.is_default && (
                                <span className="px-1.5 py-0.5 text-[9px] font-bold bg-[#F1F2F0] text-[#9E9E9E] rounded-full uppercase tracking-wider">Default</span>
                              )}
                              {!cat.is_default && (
                                <span className="px-1.5 py-0.5 text-[9px] font-bold rounded-full uppercase tracking-wider" style={{ backgroundColor: `${getCategoryColor(cat)}20`, color: getCategoryColor(cat) }}>Custom</span>
                              )}
                            </div>
                            <span className="text-xs text-[#6F6F6F] mt-0.5 block">{TYPE_LABELS[cat.type] || cat.type}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Keywords preview */}
                          {(cat.keywords || []).length > 0 && (
                            <div className="hidden lg:flex gap-1 mr-2">
                              {(cat.keywords || []).slice(0, 3).map((kw) => (
                                <span key={kw} className="px-2 py-0.5 text-[10px] bg-[#F5F5F5] text-[#757575] rounded-full">{kw}</span>
                              ))}
                              {(cat.keywords || []).length > 3 && (
                                <span className="text-[10px] text-[#9E9E9E]">+{(cat.keywords || []).length - 3}</span>
                              )}
                            </div>
                          )}

                          {/* Action buttons for custom categories */}
                          {!cat.is_default && (
                            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => { e.stopPropagation(); openEditModal(cat); }}
                                className="p-1.5 rounded-lg hover:bg-[#F5F5F5] text-[#9E9E9E] hover:text-[#1a1c1b] transition-all"
                                title="Edit"
                              >
                                <span className="material-symbols-outlined text-[18px]">edit</span>
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); setDeleteConfirmId(cat.id); }}
                                className="p-1.5 rounded-lg hover:bg-red-50 text-[#9E9E9E] hover:text-red-500 transition-all"
                                title="Hapus"
                              >
                                <span className="material-symbols-outlined text-[18px]">delete</span>
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {categories.length === 0 && (
                    <div className="px-6 py-12 text-center text-[#9E9E9E] text-sm">
                      Belum ada kategori. Klik &quot;Set New Budget&quot; untuk menambahkan.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Tips */}
          <div className="space-y-stack-md">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white mb-4 opacity-0 hidden lg:block">Insights</h3>

            {/* Insight Card */}
            <div className="bg-surface-muted dark:bg-inverse-surface rounded-[24px] p-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-white dark:bg-black flex flex-shrink-0 items-center justify-center text-primary-container shadow-sm">
                  <span className="material-symbols-outlined">lightbulb</span>
                </div>
                <div>
                  <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-2">Budget Insights</h4>
                  <p className="font-body-main text-body-main text-text-muted leading-relaxed">
                    Buat kategori custom seperti &quot;Pendidikan&quot; atau &quot;Subscription&quot; lalu tambahkan <strong>keywords</strong> agar bot otomatis mendeteksi kategori dari pesan kamu.
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Add Card */}
            <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-6 card-shadow">
              <h4 className="font-title-card text-title-card text-text-primary dark:text-white mb-4">Quick Add Category</h4>
              <p className="font-body-main text-body-main text-text-muted mb-4">
                Tambah kategori baru untuk tracking pengeluaran atau pemasukan secara lebih detail.
              </p>
              <button
                onClick={openCreateModal}
                className="w-full py-3 bg-[#1a1c1b] text-white rounded-full font-label-button text-label-button hover:bg-black transition-colors flex items-center justify-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">add</span>
                New Category
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ======= MOBILE ======= */}
      <div className="md:hidden space-y-stack-lg relative w-full pt-4 pb-20">
        <div className="ambient-glow"></div>

        {/* Header */}
        <section className="text-center space-y-stack-sm relative z-10">
          <p className="font-label-muted text-label-muted text-text-muted">Total Categories</p>
          <h2 className="font-headline-hero text-3xl font-bold text-text-primary dark:text-white tracking-tight">{loading ? "..." : categories.length}</h2>
          <div className="flex justify-center pt-4">
            <button
              onClick={openCreateModal}
              className="h-14 bg-primary-container rounded-full flex items-center justify-center text-text-primary shadow-lg hover:scale-105 active:scale-95 transition-transform px-8"
            >
              <span className="material-symbols-outlined text-[28px]">add</span>
            </button>
          </div>
        </section>

        {/* Quick Stats */}
        <section className="grid grid-cols-2 gap-stack-md">
          <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                <span className="material-symbols-outlined text-[14px]">trending_down</span>
              </div>
              <span className="font-label-muted text-label-muted">Expense</span>
            </div>
            <p className="font-title-card text-title-card text-text-primary dark:text-white">{expenseCategories.length} kategori</p>
          </div>

          <div className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow flex flex-col justify-between h-[100px]">
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-6 h-6 rounded-full bg-surface-muted dark:bg-[#2A2A2A] flex items-center justify-center">
                <span className="material-symbols-outlined text-[14px]">trending_up</span>
              </div>
              <span className="font-label-muted text-label-muted">Income</span>
            </div>
            <p className="font-title-card text-title-card text-text-primary dark:text-white">{incomeCategories.length} kategori</p>
          </div>
        </section>

        {/* Category Cards */}
        <section className="space-y-stack-md">
          <div className="flex items-center justify-between pb-2">
            <h3 className="font-headline-section text-headline-section text-text-primary dark:text-white">Categories</h3>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-7 h-7 border-2 border-[#c7ff00] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {categories.map((cat) => {
                const color = getCategoryColor(cat);
                return (
                  <div
                    key={cat.id}
                    className="bg-surface-white dark:bg-inverse-surface rounded-[24px] p-4 card-shadow hover-lift flex flex-col justify-between"
                    onClick={() => !cat.is_default && openEditModal(cat)}
                  >
                    <div className="flex flex-col gap-2 mb-4">
                      <div
                        className="w-10 h-10 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: `${color}20`, color }}
                      >
                        <span className="material-symbols-outlined icon-fill">{getCategoryIcon(cat)}</span>
                      </div>
                      <div>
                        <h4 className="font-title-card text-title-card text-text-primary dark:text-white truncate">{cat.name}</h4>
                        <p className="font-label-muted text-label-muted text-text-muted">{TYPE_LABELS[cat.type]}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      {cat.is_default ? (
                        <span className="text-[10px] font-bold text-[#9E9E9E] bg-[#F1F2F0] px-2 py-0.5 rounded-full uppercase">Default</span>
                      ) : (
                        <span className="text-[10px] font-bold rounded-full uppercase px-2 py-0.5" style={{ backgroundColor: `${color}20`, color }}>Custom</span>
                      )}
                      {!cat.is_default && (
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeleteConfirmId(cat.id); }}
                          className="p-1 rounded-lg text-[#D5D8DC] hover:text-red-400 transition-colors"
                        >
                          <span className="material-symbols-outlined text-[16px]">delete</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* ======= CREATE/EDIT MODAL ======= */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
          style={{ margin: 0 }}
          onClick={(e) => { if (e.target === e.currentTarget) setIsModalOpen(false); }}
        >
          <div className="bg-white rounded-[28px] p-6 sm:p-8 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-[#1a1c1b]">
                {editingCategory ? "Edit Category" : "Set New Budget"}
              </h2>
              <button onClick={() => setIsModalOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#F1F2F0] transition-colors border-none bg-transparent cursor-pointer">
                <span className="material-symbols-outlined text-[#6F6F6F]">close</span>
              </button>
            </div>

            <div className="space-y-5">
              {/* Name */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Category Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="contoh: Pendidikan"
                  className="w-full bg-[#F1F2F0] border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] outline-none"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Type</label>
                <div className="flex gap-2">
                  {(["expense", "income", "both"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFormType(t)}
                      className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border-none cursor-pointer ${
                        formType === t
                          ? "bg-[#1a1c1b] text-white"
                          : "bg-[#F1F2F0] text-[#6F6F6F] hover:bg-[#E8E8E8]"
                      }`}
                    >
                      {TYPE_LABELS[t]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Color */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Color</label>
                <div className="flex gap-2 flex-wrap">
                  {PALETTE_COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => setFormColor(c)}
                      className={`w-8 h-8 rounded-full transition-all border-none cursor-pointer ${
                        formColor === c ? "ring-2 ring-offset-2 ring-[#1a1c1b] scale-110" : "hover:scale-105"
                      }`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              {/* Keywords */}
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">
                  Auto-detect Keywords <span className="font-normal text-[#BDBDBD]">(pisah dengan koma)</span>
                </label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  placeholder="contoh: kuliah, tugas, kampus"
                  className="w-full bg-[#F1F2F0] border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] outline-none"
                />
                <p className="text-[11px] text-[#BDBDBD] mt-1.5">
                  Bot akan otomatis mendeteksi kategori berdasarkan keyword ini
                </p>
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={!formName.trim() || formSaving}
              className="w-full mt-6 bg-[#1a1c1b] hover:bg-black text-white py-3.5 rounded-full text-sm font-bold transition-colors border-none cursor-pointer shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {formSaving ? "Saving..." : editingCategory ? "Save Changes" : "Create Category"}
            </button>
          </div>
        </div>
      )}

      {/* ======= DELETE CONFIRM MODAL ======= */}
      {deleteConfirmId !== null && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" style={{ margin: 0 }}>
          <div className="bg-white rounded-3xl p-8 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 mx-auto bg-red-100 text-red-600">
              <span className="material-symbols-outlined text-2xl">delete</span>
            </div>
            <h3 className="text-lg font-bold text-center text-[#1a1c1b] mb-2">Hapus Kategori?</h3>
            <p className="text-sm text-center text-[#6F6F6F] mb-8">
              Kategori &quot;{categories.find((c) => c.id === deleteConfirmId)?.name}&quot; akan dihapus. Transaksi yang sudah tercatat tidak akan berubah.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 py-3 rounded-full text-sm font-semibold bg-[#F1F2F0] text-[#1a1c1b] hover:bg-[#E8E8E8] transition-colors border-none cursor-pointer"
              >
                Batal
              </button>
              <button
                onClick={() => {
                  const cat = categories.find((c) => c.id === deleteConfirmId);
                  if (cat) handleDelete(cat);
                }}
                className="flex-1 py-3 rounded-full text-sm font-semibold bg-red-500 text-white hover:bg-red-600 transition-colors border-none cursor-pointer"
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
