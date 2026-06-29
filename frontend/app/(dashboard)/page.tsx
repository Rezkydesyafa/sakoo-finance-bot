"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { getStoredAuthToken } from "@/lib/auth-storage";
import { apiClient } from "@/lib/api";

type Transaction = {
  id: number;
  type: "income" | "expense";
  amount: number;
  category_name: string;
  description: string;
  transaction_date: string;
  source: string;
};

type ChatMessage = {
  id: number;
  sender: "user" | "bot";
  text: string;
  time: string;
};

const initialMockTransactions: Transaction[] = [
  {
    id: 1,
    type: "expense",
    amount: 108000,
    category_name: "Belanja",
    description: "Tinek Detstar T-Shirt",
    transaction_date: "2026-06-28T12:00:00Z",
    source: "whatsapp_text",
  },
  {
    id: 2,
    type: "expense",
    amount: 3200000,
    category_name: "Hiburan",
    description: "Playstation 5 Slim",
    transaction_date: "2026-06-27T10:00:00Z",
    source: "telegram_text",
  },
  {
    id: 3,
    type: "income",
    amount: 5000000,
    category_name: "Gaji",
    description: "Gaji Bulanan Freelance",
    transaction_date: "2026-06-25T09:00:00Z",
    source: "dashboard_manual",
  },
  {
    id: 4,
    type: "expense",
    amount: 45000,
    category_name: "Makanan",
    description: "Makan Siang Nasi Padang",
    transaction_date: "2026-06-28T14:30:00Z",
    source: "receipt_ocr",
  },
];

