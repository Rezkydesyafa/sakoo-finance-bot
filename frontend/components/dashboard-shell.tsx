"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { Suspense, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { LogoutButton } from "@/components/logout-button";
import { apiClient } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";
import { SettingsTab } from "@/components/tabs/settings-tab";

const navigationItems = [
  { label: "Overview", icon: "dashboard", href: "/?tab=overview", id: "overview" },
  { label: "Transactions", icon: "receipt_long", href: "/?tab=transactions", id: "transactions" },
  { label: "Reports", icon: "bar_chart", href: "/?tab=reports", id: "reports" },
  { label: "Budgets", icon: "account_balance_wallet", href: "/?tab=budgets", id: "budgets" },
  { label: "Receipt Scan", icon: "document_scanner", href: "/?tab=receipt_scan", id: "receipt_scan" },
];

const mobileNavigationItems = [
  { label: "Overview", icon: "dashboard", href: "/?tab=overview", id: "overview" },
  { label: "Transactions", icon: "receipt_long", href: "/?tab=transactions", id: "transactions" },
  { label: "Scan", icon: "document_scanner", href: "/?tab=receipt_scan", id: "receipt_scan", isScan: true },
  { label: "Budgets", icon: "account_balance_wallet", href: "/?tab=budgets", id: "budgets" },
  { label: "Reports", icon: "bar_chart", href: "/?tab=reports", id: "reports" },
];

