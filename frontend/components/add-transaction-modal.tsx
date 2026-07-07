"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";

type CategoryOption = {
  id: number;
  name: string;
  type: string;
  icon: string | null;
  color: string | null;
};

type TransactionModalProps = {
  isOpen: boolean;
  mode: "add" | "edit";
  onClose: () => void;
  onSave: (data: { type: "income" | "expense"; title: string; amount: number; category_id: number | null }) => void;
  initialType: "income" | "expense";
  initialTitle?: string;
  initialAmount?: number;
  initialCategoryId?: number | null;
};

export function TransactionModal({ 
  isOpen, 
  mode,
  onClose, 
  onSave, 
  initialType,
  initialTitle = "",
  initialAmount,
  initialCategoryId,
}: TransactionModalProps) {
  const [type, setType] = useState<"income" | "expense">(initialType);
  const [title, setTitle] = useState(initialTitle);
  const [amount, setAmount] = useState(initialAmount ? initialAmount.toString() : "");
  const [categoryId, setCategoryId] = useState<number | "">("");
  
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setType(initialType);
      setTitle(initialTitle);
      setAmount(initialAmount ? initialAmount.toString() : "");
      setCategoryId(initialCategoryId || "");
      
      const token = getStoredAuthToken();
      if (token) {
        apiClient.categories.list(token)
          .then(res => {
            const cats = res.items.map(c => ({ 
              id: c.id, 
              name: c.name,
              type: c.type,
              icon: c.icon,
              color: c.color
            }));
            setCategories(cats);
          })
          .catch(err => console.error("Failed to fetch categories:", err));
      }
    } else {
      setSearchQuery("");
      setIsDropdownOpen(false);
    }
  }, [isOpen, initialType, initialTitle, initialAmount, initialCategoryId]);

  const filteredCategories = categories
    .filter(c => c.type === type || c.type === "both")
    .filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()));

  const exactMatch = categories
    .filter(c => c.type === type || c.type === "both")
    .find(c => c.name.toLowerCase() === searchQuery.toLowerCase().trim());

  const handleCreateCategory = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!searchQuery.trim() || isCreatingCategory) return;
    
    setIsCreatingCategory(true);
    const token = getStoredAuthToken();
    if (token) {
      try {
        const newCat = await apiClient.categories.create(token, {
          name: searchQuery.trim(),
          type: type
        });
        
        const newCatOption = {
          id: newCat.id,
          name: newCat.name,
          type: newCat.type,
          icon: newCat.icon,
          color: newCat.color
        };
        
        setCategories(prev => [...prev, newCatOption]);
        setCategoryId(newCat.id);
        setSearchQuery("");
        setIsDropdownOpen(false);
      } catch (err) {
        console.error("Failed to create category:", err);
      } finally {
        setIsCreatingCategory(false);
      }
    }
  };

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const numericAmount = parseFloat(amount);
    if (isNaN(numericAmount) || numericAmount <= 0) {
      alert("Nominal tidak valid!");
      return;
    }
    
    const catId = categoryId === "" ? null : Number(categoryId);
    onSave({ type, title, amount: numericAmount, category_id: catId });
  };

  return (
    <div 
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" 
      style={{ margin: 0 }}
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-[28px] p-6 sm:p-8 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-[#1a1c1b]">
            {mode === "edit" 
              ? `Edit ${type === "expense" ? "Pengeluaran" : "Pemasukan"}` 
              : `Tambah ${type === "expense" ? "Pengeluaran" : "Pemasukan"}`}
          </h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#F1F2F0] transition-colors border-none bg-transparent cursor-pointer">
            <span className="material-symbols-outlined text-[#6F6F6F]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Judul Transaksi</label>
            <input 
              type="text" 
              required
              placeholder={type === "expense" ? "Cth: Makan Siang" : "Cth: Gaji Bulanan"}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-[#F1F2F0] border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00]" 
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Kategori</label>
            <div 
              className={`relative flex items-center bg-[#F1F2F0] rounded-xl px-4 py-3 transition-shadow cursor-pointer ${isDropdownOpen ? 'ring-1 ring-[#c7ff00]' : ''}`}
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            >
              <span className="material-symbols-outlined text-[#6F6F6F] mr-2 text-[18px] flex-shrink-0">category</span>
              
              <div className="flex-1 text-sm font-medium text-[#1a1c1b]">
                {categoryId === "" 
                  ? "Lainnya (Tanpa Kategori)" 
                  : filteredCategories.find(c => c.id === categoryId)?.name || "Pilih Kategori..."}
              </div>

              <span className={`material-symbols-outlined text-[#6F6F6F] text-[18px] transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`}>
                expand_more
              </span>

              {isDropdownOpen && (
                <>
                  <div className="fixed inset-0 z-40 bg-transparent" onClick={(e) => { e.stopPropagation(); setIsDropdownOpen(false); }}></div>
                  
                  <div className="absolute top-[calc(100%+8px)] left-0 right-0 bg-white rounded-xl shadow-xl border border-[#E8E8E8] max-h-60 flex flex-col z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                    
                    <div className="px-3 py-2 border-b border-[#E8E8E8]">
                      <input 
                        type="text" 
                        placeholder="Cari atau tambah baru..." 
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full text-sm outline-none px-2 py-1 bg-transparent"
                        autoFocus
                      />
                    </div>

                    <div className="overflow-y-auto py-1">
                      <div 
                        onClick={(e) => { 
                          e.stopPropagation();
                          setCategoryId(""); 
                          setIsDropdownOpen(false); 
                          setSearchQuery("");
                        }}
                        className={`px-4 py-3 text-sm cursor-pointer transition-colors flex items-center justify-between ${categoryId === "" ? 'bg-[#F1F2F0] text-[#151f00] font-bold' : 'text-[#1a1c1b] hover:bg-[#F1F2F0]'}`}
                      >
                        Lainnya (Tanpa Kategori)
                        {categoryId === "" && <span className="material-symbols-outlined text-[16px]">check</span>}
                      </div>

                      {filteredCategories.map(c => (
                        <div 
                          key={c.id} 
                          onClick={(e) => { 
                            e.stopPropagation();
                            setCategoryId(c.id); 
                            setIsDropdownOpen(false); 
                            setSearchQuery("");
                          }}
                          className={`px-4 py-3 text-sm cursor-pointer transition-colors flex items-center justify-between ${categoryId === c.id ? 'bg-[#F1F2F0] text-[#151f00] font-bold' : 'text-[#1a1c1b] hover:bg-[#F1F2F0]'}`}
                        >
                          {c.name}
                          {categoryId === c.id && <span className="material-symbols-outlined text-[16px]">check</span>}
                        </div>
                      ))}

                      {searchQuery.trim() && !exactMatch && (
                        <div 
                          onClick={handleCreateCategory}
                          className="px-4 py-3 text-sm cursor-pointer transition-colors flex items-center justify-between text-[#1a1c1b] hover:bg-[#F1F2F0]"
                        >
                          <span>Tambahkan &quot;{searchQuery.trim()}&quot;</span>
                          {isCreatingCategory ? (
                            <span className="w-4 h-4 rounded-full border-2 border-[#1a1c1b]/20 border-t-[#1a1c1b] animate-spin"></span>
                          ) : (
                            <span className="material-symbols-outlined text-[16px]">add</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Nominal (Rp)</label>
            <input 
              type="number" 
              required
              min="1"
              placeholder="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full bg-[#F1F2F0] border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00]" 
            />
          </div>

          <button type="submit" className="w-full bg-[#1a1c1b] hover:bg-black text-white py-3.5 rounded-full text-sm font-bold transition-colors border-none cursor-pointer mt-2 shadow-md">
            {mode === "edit" ? "Simpan Perubahan" : "Simpan Transaksi"}
          </button>
        </form>
      </div>
    </div>
  );
}
