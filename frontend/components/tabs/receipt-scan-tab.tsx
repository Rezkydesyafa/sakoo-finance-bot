import type { ChangeEvent } from "react";

type ReceiptScanTabProps = {
  receiptImage: string | null;
  scanStatus: "idle" | "scanning" | "completed";
  scannedData: { merchant: string; date: string; category: string; amount: number };
  setScannedData: (data: { merchant: string; date: string; category: string; amount: number }) => void;
  handleFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  handleCancelReceipt: () => void;
  handleConfirmReceipt: () => void;
  formatCurrency: (val: number) => string;
};

export function ReceiptScanTab({
  receiptImage,
  scanStatus,
  scannedData,
  setScannedData,
  handleFileChange,
  handleCancelReceipt,
  handleConfirmReceipt,
  formatCurrency,
}: ReceiptScanTabProps) {
  return (
    <div className="space-y-6">
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

      {/* Hidden file inputs: Gallery vs direct Camera Capture */}
      <input 
        type="file" 
        id="receipt-file-input-gallery" 
        className="hidden" 
        accept="image/*" 
        onChange={handleFileChange} 
      />
      <input 
        type="file" 
        id="receipt-file-input-camera" 
        className="hidden" 
        accept="image/*" 
        capture="environment"
        onChange={handleFileChange} 
      />

      {/* ========================================================================= */}
      {/* 🖥️ DESKTOP VIEW (Visible on lg and above) */}
      {/* ========================================================================= */}
      <div className="hidden lg:block space-y-6">
        {/* Page Header */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-[#1a1c1b] mb-2">Receipt Scan</h2>
          <p className="text-sm text-[#6F6F6F] max-w-2xl">Upload your receipt and Sakoo will automatically extract the details for you using advanced OCR.</p>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column: Upload Zone */}
          <div className="col-span-7">
            <div className="bg-white rounded-2xl p-6 card-shadow h-full flex flex-col">
              <h3 className="text-sm font-bold text-[#1a1c1b] mb-6">Upload Document</h3>
              <div 
                onClick={() => document.getElementById("receipt-file-input-gallery")?.click()}
                className="flex-1 border-2 border-dashed border-[#c7ff00] bg-[#f9f9f7]/30 hover:bg-[#F1F2F0]/50 rounded-xl flex flex-col items-center justify-center p-8 transition-colors cursor-pointer group min-h-[380px]"
              >
                <div className="w-20 h-20 bg-[#c7ff00]/20 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-[40px] text-[#4e6700]">cloud_upload</span>
                </div>
                <p className="font-semibold text-sm text-[#1a1c1b] mb-2 text-center">Drop your receipt here</p>
                <p className="text-xs text-[#6F6F6F] mb-8 text-center">or click to browse from your computer</p>
                <button type="button" className="bg-[#c7ff00] text-[#151f00] text-xs font-semibold px-8 py-3 rounded-full hover:opacity-90 transition-opacity border-none cursor-pointer">
                  Select File
                </button>
                <p className="text-[10px] text-[#6F6F6F] mt-6 text-center">Supported formats: JPEG, PNG, PDF (Max 5MB)</p>
              </div>
            </div>
          </div>

          {/* Right Column: Verification & Form */}
          <div className="col-span-5">
            <div className="bg-white rounded-2xl p-6 card-shadow h-full flex flex-col">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-sm font-bold text-[#1a1c1b]">Scan Preview</h3>
                {scanStatus === "scanning" && (
                  <span className="bg-[#F1F2F0] text-[#6F6F6F] px-3 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#F6C85F] animate-pulse"></span> Processing
                  </span>
                )}
                {scanStatus === "completed" && (
                  <span className="bg-[#5FCF6A]/10 text-[#5FCF6A] px-3 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#5FCF6A]"></span> Success
                  </span>
                )}
                {scanStatus === "idle" && (
                  <span className="bg-[#F1F2F0] text-[#6F6F6F] px-3 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-neutral-400"></span> Idle
                  </span>
                )}
              </div>

              {/* Mock Receipt Preview */}
              <div className="bg-[#F1F2F0] rounded-xl p-4 mb-6 relative overflow-hidden group h-48 flex items-center justify-center border border-[#E8E8E8]">
                {scanStatus === "scanning" && (
                  <>
                    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#c7ff00]/20 to-transparent h-1/2 w-full animate-scan top-0 pointer-events-none"></div>
                    <div className="absolute top-0 left-0 w-full h-[2px] bg-[#c7ff00] animate-scanLine shadow-[0_0_8px_#c7ff00]"></div>
                  </>
                )}

                {receiptImage ? (
                  <img src={receiptImage} alt="Receipt Preview" className="max-h-full max-w-full object-contain rounded" />
                ) : (
                  <span className="material-symbols-outlined text-[64px] text-[#6F6F6F] opacity-30">receipt</span>
                )}

                {scanStatus === "idle" && (
                  <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px] flex items-center justify-center">
                    <p className="text-xs font-semibold text-[#6F6F6F]">Awaiting document...</p>
                  </div>
                )}
              </div>

              {/* Extracted Data Form */}
              <div className="flex-1 flex flex-col">
                <div className="space-y-5 flex-1">
                  <div>
                    <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Merchant Name</label>
                    <div className="bg-[#F1F2F0] rounded-full px-4 py-2.5 flex items-center">
                      <input 
                        className="bg-transparent border-none p-0 w-full text-xs text-[#1a1c1b] focus:ring-0 font-semibold" 
                        disabled={scanStatus !== "completed"} 
                        type="text" 
                        value={scannedData.merchant}
                        onChange={(e) => setScannedData({ ...scannedData, merchant: e.target.value })}
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Date</label>
                      <div className="bg-[#F1F2F0] rounded-full px-4 py-2.5 flex items-center">
                        <input 
                          className="bg-transparent border-none p-0 w-full text-xs text-[#1a1c1b] focus:ring-0 font-semibold" 
                          disabled={scanStatus !== "completed"} 
                          type="date" 
                          value={scannedData.date}
                          onChange={(e) => setScannedData({ ...scannedData, date: e.target.value })}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Category</label>
                      <div className="bg-[#F1F2F0] rounded-full px-4 py-2.5 flex items-center">
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
                        <span className="material-symbols-outlined text-[#6F6F6F] text-sm">expand_more</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-4 mt-2 border-t border-[#E8E8E8]">
                    <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Total Amount</label>
                    <div className="bg-[#F1F2F0] rounded-xl px-4 py-3 flex items-center justify-between">
                      <span className="text-xs font-semibold text-[#6F6F6F]">IDR</span>
                      <span className={`text-xl font-bold text-[#1a1c1b] ${scanStatus !== "completed" ? "opacity-30" : ""}`}>
                        {scanStatus === "completed" ? formatCurrency(scannedData.amount) : "Rp 0"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 mt-8 pt-4">
                  <button 
                    onClick={handleCancelReceipt}
                    type="button"
                    className="flex-1 bg-[#F1F2F0] text-[#1a1c1b] text-xs font-semibold py-3 rounded-full hover:bg-[#E8E8E8] transition-colors border-none cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleConfirmReceipt}
                    disabled={scanStatus !== "completed"}
                    type="button"
                    className={`flex-1 bg-[#c7ff00] text-[#151f00] text-xs font-semibold py-3 rounded-full hover:opacity-90 transition-opacity border-none ${
                      scanStatus !== "completed" ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                    }`}
                  >
                    Confirm & Save
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 📱 MOBILE VIEW (Visible below lg) */}
      {/* ========================================================================= */}
      <div className="block lg:hidden space-y-6 max-w-md mx-auto">
        <h2 className="text-lg font-bold text-[#1a1c1b] px-1">Receipt Scan</h2>

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
            <div className="absolute left-0 w-full h-[2px] bg-[#c7ff00] animate-scanLine shadow-[0_0_10px_#c7ff00]"></div>
          )}

          {/* Overlay Actions (3-Column Grid for Perfect Centering) */}
          <div className="absolute bottom-4 left-4 right-4 grid grid-cols-3 items-center bg-black/40 backdrop-blur-md p-3 rounded-2xl border border-white/10 z-10">
            <div className="flex justify-start">
              <button 
                onClick={() => document.getElementById("receipt-file-input-gallery")?.click()}
                type="button" 
                className="flex items-center gap-1.5 text-white text-xs font-semibold border-none bg-transparent cursor-pointer hover:opacity-80"
              >
                <span className="material-symbols-outlined text-[20px]">photo_library</span> Gallery
              </button>
            </div>
            
            <div className="flex justify-center">
              <button 
                onClick={() => document.getElementById("receipt-file-input-camera")?.click()}
                type="button" 
                className="w-14 h-14 bg-[#c7ff00] rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(199,255,0,0.5)] active:scale-90 transition-transform border-none cursor-pointer hover:bg-[#bff500]"
              >
                <span className="material-symbols-outlined text-[#151f00] text-[28px]">photo_camera</span>
              </button>
            </div>

            <div className="flex justify-end">
              <button 
                onClick={() => alert("Flash features are only available in native mobile apps.")}
                type="button" 
                className="w-10 h-10 flex items-center justify-center rounded-full bg-white/20 border-none cursor-pointer hover:bg-white/30"
              >
                <span className="material-symbols-outlined text-white text-[20px]">flash_on</span>
              </button>
            </div>
          </div>
        </div>

        {/* Extracted Data Form (Scan Results) */}
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
                    type="date" 
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
  );
}
