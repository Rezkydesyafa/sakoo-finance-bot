"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import type { CategoryResponse, CategoryCreateRequest } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";

const TYPE_LABELS: Record<string, string> = {
  expense: "Pengeluaran",
  income: "Pemasukan",
  both: "Keduanya",
};

const DEFAULT_COLORS = [
  "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
  "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
  "#F0B27A", "#82E0AA", "#F1948A", "#AED6F1", "#D7BDE2",
];

export function CategoriesTab() {
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryResponse | null>(null);
  const [filter, setFilter] = useState<"all" | "expense" | "income">("all");

  // Form state
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState<"expense" | "income" | "both">("expense");
  const [formColor, setFormColor] = useState(DEFAULT_COLORS[0]);
  const [formIcon, setFormIcon] = useState("");
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
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? "Gagal memuat kategori." : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  function openCreateModal() {
    setEditingCategory(null);
    setFormName("");
    setFormType("expense");
    setFormColor(DEFAULT_COLORS[Math.floor(Math.random() * DEFAULT_COLORS.length)]);
    setFormIcon("");
    setFormKeywords("");
    setIsModalOpen(true);
  }

  function openEditModal(cat: CategoryResponse) {
    if (cat.is_default) return;
    setEditingCategory(cat);
    setFormName(cat.name);
    setFormType(cat.type as "expense" | "income" | "both");
    setFormColor(cat.color || DEFAULT_COLORS[0]);
    setFormIcon(cat.icon || "");
    setFormKeywords((cat.keywords || []).join(", "));
    setIsModalOpen(true);
  }

  async function handleSave() {
    const token = getStoredAuthToken();
    if (!token || !formName.trim()) return;
    setFormSaving(true);

    const keywords = formKeywords
      .split(",")
      .map((k) => k.trim().toLowerCase())
      .filter(Boolean);

    try {
      if (editingCategory) {
        await apiClient.categories.update(token, editingCategory.id, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          icon: formIcon || null,
          keywords: keywords.length > 0 ? keywords : null,
        });
      } else {
        await apiClient.categories.create(token, {
          name: formName.trim(),
          type: formType,
          color: formColor,
          icon: formIcon || null,
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
    if (cat.is_default) return;
    if (!confirm(`Hapus kategori "${cat.name}"?`)) return;
    const token = getStoredAuthToken();
    if (!token) return;
    try {
      await apiClient.categories.delete(token, cat.id);
      await loadCategories();
    } catch {
      alert("Gagal menghapus kategori.");
    }
  }

  const filteredCategories = categories.filter((c) => {
    if (filter === "all") return true;
    return c.type === filter || c.type === "both";
  });

  const defaultCategories = filteredCategories.filter((c) => c.is_default);
  const customCategories = filteredCategories.filter((c) => !c.is_default);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-3 border-[#00C896] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#1a1c1b]">Kategori</h2>
          <p className="text-sm text-[#6F6F6F] mt-1">
            Kelola kategori transaksi kamu
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="flex items-center gap-2 px-4 py-2.5 bg-[#00C896] text-white rounded-xl font-medium text-sm hover:bg-[#00B085] transition-colors shadow-sm"
        >
          <span className="material-symbols-outlined text-lg">add</span>
          Tambah Kategori
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {(["all", "expense", "income"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f
                ? "bg-[#00C896] text-white shadow-sm"
                : "bg-[#F5F5F5] text-[#6F6F6F] hover:bg-[#EDEDED]"
            }`}
          >
            {f === "all" ? "Semua" : f === "expense" ? "Pengeluaran" : "Pemasukan"}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Custom Categories */}
      {customCategories.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[#6F6F6F] uppercase tracking-wider mb-3">
            Kategori Custom
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {customCategories.map((cat) => (
              <CategoryCard
                key={cat.id}
                category={cat}
                onEdit={() => openEditModal(cat)}
                onDelete={() => handleDelete(cat)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Default Categories */}
      <div>
        <h3 className="text-sm font-semibold text-[#6F6F6F] uppercase tracking-wider mb-3">
          Kategori Default
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {defaultCategories.map((cat) => (
            <CategoryCard
              key={cat.id}
              category={cat}
              isDefault
            />
          ))}
        </div>
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
          style={{ margin: 0 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsModalOpen(false);
          }}
        >
          <div className="bg-white rounded-3xl p-6 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-[#1a1c1b] mb-4">
              {editingCategory ? "Edit Kategori" : "Tambah Kategori Baru"}
            </h3>

            <div className="space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-[#1a1c1b] mb-1.5">
                  Nama Kategori
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="contoh: Pendidikan"
                  className="w-full px-4 py-2.5 rounded-xl border border-[#E0E0E0] text-[#1a1c1b] text-sm focus:outline-none focus:ring-2 focus:ring-[#00C896]/30 focus:border-[#00C896] transition-all"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-sm font-medium text-[#1a1c1b] mb-1.5">
                  Tipe
                </label>
                <div className="flex gap-2">
                  {(["expense", "income", "both"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFormType(t)}
                      className={`flex-1 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                        formType === t
                          ? "bg-[#00C896] text-white"
                          : "bg-[#F5F5F5] text-[#6F6F6F] hover:bg-[#EDEDED]"
                      }`}
                    >
                      {TYPE_LABELS[t]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Color */}
              <div>
                <label className="block text-sm font-medium text-[#1a1c1b] mb-1.5">
                  Warna
                </label>
                <div className="flex gap-2 flex-wrap">
                  {DEFAULT_COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => setFormColor(c)}
                      className={`w-8 h-8 rounded-full transition-all ${
                        formColor === c
                          ? "ring-2 ring-offset-2 ring-[#00C896] scale-110"
                          : "hover:scale-105"
                      }`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              {/* Keywords */}
              <div>
                <label className="block text-sm font-medium text-[#1a1c1b] mb-1.5">
                  Keywords{" "}
                  <span className="font-normal text-[#9E9E9E]">(pisah dengan koma)</span>
                </label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  placeholder="contoh: kuliah, tugas, kampus"
                  className="w-full px-4 py-2.5 rounded-xl border border-[#E0E0E0] text-[#1a1c1b] text-sm focus:outline-none focus:ring-2 focus:ring-[#00C896]/30 focus:border-[#00C896] transition-all"
                />
                <p className="text-xs text-[#9E9E9E] mt-1">
                  Bot akan otomatis mendeteksi kategori berdasarkan keyword ini
                </p>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setIsModalOpen(false)}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-[#F5F5F5] text-[#6F6F6F] hover:bg-[#EDEDED] transition-colors"
              >
                Batal
              </button>
              <button
                onClick={handleSave}
                disabled={!formName.trim() || formSaving}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-[#00C896] text-white hover:bg-[#00B085] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {formSaving ? "Menyimpan..." : editingCategory ? "Simpan" : "Tambah"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CategoryCard({
  category,
  isDefault = false,
  onEdit,
  onDelete,
}: {
  category: CategoryResponse;
  isDefault?: boolean;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  const color = category.color || "#00C896";
  const keywords = category.keywords || [];

  return (
    <div
      className="bg-white rounded-2xl border border-[#F0F0F0] p-4 hover:shadow-md transition-all group"
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-semibold text-[#1a1c1b] truncate">{category.name}</h4>
            {isDefault && (
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-[#E8F5E9] text-[#2E7D32] rounded-full uppercase tracking-wider">
                Default
              </span>
            )}
          </div>
          <span
            className="inline-block px-2 py-0.5 text-xs font-medium rounded-full"
            style={{
              backgroundColor: `${color}15`,
              color: color,
            }}
          >
            {TYPE_LABELS[category.type] || category.type}
          </span>

          {keywords.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {keywords.slice(0, 5).map((kw) => (
                <span
                  key={kw}
                  className="px-2 py-0.5 text-[11px] bg-[#F5F5F5] text-[#757575] rounded-full"
                >
                  {kw}
                </span>
              ))}
              {keywords.length > 5 && (
                <span className="px-2 py-0.5 text-[11px] text-[#9E9E9E]">
                  +{keywords.length - 5} lagi
                </span>
              )}
            </div>
          )}
        </div>

        {!isDefault && (
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={onEdit}
              className="p-1.5 rounded-lg hover:bg-[#F5F5F5] text-[#9E9E9E] hover:text-[#1a1c1b] transition-all"
              title="Edit"
            >
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg hover:bg-red-50 text-[#9E9E9E] hover:text-red-500 transition-all"
              title="Hapus"
            >
              <span className="material-symbols-outlined text-lg">delete</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