function DashboardShellContent({ children }: { children: ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab") || "overview";
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Mobile scanning states
  const [isMobileScanOpen, setIsMobileScanOpen] = useState(false);
  const [receiptImage, setReceiptImage] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<"idle" | "scanning" | "completed">("idle");
  const [scannedData, setScannedData] = useState({
    merchant: "---",
    date: "---",
    category: "---",
    amount: 0,
  });

  const [userName, setUserName] = useState("Kevin Merico");
  const [userEmail, setUserEmail] = useState("kevin.merico@example.com");
  const [userPhone, setUserPhone] = useState("+62 812 3456 7890");
  const [profileImage, setProfileImage] = useState<string | null>(null);

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    if (currentTab === "settings" && !isSettingsOpen) {
      setIsSettingsOpen(true);
    }
  }, [currentTab]);

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    apiClient.me(token).then((user) => {
      if (user.name) setUserName(user.name);
      if (user.email) setUserEmail(user.email);
      if (user.phone_number) setUserPhone(user.phone_number);
    }).catch(() => {
      // If fetching user fails, might be an expired token
      router.replace("/login");
    });

    const loadProfileImage = () => {
      const savedImage = localStorage.getItem("sakoo_profile_image");
      if (savedImage) setProfileImage(savedImage);
    };

    loadProfileImage();
    window.addEventListener("profile_image_updated", loadProfileImage);

    return () => {
      window.removeEventListener("profile_image_updated", loadProfileImage);
    };
  }, []);

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
    setIsMobileScanOpen(false);
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

  function formatCurrency(val: number) {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(val);
  }
  return (
    <div className="text-sm text-[#1a1c1b] antialiased bg-[#f9f9f7] min-h-screen">
      <div className="ambient-glow"></div>
      
      {/* SideNavBar */}
      <nav className="hidden md:flex fixed left-0 top-0 h-screen w-[240px] bg-white flex-col py-8 border-r border-[#E8E8E8] z-50">
        <div className="px-8 mb-8">
          <h1 className="text-xl font-bold text-[#1a1c1b]">Sakoo</h1>
          <p className="text-xs text-[#6F6F6F] mt-1">Finance Bot</p>
        </div>
        
        <div className="flex-1 flex flex-col gap-2 overflow-y-auto no-scrollbar">
          {navigationItems.map((item) => {
            const isActive = currentTab === item.id;
            
            if (item.id === "settings") {
              return (
                <button
                  key={item.id}
                  onClick={() => setIsSettingsOpen(true)}
                  className="flex items-center gap-3 text-[#5f5e5e] hover:text-[#4e6700] px-4 py-3 mx-2 transition-colors hover:bg-neutral-100 rounded-xl bg-transparent border-none cursor-pointer w-[calc(100%-1rem)] text-left"
                >
                  <span className="material-symbols-outlined">{item.icon}</span>
                  <span className="text-[13px] font-semibold">{item.label}</span>
                </button>
              );
            }

            return (
              <Link
                key={item.id}
                href={item.href}
                className={isActive
                  ? "flex items-center gap-3 bg-[#c7ff00] text-[#151f00] rounded-xl px-4 py-3 mx-2 scale-[0.98] transition-transform duration-200"
                  : "flex items-center gap-3 text-[#5f5e5e] hover:text-[#4e6700] px-4 py-3 mx-2 transition-colors hover:bg-neutral-100 rounded-xl"
                }
              >
                <span className="material-symbols-outlined" style={isActive ? { fontVariationSettings: '"FILL" 1' } : {}}>{item.icon}</span>
                <span className="text-[13px] font-semibold">{item.label}</span>
              </Link>
            );
          })}
        </div>
        
        <div className="px-6 mb-4 mt-auto">
          <Link href="/?tab=transactions" className="w-full py-3 px-4 bg-[#4e6700] text-white text-[13px] font-semibold rounded-full hover:opacity-90 transition-opacity flex items-center justify-center gap-2">
            <span className="material-symbols-outlined">add</span>
            + New Transaction
          </Link>
        </div>
      </nav>

      {/* TopNavBar */}
      <header className="fixed top-0 md:right-0 w-full md:w-[calc(100%_-_240px)] z-40 bg-[#f9f9f7] flex justify-between items-center h-20 px-4 md:px-8 border-b md:border-none border-[#E8E8E8]">
        <div className="flex items-center w-64 md:w-96 relative hidden sm:flex">
          <span className="material-symbols-outlined absolute left-4 text-[#6F6F6F]">search</span>
          <input 
            type="text" 
            placeholder="Search transactions, assets..." 
            className="w-full bg-[#F1F2F0] border-none rounded-full py-2.5 pl-12 pr-4 text-xs focus:ring-1 focus:ring-[#c7ff00] text-[#1a1c1b] font-semibold placeholder-[#6F6F6F]"
          />
        </div>

        <div className="flex sm:hidden items-center">
          <h1 className="text-lg font-bold text-[#1a1c1b]">Sakoo</h1>
        </div>

        <div className="flex items-center gap-4 ml-auto sm:ml-0">
          <button className="w-10 h-10 rounded-full hover:bg-neutral-100 flex items-center justify-center transition-colors border-none bg-transparent">
            <span className="material-symbols-outlined text-[#6F6F6F]">notifications</span>
          </button>
          
          <div className="h-6 w-[1px] bg-[#E8E8E8] mx-2"></div>

          {/* Profile Dropdown */}
          <div className="relative">
            <button 
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-2 focus:outline-none border-none bg-transparent cursor-pointer"
            >
              <div className="w-10 h-10 rounded-full bg-[#c7ff00] flex items-center justify-center font-bold text-[#151f00] shadow-sm overflow-hidden">
                {profileImage ? (
                  <img 
                    src={profileImage}
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="material-symbols-outlined text-[#151f00]">person</span>
                )}
              </div>
            </button>

            {isDropdownOpen && (
              <>
                <div className="fixed inset-0 z-45" onClick={() => setIsDropdownOpen(false)}></div>
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-[#E8E8E8] py-1 z-50 animate-fade-in">
                  <div className="px-4 py-3 border-b border-[#E8E8E8]">
                    <p className="text-[10px] text-[#6F6F6F] font-semibold uppercase tracking-wider">Signed in as</p>
                    <p className="text-sm font-semibold text-[#1a1c1b] truncate">{userName}</p>
                  </div>
                  
                  <Link 
                    href="/?tab=integrations" 
                    onClick={() => setIsDropdownOpen(false)}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-[#5f5e5e] hover:bg-neutral-100 transition-colors"
                  >
                    <span className="material-symbols-outlined text-[20px]">smart_toy</span>
                    <span>Bot Channels</span>
                  </Link>

                  <button 
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setIsSettingsOpen(true);
                    }}
                    className="flex items-center gap-3 w-full text-left px-4 py-2 text-sm text-[#5f5e5e] hover:bg-neutral-100 transition-colors bg-transparent border-none cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[20px]">settings</span>
                    <span>Settings</span>
                  </button>

                  <a 
                    href="#" 
                    onClick={() => setIsDropdownOpen(false)}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-[#5f5e5e] hover:bg-neutral-100 transition-colors border-t border-[#E8E8E8]"
                  >
                    <span className="material-symbols-outlined text-[20px]">headset_mic</span>
                    <span>Support</span>
                  </a>

                  <div className="px-1 py-1 border-t border-[#E8E8E8] mt-1">
                    <div className="flex items-center gap-3 w-full px-3 py-2 text-sm text-[#ba1a1a] hover:bg-red-50 rounded-xl transition-colors">
                      <span className="material-symbols-outlined text-[20px]">logout</span>
                      <LogoutButton className="text-sm font-semibold text-left w-full" />
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </header>
      
      {/* Mobile Navigation */}
      <nav className="flex items-center justify-between border-t border-[#E8E8E8] bg-white fixed bottom-0 left-0 right-0 z-50 py-1 px-2 md:hidden no-scrollbar shadow-[0_-4px_12px_rgba(0,0,0,0.04)] rounded-t-[24px] animate-fade-in">
        {mobileNavigationItems.map((item) => {
          const isActive = currentTab === item.id;
          if (item.isScan) {
            return (
              <div key={item.id} className="relative flex justify-center items-center w-[72px] shrink-0">
                <button
                  onClick={() => setIsMobileScanOpen(true)}
                  type="button"
                  className={`absolute left-1/2 -translate-x-1/2 -top-[28px] flex items-center justify-center w-[52px] h-[52px] rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.12)] border-[2px] border-white active:scale-95 transition-all duration-200 ${
                    isMobileScanOpen
                      ? "bg-[#4e6700] text-white"
                      : "bg-[#c7ff00] text-[#151f00] hover:bg-[#bff500]"
                  }`}
                >
                  <span className="material-symbols-outlined text-[26px]" style={isMobileScanOpen ? { fontVariationSettings: '"FILL" 1' } : {}}>{item.icon}</span>
                </button>
              </div>
            );
          }

          return (
            <div key={item.label} className="flex-1 flex justify-center items-center">
              <Link
                href={item.href}
                className={`flex flex-col items-center justify-center py-1 w-full rounded-2xl transition duration-150 ${
                  isActive
                    ? "text-[#4e6700]"
                    : "text-[#6F6F6F] opacity-70 hover:opacity-100"
                }`}
              >
                <div className={`flex items-center justify-center px-3 py-0.5 rounded-full mb-0.5 transition-colors ${isActive ? 'bg-[#c7ff00]/20' : 'bg-transparent'}`}>
                  <span className="material-symbols-outlined text-[26px]" style={isActive ? { fontVariationSettings: '"FILL" 1' } : {}}>{item.icon}</span>
                </div>
                <span className={`text-[10px] font-semibold tracking-tight ${isActive ? 'text-[#4e6700]' : 'text-[#6F6F6F]'}`}>{item.label}</span>
              </Link>
            </div>
          );
        })}
      </nav>

      {/* Main Content Area */}
      <main className="md:ml-[240px] pt-28 px-4 pb-32 md:pt-28 md:px-8 md:pb-8 max-w-[1440px] min-h-screen">
        {children}
      </main>

      {/* Sliding Mobile Scanner Overlay */}
      <div 
        className={`fixed inset-0 bg-[#f9f9f7] z-[100] md:hidden transition-transform duration-300 ease-out transform ${
          isMobileScanOpen ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <style>{`
          @keyframes scan {
            0% { transform: translateY(-100%); }
            50% { transform: translateY(200%); }
            100% { transform: translateY(-100%); }
          }
          @keyframes scanLine {
            0% { top: 0; }
            50% { top: 100%; }
            100% { top: 0; }
          }
          .animate-scan {
            animation: scan 4s ease-in-out infinite;
          }
          .animate-scanLine {
            animation: scanLine 4s ease-in-out infinite;
          }
        `}</style>

        <div className="flex flex-col h-full relative overflow-y-auto pb-10">
          {/* Header with Back Button */}
          <header className="sticky top-0 bg-[#f9f9f7] flex items-center justify-between px-4 py-4 z-40 border-b border-[#E8E8E8]/50 shrink-0">
            <button 
              onClick={handleCancelReceipt}
              type="button"
              className="w-10 h-10 flex items-center justify-center rounded-full bg-[#F1F2F0] hover:opacity-80 transition-opacity border-none cursor-pointer"
            >
              <span className="material-symbols-outlined text-[#1a1c1b]">arrow_back</span>
            </button>
            <h1 className="text-base font-bold text-[#1a1c1b]">Receipt Scan</h1>
            <div className="w-10"></div>
          </header>

          {/* Body Content */}
          <div className="flex-1 px-4 py-6 space-y-6 max-w-md mx-auto w-full">
            {/* Hidden file inputs */}
            <input 
              type="file" 
              id="mobile-receipt-input-gallery" 
              className="hidden" 
              accept="image/*" 
              onChange={handleFileChange} 
            />
            <input 
              type="file" 
              id="mobile-receipt-input-camera" 
              className="hidden" 
              accept="image/*" 
              capture="environment"
              onChange={handleFileChange} 
            />

            {/* Scan Area view finder */}
            <div className="relative w-full aspect-[3/4] bg-neutral-900 rounded-[28px] overflow-hidden shadow-lg border border-neutral-800">
              {receiptImage ? (
                <img src={receiptImage} alt="Receipt Scan Viewfinder" className="w-full h-full object-cover opacity-80" />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-white/40 gap-3">
                  <span className="material-symbols-outlined text-5xl">photo_camera</span>
                  <p className="text-xs text-neutral-400">Select Gallery or Capture to Scan</p>
                </div>
              )}

              <div className="absolute inset-0 border-2 border-[#c7ff00]/40 m-4 rounded-[20px] pointer-events-none"></div>
              
              {scanStatus === "scanning" && (
                <>
                  <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#c7ff00]/20 to-transparent h-1/2 w-full animate-scan top-0 pointer-events-none"></div>
                  <div className="absolute top-0 left-0 w-full h-[2px] bg-[#c7ff00] animate-scanLine shadow-[0_0_10px_#c7ff00]"></div>
                </>
              )}

              {/* Overlay Actions */}
              <div className="absolute bottom-4 left-4 right-4 grid grid-cols-3 items-center bg-black/40 backdrop-blur-md p-3 rounded-2xl border border-white/10 z-10">
                <div className="flex justify-start">
                  <button 
                    onClick={() => document.getElementById("mobile-receipt-input-gallery")?.click()}
                    type="button" 
                    className="flex items-center gap-1.5 text-white text-xs font-semibold border-none bg-transparent cursor-pointer hover:opacity-80"
                  >
                    <span className="material-symbols-outlined text-[20px]">photo_library</span> Gallery
                  </button>
                </div>
                
                <div className="flex justify-center">
                  <button 
                    onClick={() => document.getElementById("mobile-receipt-input-camera")?.click()}
                    type="button" 
                    className="w-12 h-12 bg-[#c7ff00] rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(199,255,0,0.5)] active:scale-90 transition-transform border-none cursor-pointer hover:bg-[#bff500]"
                  >
                    <span className="material-symbols-outlined text-[#151f00] text-[28px]">photo_camera</span>
                  </button>
                </div>

                <div className="flex justify-end">
                  <button 
                    onClick={() => alert("Flash features are only available in native mobile apps.")}
                    type="button" 
                    className="w-8 h-8 flex items-center justify-center rounded-full bg-white/20 border-none cursor-pointer hover:bg-white/30"
                  >
                    <span className="material-symbols-outlined text-white text-[20px]">flash_on</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Extracted Data Form */}
            <div className="bg-white rounded-[24px] p-5 shadow-sm space-y-4 border border-[#E8E8E8]">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-[#1a1c1b]">Scan Results</h2>
                {scanStatus === "scanning" && (
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F6C85F] opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#F6C85F]"></span>
                  </span>
                )}
                {scanStatus === "completed" && (
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#5FCF6A]"></span>
                  </span>
                )}
                {scanStatus === "idle" && (
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-neutral-400"></span>
                  </span>
                )}
              </div>

              {/* Total Amount Highlight */}
              <div className="flex flex-col items-center justify-center py-4 bg-[#F1F2F0] rounded-2xl">
                <span className="text-[10px] font-semibold text-[#6F6F6F] mb-1">Total Amount</span>
                <span className={`text-2xl font-bold text-[#1a1c1b] ${scanStatus !== "completed" ? "opacity-30" : ""}`}>
                  {scanStatus === "completed" ? formatCurrency(scannedData.amount) : "Rp 0"}
                </span>
              </div>

              {/* Form Fields */}
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-semibold text-[#6F6F6F] mb-1 block">Merchant</label>
                  <div className="flex items-center bg-[#F1F2F0] rounded-full px-4 py-2.5">
                    <span className="material-symbols-outlined text-[#6F6F6F] mr-2 text-[18px]">storefront</span>
                    <input 
                      className="bg-transparent border-none p-0 w-full text-xs text-[#1a1c1b] focus:ring-0 font-semibold" 
                      disabled={scanStatus !== "completed"} 
                      type="text" 
                      value={scannedData.merchant}
                      onChange={(e) => setScannedData({ ...scannedData, merchant: e.target.value })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-semibold text-[#6F6F6F] mb-1 block">Date</label>
                    <div className="flex items-center bg-[#F1F2F0] rounded-full px-4 py-2.5">
                      <span className="material-symbols-outlined text-[#6F6F6F] mr-2 text-[18px]">calendar_today</span>
                      <input 
                        className="bg-transparent border-none p-0 w-full text-xs text-[#1a1c1b] focus:ring-0 font-semibold" 
                        disabled={scanStatus !== "completed"} 
                        type="text" 
                        value={scannedData.date}
                        onChange={(e) => setScannedData({ ...scannedData, date: e.target.value })}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] font-semibold text-[#6F6F6F] mb-1 block">Category</label>
                    <div className="flex items-center bg-[#F1F2F0] rounded-full px-4 py-2.5">
                      <span className="material-symbols-outlined text-[#6F6F6F] mr-2 text-[18px]">restaurant</span>
                      <select 
                        className="bg-transparent border-none p-0 w-full text-xs text-[#1a1c1b] focus:ring-0 font-semibold appearance-none cursor-pointer" 
                        disabled={scanStatus !== "completed"} 
                        value={scannedData.category}
                        onChange={(e) => setScannedData({ ...scannedData, category: e.target.value })}
                      >
                        <option value="---">---</option>
                        <option value="Makanan">Makanan</option>
                        <option value="Belanja">Belanja</option>
                        <option value="Transportasi">Transportasi</option>
                        <option value="Hiburan">Hiburan</option>
                        <option value="Lainnya">Lainnya</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button 
                  onClick={handleCancelReceipt}
                  type="button" 
                  className="flex-1 py-3 bg-[#F1F2F0] text-[#1a1c1b] text-xs font-semibold rounded-full hover:bg-[#E8E8E8] transition-colors border-none cursor-pointer"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleConfirmReceipt}
                  disabled={scanStatus !== "completed"}
                  type="button" 
                  className={`flex-1 py-3 bg-[#c7ff00] text-[#151f00] text-xs font-semibold rounded-full hover:opacity-90 transition-opacity border-none flex justify-center items-center gap-1 ${
                    scanStatus !== "completed" ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">check_circle</span>
                  Save
                </button>
              </div>
            </div>
        </div>
      </div>
      </div>

      {/* Settings Overlay Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-[200] bg-[#f9f9f7] overflow-y-auto animate-in fade-in duration-200">
          <div className="ambient-glow"></div>
          <div className="p-4 md:p-8 max-w-5xl mx-auto pt-6 md:pt-10 relative z-10">
            <SettingsTab 
              userName={userName} 
              userEmail={userEmail} 
              userPhone={userPhone} 
              onClose={() => setIsSettingsOpen(false)} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#f9f9f7] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-12 w-12 rounded-2xl bg-[#c7ff00] flex items-center justify-center font-bold text-[#151f00] animate-pulse shadow-lg text-xl">
            S
          </div>
          <p className="text-sm font-semibold text-[#6F6F6F]">Loading Sakoo...</p>
        </div>
      </div>
    }>
      <DashboardShellContent>{children}</DashboardShellContent>
    </Suspense>
  );
}
