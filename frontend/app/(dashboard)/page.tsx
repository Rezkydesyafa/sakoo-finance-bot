"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { clearAuthToken, getStoredAuthToken } from "@/lib/auth-storage";
import { ApiError, apiClient } from "@/lib/api";
import type { Transaction as ApiTransaction, TransactionType } from "@/lib/api";
import { OverviewTab } from "@/components/tabs/overview-tab";
import { TransactionsTab } from "@/components/tabs/transactions-tab";
import { ReportsTab } from "@/components/tabs/reports-tab";
import { ReceiptScanTab } from "@/components/tabs/receipt-scan-tab";
import { BudgetsTab } from "@/components/tabs/budgets-tab";
import { SettingsTab } from "@/components/tabs/settings-tab";
import { IntegrationsTab } from "@/components/tabs/integrations-tab";
import { TransactionModal } from "@/components/add-transaction-modal";
import type { Transaction, ChatMessage } from "./types";

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
  const [userEmail, setUserEmail] = useState("kevin.merico@example.com");
  const [userPhone, setUserPhone] = useState("+62 812 3456 7890");
  const [transactions, setTransactions] = useState<Transaction[]>(initialMockTransactions);
  const [searchTerm, setSearchTerm] = useState("");
  const [expenseFilterType, setExpenseFilterType] = useState<"all" | "income" | "expense">("all");
  const [quickActionLoading, setQuickActionLoading] = useState<TransactionType | null>(null);
  const [quickActionStatus, setQuickActionStatus] = useState<string | null>(null);

  const [isAddTxModalOpen, setIsAddTxModalOpen] = useState(false);
  const [addTxInitialType, setAddTxInitialType] = useState<TransactionType>("expense");

  const [editTxId, setEditTxId] = useState<number | null>(null);
  const [editTxData, setEditTxData] = useState<{ type: TransactionType, title: string, amount: number } | null>(null);

  const [deleteTxId, setDeleteTxId] = useState<number | null>(null);

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

  // Receipt Scanner states (Desktop)
  const [receiptImage, setReceiptImage] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<"idle" | "scanning" | "completed">("idle");
  const [scannedData, setScannedData] = useState({
    merchant: "---",
    date: "---",
    category: "---",
    amount: 0,
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
          if (user.email) setUserEmail(user.email);
          if (user.phone_number) setUserPhone(user.phone_number);
        })
        .catch((error) => {
          if (isAuthExpiredError(error)) {
            clearAuthToken();
            window.location.href = "/login?next=/";
          }
        });

      refreshTransactions(token)
        .catch((error) => {
          if (isAuthExpiredError(error)) {
            clearAuthToken();
            window.location.href = "/login?next=/";
          }
        });
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

  function formatCurrency(val: number) {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(val).replace("Rp", "Rp ").trim();
  }

  async function handleConfirmDeleteTransaction() {
    if (!deleteTxId) return;
    
    const token = getStoredAuthToken();
    if (!token) return;

    try {
      await apiClient.transactions.delete(token, deleteTxId);
      await refreshTransactions(token);
    } catch (error) {
      alert("Gagal menghapus transaksi.");
    } finally {
      setDeleteTxId(null);
    }
  }

  function handleDeleteTransaction(id: number) {
    setDeleteTxId(id);
  }

  async function handleEditTransaction(id: number) {
    const tx = transactions.find((t) => t.id === id);
    if (!tx) return;
    
    setEditTxId(id);
    setEditTxData({
      type: tx.type,
      title: tx.description || "",
      amount: tx.amount,
    });
  }

  async function handleSaveEditTransaction(data: { type: "income" | "expense"; title: string; amount: number }) {
    if (!editTxId) return;
    const id = editTxId;
    setEditTxId(null);
    setEditTxData(null);
    
    const token = getStoredAuthToken();
    if (!token) return alert("Silakan login terlebih dahulu.");

    try {
      await apiClient.transactions.update(token, id, {
        description: data.title.trim(),
        amount: data.amount,
        type: data.type,
      });
      await refreshTransactions(token);
    } catch (error) {
      alert("Gagal mengubah transaksi.");
    }
  }

  async function refreshTransactions(token: string) {
    const res = await apiClient.transactions.list(token);
    setTransactions(res.items.map(item => toDashboardTransaction(item)));
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

  async function handleSaveModalTransaction(data: { type: "income" | "expense"; title: string; amount: number }) {
    setIsAddTxModalOpen(false);
    const token = getStoredAuthToken();
    if (!token) {
      setQuickActionStatus("Silakan login ulang sebelum menambah transaksi.");
      window.location.href = "/login?next=/";
      return;
    }

    const isIncome = data.type === "income";
    const label = isIncome ? "pemasukan" : "pengeluaran";

    setQuickActionLoading(data.type);
    setQuickActionStatus(`Mencatat ${label}...`);

    try {
      const created = await apiClient.transactions.create(token, {
        type: data.type,
        amount: data.amount,
        description: data.title.trim(),
        transaction_date: formatLocalDate(new Date()),
      });

      setTransactions(prev => [
        toDashboardTransaction(created, "Lainnya"),
        ...prev.filter(transaction => transaction.id !== created.id),
      ]);
      await refreshTransactions(token);
      setQuickActionStatus(`${isIncome ? "Pemasukan" : "Pengeluaran"} berhasil ditambahkan.`);
    } catch (error) {
      if (isAuthExpiredError(error)) {
        clearAuthToken();
        setQuickActionStatus("Sesi login kedaluwarsa. Silakan login ulang.");
        window.location.href = "/login?next=/";
        return;
      }
      setQuickActionStatus(getTransactionCreateErrorMessage(error));
    } finally {
      setQuickActionLoading(null);
    }
  }

  // Quick Action Handlers
  const handleQuickAddIncome = () => {
    setAddTxInitialType("income");
    setIsAddTxModalOpen(true);
  };

  const handleQuickAddExpense = () => {
    setAddTxInitialType("expense");
    setIsAddTxModalOpen(true);
  };

  // Receipt scanning handlers (Desktop)
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      setReceiptImage(reader.result as string);
    };
    reader.readAsDataURL(file);

    setScanStatus("scanning");
    setScannedData({
      merchant: "---",
      date: "---",
      category: "---",
      amount: 0,
    });

    setTimeout(() => {
      setScanStatus("completed");
      setScannedData({
        merchant: "Starbucks Coffee",
        date: new Date().toISOString().split("T")[0],
        category: "Makanan",
        amount: 85000,
      });
    }, 2500);
  };

  const handleCancelReceipt = () => {
    setReceiptImage(null);
    setScanStatus("idle");
    setScannedData({
      merchant: "---",
      date: "---",
      category: "---",
      amount: 0,
    });
  };

  const handleConfirmReceipt = () => {
    if (scanStatus !== "completed") return;
    const token = getStoredAuthToken();
    if (token) {
      apiClient.transactions.create(token, {
        type: "expense",
        amount: scannedData.amount,
        description: scannedData.merchant,
        transaction_date: scannedData.date,
      }).then(() => {
        handleCancelReceipt();
        window.location.reload();
      }).catch(() => {
        alert("Failed to save transaction.");
      });
    } else {
      alert("Please login first.");
    }
  };

  return (
    <>
      {/* Render Main Tab Content */}
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both" style={{ animationDelay: '100ms' }}>
        {(activeTab === "overview" || activeTab === "settings") && (
          <OverviewTab
            userName={userName}
            totalBalance={totalBalance}
            totalIncome={totalIncome}
            totalExpense={totalExpense}
            formatCurrency={formatCurrency}
            handleDownloadPDF={handleDownloadPDF}
            isExporting={isExporting}
            chatMessages={chatMessages}
            chatInput={chatInput}
            setChatInput={setChatInput}
            handleSendChatMessage={handleSendChatMessage}
            handleQuickAddIncome={handleQuickAddIncome}
            handleQuickAddExpense={handleQuickAddExpense}
            quickActionLoading={quickActionLoading}
            quickActionStatus={quickActionStatus}
            filteredTransactions={filteredTransactions}
          />
        )}

        {activeTab === "transactions" && (
          <TransactionsTab
            transactions={transactions}
            filteredTransactions={filteredTransactions}
            expenseFilterType={expenseFilterType}
            setExpenseFilterType={setExpenseFilterType}
            formatCurrency={formatCurrency}
            handleDeleteTransaction={handleDeleteTransaction}
            handleEditTransaction={handleEditTransaction}
            handleQuickAddIncome={handleQuickAddIncome}
            handleQuickAddExpense={handleQuickAddExpense}
            quickActionLoading={quickActionLoading}
            quickActionStatus={quickActionStatus}
            handleDownloadPDF={handleDownloadPDF}
            isExporting={isExporting}
            totalBalance={totalBalance}
          />
        )}

        {activeTab === "reports" && (
          <ReportsTab
            transactions={transactions}
            categoryStats={categoryStats}
            totalIncome={totalIncome}
            totalExpense={totalExpense}
            totalBalance={totalBalance}
            formatCurrency={formatCurrency}
            handleDownloadPDF={handleDownloadPDF}
            isExporting={isExporting}
          />
        )}

        {activeTab === "receipt_scan" && (
          <ReceiptScanTab
            receiptImage={receiptImage}
            scanStatus={scanStatus}
            scannedData={scannedData}
            setScannedData={setScannedData}
            handleFileChange={handleFileChange}
            handleCancelReceipt={handleCancelReceipt}
            handleConfirmReceipt={handleConfirmReceipt}
            formatCurrency={formatCurrency}
          />
        )}

        {activeTab === "budgets" && <BudgetsTab />}

        {activeTab === "integrations" && <IntegrationsTab />}
      </div>

      <TransactionModal 
        isOpen={isAddTxModalOpen} 
        mode="add"
        onClose={() => setIsAddTxModalOpen(false)} 
        onSave={handleSaveModalTransaction} 
        initialType={addTxInitialType} 
      />

      {editTxData && (
        <TransactionModal 
          isOpen={editTxId !== null} 
          mode="edit"
          onClose={() => { setEditTxId(null); setEditTxData(null); }} 
          onSave={handleSaveEditTransaction} 
          initialType={editTxData.type}
          initialTitle={editTxData.title}
          initialAmount={editTxData.amount}
        />
      )}

      {deleteTxId !== null && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" style={{ margin: 0 }}>
          <div className="bg-white rounded-3xl p-8 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200 relative">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 mx-auto bg-red-100 text-red-600">
              <span className="material-symbols-outlined text-2xl">
                delete
              </span>
            </div>
            
            <h3 className="text-lg font-bold text-center text-[#1a1c1b] mb-2">
              Hapus Transaksi?
            </h3>
            <p className="text-sm text-center text-[#6F6F6F] mb-8">
              Tindakan ini tidak dapat dibatalkan. Transaksi ini akan dihapus dari laporan Anda selamanya.
            </p>
            
            <div className="flex flex-col gap-3">
              <button onClick={handleConfirmDeleteTransaction} className="w-full py-3 rounded-full text-sm font-bold border-none cursor-pointer transition-colors bg-red-600 hover:bg-red-700 text-white">
                Ya, Hapus
              </button>
              <button onClick={() => setDeleteTxId(null)} className="w-full py-3 bg-white border border-[#E8E8E8] text-[#1a1c1b] rounded-full text-sm font-bold hover:bg-[#F1F2F0] transition-colors cursor-pointer">
                Batal
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function toDashboardTransaction(
  transaction: ApiTransaction,
  fallbackCategory = "Lainnya",
): Transaction {
  return {
    id: transaction.id,
    type: transaction.type,
    amount: parseFloat(transaction.amount),
    category_name: transaction.category_name || fallbackCategory,
    description: transaction.description || "Transaksi Tanpa Keterangan",
    transaction_date: transaction.transaction_date,
    source: transaction.source,
  };
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isAuthExpiredError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function getTransactionCreateErrorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    return "Gagal menambah transaksi. Backend belum bisa dihubungi.";
  }

  if (error instanceof ApiError) {
    const detail = getPayloadDetail(error.payload);
    if (detail) {
      return `Gagal menambah transaksi: ${detail}`;
    }
    if (error.status === 401) {
      return "Sesi login sudah berakhir. Silakan login ulang.";
    }
    if (error.status === 404) {
      return "Gagal menambah transaksi. Route API tidak ditemukan.";
    }
  }

  return "Gagal menambah transaksi.";
}

function getPayloadDetail(payload: unknown): string | null {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    Array.isArray(payload.detail)
  ) {
    return payload.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg);
        }

        return null;
      })
      .filter(Boolean)
      .join(", ");
  }

  return null;
}
