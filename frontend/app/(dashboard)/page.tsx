"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { getStoredAuthToken } from "@/lib/auth-storage";
import { apiClient } from "@/lib/api";
import { OverviewTab } from "@/components/tabs/overview-tab";
import { TransactionsTab } from "@/components/tabs/transactions-tab";
import { ReportsTab } from "@/components/tabs/reports-tab";
import { ReceiptScanTab } from "@/components/tabs/receipt-scan-tab";
import { BudgetsTab } from "@/components/tabs/budgets-tab";
import { SettingsTab } from "@/components/tabs/settings-tab";
import { IntegrationsTab } from "@/components/tabs/integrations-tab";
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

  // Quick Action Handlers
  const handleQuickAddIncome = () => {
    const token = getStoredAuthToken();
    if (!token) return alert("Please login first");
    apiClient.transactions.create(token, {
      type: "income",
      amount: 1000000,
      description: "Quick Income",
      transaction_date: new Date().toISOString().split("T")[0],
    }).then(() => {
      window.location.reload();
    }).catch(() => {
      alert("Failed to add transaction.");
    });
  };

  const handleQuickAddExpense = () => {
    const token = getStoredAuthToken();
    if (!token) return alert("Please login first");
    apiClient.transactions.create(token, {
      type: "expense",
      amount: 50000,
      description: "Quick Expense",
      transaction_date: new Date().toISOString().split("T")[0],
    }).then(() => {
      window.location.reload();
    }).catch(() => {
      alert("Failed to add transaction.");
    });
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
      {activeTab === "overview" && (
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
          handleQuickAddIncome={handleQuickAddIncome}
          handleQuickAddExpense={handleQuickAddExpense}
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

      {activeTab === "settings" && <SettingsTab />}

      {activeTab === "integrations" && <IntegrationsTab />}
    </>
  );
}
