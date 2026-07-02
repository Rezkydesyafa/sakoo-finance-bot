"use client";

import { useState, useEffect } from "react";

type TransactionModalProps = {
  isOpen: boolean;
  mode: "add" | "edit";
  onClose: () => void;
  onSave: (data: { type: "income" | "expense"; title: string; amount: number }) => void;
  initialType: "income" | "expense";
  initialTitle?: string;
  initialAmount?: number;
};

export function TransactionModal({ 
  isOpen, 
  mode,
  onClose, 
  onSave, 
  initialType,
  initialTitle = "",
  initialAmount,
}: TransactionModalProps) {
  const [type, setType] = useState<"income" | "expense">(initialType);
  const [title, setTitle] = useState(initialTitle);
  const [amount, setAmount] = useState(initialAmount ? initialAmount.toString() : "");

  useEffect(() => {
    if (isOpen) {
      setType(initialType);
      setTitle(initialTitle);
      setAmount(initialAmount ? initialAmount.toString() : "");
    }
  }, [isOpen, initialType, initialTitle, initialAmount]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const numericAmount = parseFloat(amount);
    if (isNaN(numericAmount) || numericAmount <= 0) {
      alert("Nominal tidak valid!");
      return;
    }
    onSave({ type, title, amount: numericAmount });
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" style={{ margin: 0 }}>
      <div className="bg-white rounded-[28px] p-6 sm:p-8 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200 relative">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-[#1a1c1b]">
            {mode === "edit" ? "Edit Transaksi" : "Tambah Transaksi"}
          </h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#F1F2F0] transition-colors border-none bg-transparent cursor-pointer">
            <span className="material-symbols-outlined text-[#6F6F6F]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="flex bg-[#F1F2F0] rounded-xl p-1">
            <button
              type="button"
              onClick={() => {
                setType("expense");
              }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-colors border-none cursor-pointer ${type === "expense" ? "bg-white text-[#1a1c1b] shadow-sm" : "bg-transparent text-[#6F6F6F]"}`}
            >
              Pengeluaran
            </button>
            <button
              type="button"
              onClick={() => {
                setType("income");
              }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-colors border-none cursor-pointer ${type === "income" ? "bg-[#c7ff00] text-[#151f00] shadow-sm" : "bg-transparent text-[#6F6F6F]"}`}
            >
              Pemasukan
            </button>
          </div>

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