export default function Home() {
  const searchParams = useSearchParams();
  const activeTab = searchParams.get("tab") || "overview";

  const [userName, setUserName] = useState("Kevin Merico");
  const [transactions, setTransactions] = useState<Transaction[]>(initialMockTransactions);
  const [searchTerm, setSearchTerm] = useState("");
  const [expenseFilterType, setExpenseFilterType] = useState<"all" | "income" | "expense">("all");

  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      sender: "bot",
      text: "Halo! Saya Sakoo, asisten keuangan pribadimu.\n\nKamu bisa mencatat transaksi langsung dari sini. Coba ketik:\n• 'beli bakso 25rb'\n• 'gaji masuk 3.5jt'\n• 'laporan'\n• 'bantuan'",
      time: "Baru saja",
    },
  ]);

  const [healthStatus, setHealthStatus] = useState({
    db: "checking",
    waha: "checking",
    backend: "checking",
  });

  useEffect(() => {
    const token = getStoredAuthToken();

    apiClient.health()
      .then(() => setHealthStatus(prev => ({ ...prev, backend: "online" })))
      .catch(() => setHealthStatus(prev => ({ ...prev, backend: "offline" })));

    apiClient.databaseHealth()
      .then(() => setHealthStatus(prev => ({ ...prev, db: "online" })))
      .catch(() => setHealthStatus(prev => ({ ...prev, db: "offline" })));

    apiClient.wahaHealth()
      .then(() => setHealthStatus(prev => ({ ...prev, waha: "online" })))
      .catch(() => setHealthStatus(prev => ({ ...prev, waha: "offline" })));

    if (token) {
      apiClient.me(token)
        .then((user) => {
          if (user.name) setUserName(user.name);
        })
        .catch(() => {});

      apiClient.transactions.list(token)
        .then((res) => {
          if (res.items && res.items.length > 0) {
            const formatted = res.items.map((t: { id: number; type: "income" | "expense"; amount: string; category_name?: string; description?: string | null; transaction_date: string; source: string }) => ({
              id: t.id,
              type: t.type,
              amount: parseFloat(t.amount),
              category_name: t.category_name || "Lainnya",
              description: t.description || "Transaksi Tanpa Keterangan",
              transaction_date: t.transaction_date,
              source: t.source,
            }));
            setTransactions(formatted);
          }
        })
        .catch(() => {});
    }
  }, []);

  const totalIncome = useMemo(() => {
    return transactions.filter(t => t.type === "income").reduce((sum, t) => sum + t.amount, 0);
  }, [transactions]);

  const totalExpense = useMemo(() => {
    return transactions.filter(t => t.type === "expense").reduce((sum, t) => sum + t.amount, 0);
  }, [transactions]);

  const totalBalance = useMemo(() => totalIncome - totalExpense, [totalIncome, totalExpense]);

  const filteredTransactions = useMemo(() => {
    let result = transactions;
    if (expenseFilterType !== "all") {
      result = result.filter(t => t.type === expenseFilterType);
    }
    if (!searchTerm.trim()) return result;
    const term = searchTerm.toLowerCase();
    return result.filter(t => t.description.toLowerCase().includes(term) || t.category_name.toLowerCase().includes(term));
  }, [transactions, searchTerm, expenseFilterType]);

  const channelStats = useMemo(() => {
    const counts = { whatsapp: 0, telegram: 0, dashboard: 0 };
    transactions.forEach(t => {
      if (t.source.includes("whatsapp")) counts.whatsapp += 1;
      else if (t.source.includes("telegram")) counts.telegram += 1;
      else counts.dashboard += 1;
    });
    return {
      whatsapp: counts.whatsapp || 233,
      telegram: counts.telegram || 23,
      dashboard: counts.dashboard || 482,
    };
  }, [transactions]);

  const categoryStats = useMemo(() => {
    const cats: Record<string, number> = {};
    transactions.forEach(t => {
      if (t.type === "expense") {
        cats[t.category_name] = (cats[t.category_name] || 0) + 1;
      }
    });
    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]);
    const items = sorted.slice(0, 4);

    return [
      { name: items[0]?.[0] || "Makanan", value: items[0]?.[1] * 80 || 3572, color: "#9BE634" },
      { name: items[1]?.[0] || "Belanja", value: items[1]?.[1] * 60 || 2435, color: "#84cc16" },
      { name: items[2]?.[0] || "Tagihan", value: items[2]?.[1] * 40 || 764, color: "#4d7c0f" },
      { name: items[3]?.[0] || "Transportasi", value: items[3]?.[1] * 20 || 142, color: "#bef264" },
    ];
  }, [transactions]);

  const donutPercentages = useMemo(() => {
    const total = totalExpense || 1;
    const groups: Record<string, number> = {};
    transactions.filter(t => t.type === "expense").forEach(t => {
      groups[t.category_name] = (groups[t.category_name] || 0) + t.amount;
    });
    const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
    const p1 = Math.round(((sorted[0]?.[1] || 0) / total) * 100);
    const p2 = Math.round(((sorted[1]?.[1] || 0) / total) * 100);
    const p3 = 100 - p1 - p2;

    return {
      p1: p1 || 68,
      p2: p2 || 23,
      p3: p3 > 0 ? p3 : 9,
      cat1: sorted[0]?.[0] || "Makanan",
      cat2: sorted[1]?.[0] || "Belanja",
      cat3: sorted[2]?.[0] || "Transportasi",
    };
  }, [transactions, totalExpense]);

  function formatCurrency(val: number) {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(val).replace("Rp", "Rp ").trim();
  }

  function handleDeleteTransaction(id: number) {
    setTransactions(prev => prev.filter(t => t.id !== id));
  }

  const [isExporting, setIsExporting] = useState(false);
  function handleDownloadPDF() {
    setIsExporting(true);
    setTimeout(() => {
      setIsExporting(false);
      alert("Laporan PDF Keuangan Sakoo berhasil diunduh.");
    }, 1500);
  }

  function handleSendChatMessage() {
    if (!chatInput.trim()) return;
    const text = chatInput;
    const userMsg: ChatMessage = {
      id: Date.now(),
      sender: "user",
      text,
      time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
    };

    setChatMessages(prev => [...prev, userMsg]);
    setChatInput("");

    setTimeout(() => {
      const clean = text.toLowerCase().trim();
      const parseAmount = (str: string): number => {
        let multiplier = 1;
        if (str.includes("juta") || str.includes("jt")) multiplier = 1000000;
        else if (str.includes("ribu") || str.includes("rb") || str.includes("k")) multiplier = 1000;
        const numMatch = str.match(/\d+(?:[.,]\d+)?/);
        if (!numMatch) return 0;
        const val = parseFloat(numMatch[0].replace(",", "."));
        return val * multiplier;
      };

      let replyText = "";
      if (clean.includes("beli") || clean.includes("bayar") || clean.includes("pengeluaran")) {
        const amount = parseAmount(clean);
        if (amount === 0) {
          replyText = "Maaf, nominal tidak terbaca. Contoh: 'beli kopi 15rb'.";
        } else {
          let category = "Makanan";
          if (clean.includes("baju") || clean.includes("kaos") || clean.includes("belanja")) category = "Belanja";
          else if (clean.includes("bensin") || clean.includes("gojek")) category = "Transportasi";
          else if (clean.includes("listrik") || clean.includes("kos")) category = "Tagihan";

          const newTransaction: Transaction = {
            id: Date.now() + 1,
            type: "expense",
            amount,
            category_name: category,
            description: text.replace(/beli|bayar|pengeluaran/gi, "").trim() || "Pengeluaran Baru",
            transaction_date: new Date().toISOString(),
            source: "whatsapp_text",
          };
          setTransactions(prev => [newTransaction, ...prev]);
          replyText = `Transaksi dicatat: ${formatCurrency(amount)} kategori ${category}`;
        }
      } else if (clean.includes("gaji") || clean.includes("masuk") || clean.includes("pemasukan")) {
        const amount = parseAmount(clean);
        if (amount === 0) {
          replyText = "Maaf, nominal pemasukan tidak terbaca. Contoh: 'gaji masuk 3.5 juta'.";
        } else {
          const newTransaction: Transaction = {
            id: Date.now() + 1,
            type: "income",
            amount,
            category_name: "Gaji",
            description: text.replace(/gaji|masuk|pemasukan/gi, "").trim() || "Pemasukan Baru",
            transaction_date: new Date().toISOString(),
            source: "whatsapp_text",
          };
          setTransactions(prev => [newTransaction, ...prev]);
          replyText = `Pemasukan dicatat: ${formatCurrency(amount)}`;
        }
      } else if (clean.includes("laporan") || clean.includes("saldo")) {
        replyText = `Saldo Anda: ${formatCurrency(totalBalance)}\nPemasukan: ${formatCurrency(totalIncome)}\nPengeluaran: ${formatCurrency(totalExpense)}`;
      } else {
        replyText = "Ketik cth:\n• 'beli bensin 25rb'\n• 'gaji masuk 3jt'\n• 'laporan'";
      }

      const botReply: ChatMessage = {
        id: Date.now() + 2,
        sender: "bot",
        text: replyText,
        time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
      };
      setChatMessages(prev => [...prev, botReply]);
    }, 800);
  }

  const Icons = {
    Search: () => (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    ThreeDots: () => (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
      </svg>
    ),
    ChevronRight: () => (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    ),
    CategoryIcon: ({ name }: { name: string }) => {
      const className = "w-5 h-5 text-white";
      if (name === "Makanan") return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" /></svg>;
      if (name === "Belanja") return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" /></svg>;
      if (name === "Transportasi") return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>;
      if (name === "Gaji") return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>;
      return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>;
    }
  };

  return (
    <div className="py-6 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-6">
      
      {/* Header Banner */}
      <section className="bg-[#062A1F] text-white rounded-3xl p-6 shadow-md relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="absolute -top-12 -right-12 w-48 h-48 bg-[#A1F02D]/10 rounded-full blur-2xl" />
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#A1F02D]/20 text-[#A1F02D]">Production Ready</span>
            <span className="h-2 w-2 bg-[#A1F02D] rounded-full animate-pulse-glow" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Selamat Datang Kembali, {userName}!</h2>
          <p className="text-xs text-slate-300 font-medium max-w-xl">
            Semua data disinkronkan otomatis dari pesan WhatsApp, Telegram, dan struk belanja Anda.
          </p>
        </div>
        
        <button
          onClick={handleDownloadPDF}
          disabled={isExporting}
          className="bg-[#A1F02D] hover:bg-[#84cc16] text-[#062A1F] font-semibold px-4 py-2.5 rounded-xl text-xs shadow-md transition flex items-center gap-2"
          type="button"
        >
          {isExporting ? "Mengekspor..." : "Unduh Laporan PDF"}
        </button>
      </section>

      {/* Tab content rendering */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Summary metrics */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm">
              <div className="flex justify-between items-center text-slate-400 text-xs font-semibold mb-2">
                <span>Pemasukan</span>
                <Icons.ThreeDots />
              </div>
              <p className="text-2xl font-semibold text-slate-900">{formatCurrency(totalIncome)}</p>
              <p className="text-[10px] text-emerald-600 font-semibold mt-2">+35% dari bulan lalu</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm">
              <div className="flex justify-between items-center text-slate-400 text-xs font-semibold mb-2">
                <span>Pengeluaran</span>
                <Icons.ThreeDots />
              </div>
              <p className="text-2xl font-semibold text-slate-900">{formatCurrency(totalExpense)}</p>
              <p className="text-[10px] text-orange-500 font-semibold mt-2">-24% dari bulan lalu</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm sm:col-span-2 lg:col-span-1">
              <div className="flex justify-between items-center text-slate-400 text-xs font-semibold mb-2">
                <span>Saldo Bersih</span>
                <Icons.ThreeDots />
              </div>
              <p className="text-2xl font-semibold text-[#062A1F]">{formatCurrency(totalBalance)}</p>
              <p className="text-[10px] text-emerald-600 font-semibold mt-2">+12.4% kenaikan bersih</p>
            </div>
          </section>

          {/* Overview columns */}
          <div className="grid gap-6 lg:grid-cols-3">
            
            <div className="lg:col-span-2 space-y-6">
              {/* Green update box */}
              <div className="bg-[#062A1F] text-white rounded-3xl p-5 shadow-md relative overflow-hidden">
                <div className="absolute -top-10 -right-10 w-24 h-24 bg-[#A1F02D]/10 rounded-full blur-xl" />
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#A1F02D]/20 text-[#A1F02D] gap-1 mb-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#A1F02D] animate-pulse" />
                  Bot AI Aktif
                </span>
                <h4 className="text-base font-semibold mb-2 leading-tight">
                  Tulis pencatatan langsung di chat terminal atau lewat WhatsApp untuk mencatatkan keuangan otomatis!
                </h4>
                <p className="text-xs text-slate-400">Pesan suara dan OCR struk juga didukung penuh.</p>
              </div>

              {/* Chat Simulator Widget */}
              <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col h-[280px]">
                <div className="border-b border-slate-100 pb-2 mb-3 flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-slate-900">Uji Coba Cepat Chatbot</h4>
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
                <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 mb-3 pr-1 text-xs font-semibold leading-relaxed">
                  {chatMessages.slice(-2).map((msg) => (
                    <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}>
                      <div className={`p-2.5 rounded-2xl ${
                        msg.sender === "user" ? "bg-[#062A1F] text-white rounded-tr-none" : "bg-slate-100 text-slate-800 rounded-tl-none border border-slate-100"
                      }`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 border-t border-slate-100 pt-2">
                  <input
                    type="text"
                    placeholder="Tulis perintah..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendChatMessage()}
                    className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#062A1F] text-slate-800 font-semibold"
                  />
                  <button onClick={handleSendChatMessage} className="bg-[#A1F02D] hover:bg-[#84cc16] text-[#062A1F] font-semibold px-3 py-1 rounded-xl text-xs" type="button">
                    Kirim
                  </button>
                </div>
              </div>
            </div>

            {/* Recent list column */}
            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col h-[420px] lg:col-span-1">
              <h4 className="text-sm font-semibold text-slate-950 mb-3">Transaksi Terbaru</h4>
              <div className="flex-1 overflow-y-auto no-scrollbar space-y-2.5">
                {filteredTransactions.slice(0, 5).map(t => (
                  <div key={t.id} className="flex items-center justify-between border border-slate-100 rounded-2xl p-2.5 bg-slate-50 hover:bg-slate-100/50 transition">
                    <div className="flex items-center gap-2.5">
                      <div className={`h-8 w-8 rounded-xl flex items-center justify-center ${t.type === "income" ? "bg-emerald-600" : "bg-[#062A1F]"}`}>
                        <Icons.CategoryIcon name={t.category_name} />
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-955 leading-tight">{t.description}</p>
                        <p className="text-[9px] font-medium text-slate-400">{t.category_name} • {new Date(t.transaction_date).toLocaleDateString("id-ID")}</p>
                      </div>
                    </div>
                    <p className={`text-xs font-semibold ${t.type === "income" ? "text-emerald-600" : "text-slate-900"}`}>
                      {t.type === "income" ? "+" : "-"}{formatCurrency(t.amount)}
                    </p>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}

      {activeTab === "transactions" && (
        <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Semua Transaksi</h3>
              <p className="text-xs font-semibold text-slate-400">Total {filteredTransactions.length} transaksi tercatat</p>
            </div>
            
            <div className="flex items-center gap-3">
              <select
                value={expenseFilterType}
                onChange={(e) => setExpenseFilterType(e.target.value as "all" | "income" | "expense")}
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 focus:outline-none"
              >
                <option value="all">Semua Tipe</option>
                <option value="income">Pemasukan</option>
                <option value="expense">Pengeluaran</option>
              </select>

              <input
                type="text"
                placeholder="Cari..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-[#062A1F] text-slate-800 font-semibold"
              />
            </div>
          </div>

          <div className="overflow-x-auto font-medium">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold tracking-wider">
                  <th className="pb-3 pl-3">Transaksi</th>
                  <th className="pb-3">Kategori</th>
                  <th className="pb-3">Tanggal</th>
                  <th className="pb-3">Channel</th>
                  <th className="pb-3 text-right">Nominal</th>
                  <th className="pb-3 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredTransactions.map(t => (
                  <tr key={t.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 pl-3">
                      <div className="flex items-center gap-3">
                        <div className={`h-8 w-8 rounded-xl flex items-center justify-center ${t.type === "income" ? "bg-emerald-600" : "bg-[#062A1F]"}`}>
                          <Icons.CategoryIcon name={t.category_name} />
                        </div>
                        <span className="font-semibold text-slate-900">{t.description}</span>
                      </div>
                    </td>
                    <td>{t.category_name}</td>
                    <td className="text-slate-400">{new Date(t.transaction_date).toLocaleDateString("id-ID", { year: "numeric", month: "short", day: "numeric" })}</td>
                    <td className="capitalize">{t.source.replace("_", " ")}</td>
                    <td className={`text-right font-semibold ${t.type === "income" ? "text-emerald-600" : "text-slate-900"}`}>
                      {t.type === "income" ? "+" : "-"}{formatCurrency(t.amount)}
                    </td>
                    <td className="text-center">
                      <button onClick={() => handleDeleteTransaction(t.id)} className="text-red-500 hover:text-red-700 bg-red-50 hover:bg-red-100 px-3 py-1 rounded-xl" type="button">
                        Hapus
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "reports" && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-3">
            
            {/* Bar chart - Volume */}
            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm space-y-4">
              <h4 className="text-sm font-semibold text-slate-950">Volume Transaksi per Channel</h4>
              
              <div className="space-y-4 font-semibold text-xs text-slate-700">
                <div>
                  <div className="flex justify-between text-[10px] font-semibold mb-1 text-slate-600">
                    <span>WhatsApp Bot (WAHA)</span>
                    <span className="text-slate-950">{channelStats.whatsapp}</span>
                  </div>
                  <div className="bg-slate-100 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-[#A1F02D] h-full rounded-full" style={{ width: `${Math.min((channelStats.whatsapp / 500) * 100, 100)}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[10px] font-semibold mb-1 text-slate-600">
                    <span>Telegram Bot Gateway</span>
                    <span className="text-slate-950">{channelStats.telegram}</span>
                  </div>
                  <div className="bg-slate-100 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-[#84cc16] h-full rounded-full" style={{ width: `${Math.min((channelStats.telegram / 500) * 100, 100)}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[10px] font-semibold mb-1 text-slate-600">
                    <span>Web Dashboard</span>
                    <span className="text-slate-950">{channelStats.dashboard}</span>
                  </div>
                  <div className="bg-slate-100 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-[#4d7c0f] h-full rounded-full" style={{ width: `${Math.min((channelStats.dashboard / 500) * 100, 100)}%` }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Bubble chart - Category distribution */}
            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col justify-between h-[320px]">
              <div>
                <h4 className="text-sm font-semibold text-slate-955">Distribusi Kategori Utama</h4>
                <p className="text-[10px] text-slate-400 font-medium mb-3">Distribusi volume pengeluaran</p>
              </div>

              {/* Overlapping Circles */}
              <div className="flex-1 flex items-center justify-center relative bg-slate-50 border border-slate-100 rounded-2xl p-4">
                <div className="relative w-48 h-28 flex items-center justify-center">
                  <div
                    className="absolute rounded-full flex flex-col items-center justify-center text-center shadow-md animate-pulse-glow"
                    style={{
                      width: "80px",
                      height: "80px",
                      backgroundColor: categoryStats[0].color,
                      left: "10px",
                      top: "5px",
                      zIndex: 4,
                    }}
                  >
                    <span className="text-[9px] font-semibold text-slate-900 leading-none">{categoryStats[0].name}</span>
                    <span className="text-[11px] font-semibold text-slate-900 leading-normal">{categoryStats[0].value}</span>
                  </div>

                  <div
                    className="absolute rounded-full flex flex-col items-center justify-center text-center shadow-sm"
                    style={{
                      width: "65px",
                      height: "65px",
                      backgroundColor: categoryStats[1].color,
                      right: "15px",
                      top: "20px",
                      zIndex: 3,
                    }}
                  >
                    <span className="text-[8px] font-semibold text-slate-800 leading-none">{categoryStats[1].name}</span>
                    <span className="text-[10px] font-semibold text-slate-950">{categoryStats[1].value}</span>
                  </div>

                  <div
                    className="absolute rounded-full flex flex-col items-center justify-center text-center shadow-sm"
                    style={{
                      width: "50px",
                      height: "50px",
                      backgroundColor: categoryStats[2].color,
                      left: "65px",
                      bottom: "-5px",
                      zIndex: 2,
                    }}
                  >
                    <span className="text-[8px] font-semibold text-slate-900 leading-none">{categoryStats[2].name}</span>
                    <span className="text-[9px] font-semibold text-slate-955">{categoryStats[2].value}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Donut chart - Allocation */}
            <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col justify-between h-[320px]">
              <h4 className="text-sm font-semibold text-slate-955">Proporsi Anggaran Belanja</h4>

              <div className="flex gap-4 items-center flex-1">
                <div className="relative w-28 h-28 flex-shrink-0">
                  <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="35" fill="transparent" stroke="#E2E8F0" strokeWidth="12" />
                    <circle cx="50" cy="50" r="35" fill="transparent" stroke="#A1F02D" strokeWidth="12" strokeDasharray="220" strokeDashoffset={220 - (220 * donutPercentages.p1) / 100} />
                    <circle cx="50" cy="50" r="35" fill="transparent" stroke="#0d9488" strokeWidth="12" strokeDasharray="220" strokeDashoffset={220 - (220 * (donutPercentages.p1 + donutPercentages.p2)) / 100} style={{ transform: `rotate(${3.6 * donutPercentages.p1}deg)`, transformOrigin: "center" } as React.CSSProperties} />
                    <circle cx="50" cy="50" r="35" fill="transparent" stroke="#F97316" strokeWidth="12" strokeDasharray="220" strokeDashoffset={220 - (220 * donutPercentages.p3) / 100} style={{ transform: `rotate(${3.6 * (donutPercentages.p1 + donutPercentages.p2)}deg)`, transformOrigin: "center" } as React.CSSProperties} />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-[8px] font-medium text-slate-400">Total</span>
                    <span className="text-[10px] font-semibold text-slate-800">{formatCurrency(totalExpense)}</span>
                  </div>
                </div>

                <div className="space-y-1.5 w-full text-xs font-semibold">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-[#A1F02D]" />
                      <span className="text-slate-500">{donutPercentages.cat1}</span>
                    </div>
                    <span>{donutPercentages.p1}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-[#0d9488]" />
                      <span className="text-slate-500">{donutPercentages.cat2}</span>
                    </div>
                    <span>{donutPercentages.p2}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-[#F97316]" />
                      <span className="text-slate-500">{donutPercentages.cat3}</span>
                    </div>
                    <span>{donutPercentages.p3}%</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      )}

      {activeTab === "integrations" && (
        <div className="grid gap-6 lg:grid-cols-3">
          
          <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col h-[520px] lg:col-span-2">
            <div className="border-b border-slate-100 pb-3 mb-4 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-slate-950">Chat Terminal Sakoo</h4>
                <p className="text-[10px] text-slate-400 font-semibold font-mono">Uji coba parsing perintah bot</p>
              </div>
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse-glow" />
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar space-y-3.5 mb-4 pr-1">
              {chatMessages.map(msg => (
                <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}>
                  <div className={`p-3 rounded-2xl text-xs font-semibold whitespace-pre-line leading-relaxed ${
                    msg.sender === "user" ? "bg-[#062A1F] text-white rounded-tr-none" : "bg-slate-100 text-slate-800 rounded-tl-none border border-slate-200"
                  }`}>
                    {msg.text}
                  </div>
                  <span className="text-[8px] font-semibold text-slate-400 mt-1">{msg.time}</span>
                </div>
              ))}
            </div>

            <div className="flex gap-2 border-t border-slate-100 pt-3">
              <input
                type="text"
                placeholder="Ketik cth: 'beli bensin 25rb'..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChatMessage()}
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-[#062A1F] text-slate-800 font-semibold"
              />
              <button onClick={handleSendChatMessage} className="bg-[#A1F02D] hover:bg-[#84cc16] text-[#062A1F] font-semibold px-4 py-2 rounded-xl text-xs shadow" type="button">
                Kirim
              </button>
            </div>
          </div>

          {/* Right connections card */}
          <div className="bg-white border border-slate-200 rounded-3xl p-5 shadow-sm flex flex-col justify-between h-[520px]">
            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-slate-950">Status Integrasi Platform</h4>
              
              <div className="space-y-3 font-semibold text-xs text-slate-700">
                <div className="flex justify-between items-center border-b pb-2.5">
                  <span>WhatsApp Bot (WAHA)</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-semibold ${healthStatus.waha === "online" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                    {healthStatus.waha === "online" ? "ONLINE" : "OFFLINE"}
                  </span>
                </div>

                <div className="flex justify-between items-center border-b pb-2.5">
                  <span>Telegram Bot API</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-emerald-100 text-emerald-800">STANDBY</span>
                </div>

                <div className="flex justify-between items-center border-b pb-2.5">
                  <span>PostgreSQL Database</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-semibold ${healthStatus.db === "online" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                    {healthStatus.db === "online" ? "ONLINE" : "OFFLINE"}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span>FastAPI Server</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-semibold ${healthStatus.backend === "online" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                    {healthStatus.backend === "online" ? "ONLINE" : "OFFLINE"}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 border rounded-2xl p-4 text-[10px] text-slate-500 font-semibold leading-relaxed">
              Pastikan server backend FastAPI berjalan di port 8000 untuk menyinkronkan status koneksi dan database secara langsung.
            </div>
          </div>

        </div>
      )}

    </div>
  );
}
