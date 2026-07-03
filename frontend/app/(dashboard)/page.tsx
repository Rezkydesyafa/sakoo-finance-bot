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
import { ChatSimulator } from "@/components/chat-simulator";
import type { Transaction, ChatMessage } from "./types";

export default function Home() {
  const searchParams = useSearchParams();
  const activeTab = searchParams.get("tab") || "overview";

  const [userId, setUserId] = useState<number | null>(null);
  const [userName, setUserName] = useState("User");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
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
      text: "Halo! Saya Sakoo, asisten keuangan pribadimu.\n\nKamu bisa mencatat transaksi langsung dari sini. Coba ketik:\n- 'beli bakso 25rb'\n- 'gaji masuk 3.5jt'\n- 'laporan'\n- 'bantuan'",
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
          setUserId(user.id);
          if (user.name) setUserName(user.name);
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
        cats[t.category_name] = (cats[t.category_name] || 0) + t.amount;
      }
    });
    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]);
    const items = sorted.slice(0, 4);
    const colors = ["#9BE634", "#84cc16", "#4d7c0f", "#bef264"];

    return items.map(([name, value], index) => ({
      name,
      value,
      color: colors[index] ?? "#bef264",
    }));
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

  function appendBotMessage(text: string) {
    const botReply: ChatMessage = {
      id: Date.now() + 2,
      sender: "bot",
      text,
      time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
    };
    setChatMessages(prev => [...prev, botReply]);
  }

  const [isExporting, setIsExporting] = useState(false);
  async function handleDownloadPDF() {
    const token = getStoredAuthToken();
    if (!token) {
      alert("Silakan login terlebih dahulu.");
      window.location.href = "/login?next=/";
      return;
    }

    setIsExporting(true);
    try {
      const response = await apiClient.reports.pdfGenerate(token, {
        period: "month",
        generated_from: "dashboard",
      });
      const link = document.createElement("a");
      link.href = response.download_url;
      link.download = "";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      alert("Gagal membuat laporan PDF.");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleSendChatMessage() {
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

    const token = getStoredAuthToken();
    if (!token) {
      appendBotMessage("Silakan login terlebih dahulu agar Sakoo bisa mencatat transaksi ke dashboard.");
      return;
    }

    try {
      const result = await apiClient.transactions.parseText(token, { text });
      appendBotMessage(result.reply_text);
      if (result.transaction_id !== null) {
        await refreshTransactions(token);
      }
    } catch {
      appendBotMessage("Maaf, dashboard belum bisa menghubungi backend. Coba lagi sebentar.");
    }
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
      setTimeout(() => setQuickActionStatus(null), 3000);
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
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const token = getStoredAuthToken();
    if (!token) {
      alert("Silakan login terlebih dahulu.");
      return;
    }

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

    try {
      const media = await apiClient.media.upload(token, file, "receipt", "dashboard_upload");
      const queued = await apiClient.ocr.runReceipt(token, media.id);
      const job = await waitForJob(token, queued.job.id);
      if (!job.result_id) {
        throw new Error(job.error_message || "OCR tidak menghasilkan data.");
      }
      const receipt = await apiClient.ocr.receiptResult(token, job.result_id);
      setScanStatus("completed");
      setScannedData({
        merchant: receipt.merchant_name || "Struk",
        date: receipt.receipt_date || formatLocalDate(new Date()),
        category: "Lainnya",
        amount: Number(receipt.total_amount || 0),
      });
    } catch (error) {
      setScanStatus("idle");
      alert(error instanceof Error ? error.message : "Gagal memproses OCR struk.");
    }
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
      }).then(async () => {
        handleCancelReceipt();
        await refreshTransactions(token);
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
            accountId={userId ? `SAKOO-${String(userId).padStart(6, "0")}` : "SAKOO"}
            totalBalance={totalBalance}
            totalIncome={totalIncome}
            totalExpense={totalExpense}
            transactions={transactions}
            formatCurrency={formatCurrency}
            handleDownloadPDF={handleDownloadPDF}
            isExporting={isExporting}
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

      <ChatSimulator 
        chatMessages={chatMessages}
        chatInput={chatInput}
        setChatInput={setChatInput}
        handleSendChatMessage={handleSendChatMessage}
      />

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
    created_at: transaction.created_at,
    source: transaction.source,
  };
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function waitForJob(token: string, jobId: number) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const job = await apiClient.jobs.get(token, jobId);
    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error_message || "Job OCR gagal.");
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }

  throw new Error("OCR masih diproses. Coba cek lagi beberapa saat.");
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
