"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { ChatMessage } from "@/app/(dashboard)/types";
import { apiClient } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";

type ChatTabProps = {
  onTransactionAdded: (token: string) => Promise<void>;
};

const compressImage = async (file: File, maxWidth = 1024): Promise<File> => {
  return new Promise((resolve) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const canvas = document.createElement("canvas");
      let width = img.width;
      let height = img.height;

      if (width > maxWidth) {
        height = Math.round((height * maxWidth) / width);
        width = maxWidth;
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(img, 0, 0, width, height);

      canvas.toBlob((blob) => {
        if (blob) {
          try {
            resolve(new File([blob], file.name || "image.jpg", { type: "image/jpeg", lastModified: Date.now() }));
          } catch (e) {
            // Fallback for older browsers
            resolve(file);
          }
        } else {
          resolve(file);
        }
      }, "image/jpeg", 0.7);
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      resolve(file);
    };
    img.src = objectUrl;
  });
};

export function ChatTab({ onTransactionAdded }: ChatTabProps) {
  const router = useRouter();
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  
  // Voice note states
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const galleryInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("sakoo_chat_history");
    if (saved) {
      try {
        setChatMessages(JSON.parse(saved));
      } catch (e) {}
    }
  }, []);

  useEffect(() => {
    if (chatMessages.length > 0) {
      localStorage.setItem("sakoo_chat_history", JSON.stringify(chatMessages));
    }
  }, [chatMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isSending]);

  // Handle keyboard popup resizing
  useEffect(() => {
    const handleResize = () => {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 150); // small delay for keyboard animation
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const appendBotMessage = (text: string) => {
    const botReply: ChatMessage = {
      id: Date.now() + Math.random(),
      sender: "bot",
      text,
      time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
    };
    setChatMessages((prev) => [...prev, botReply]);
  };

  const handleSendText = async () => {
    if (!chatInput.trim() || isSending) return;
    
    const text = chatInput;
    const userMsg: ChatMessage = {
      id: Date.now(),
      sender: "user",
      text,
      time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setIsSending(true);

    const textarea = document.querySelector('textarea');
    if (textarea) textarea.style.height = '40px';

    const token = getStoredAuthToken();
    if (!token) {
      appendBotMessage("Silakan login terlebih dahulu agar Sakoo bisa mencatat transaksi.");
      setIsSending(false);
      return;
    }

    try {
      const result = await apiClient.transactions.parseText(token, { text });
      appendBotMessage(result.reply_text);
      if (result.transaction_id !== null) {
        await onTransactionAdded(token);
      }
    } catch {
      appendBotMessage("Maaf, gagal memproses pesan. Coba lagi sebentar.");
    } finally {
      setIsSending(false);
    }
  };

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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setIsMenuOpen(false);
    const file = e.target.files?.[0];
    if (!file) return;

    const token = getStoredAuthToken();
    if (!token) {
      appendBotMessage("Silakan login terlebih dahulu.");
      return;
    }

    // Add placeholder user message for image upload
    const userMsg: ChatMessage = {
      id: Date.now(),
      sender: "user",
      text: "📷 Mengunggah gambar struk...",
      time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setIsSending(true);

    try {
      const compressedFile = await compressImage(file);
      const media = await apiClient.media.upload(token, compressedFile, "receipt", "chat_upload");
      const queued = await apiClient.ocr.runReceipt(token, media.id);
      appendBotMessage("Struk berhasil diunggah, sedang memproses menggunakan AI OCR...");
      
      const job = await waitForJob(token, queued.job.id);
      if (!job.result_id) {
        throw new Error(job.error_message || "OCR tidak menghasilkan data.");
      }
      const receipt = await apiClient.ocr.receiptResult(token, job.result_id);
      
      const merchant = receipt.merchant_name || "Struk";
      const amount = Number(receipt.total_amount || 0);
      const date = receipt.receipt_date || new Date().toISOString().split("T")[0];

      await apiClient.transactions.create(token, {
        type: "expense",
        amount: amount,
        description: merchant,
        transaction_date: date,
      });

      await onTransactionAdded(token);
      appendBotMessage(`Struk berhasil diproses!\nMerchant: ${merchant}\nTanggal: ${date}\nTotal: Rp ${amount.toLocaleString("id-ID")}\n\nTransaksi pengeluaran telah ditambahkan.`);
      
    } catch (error) {
      appendBotMessage(error instanceof Error ? error.message : "Gagal memproses struk.");
    } finally {
      setIsSending(false);
      if (galleryInputRef.current) galleryInputRef.current.value = "";
      if (cameraInputRef.current) cameraInputRef.current.value = "";
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach(track => track.stop());
        
        if (audioChunksRef.current.length === 0) return;

        const token = getStoredAuthToken();
        if (!token) {
          appendBotMessage("Silakan login terlebih dahulu.");
          return;
        }

        const userMsg: ChatMessage = {
          id: Date.now(),
          sender: "user",
          text: "🎤 Mengirim pesan suara...",
          time: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
        };
        setChatMessages((prev) => [...prev, userMsg]);
        setIsSending(true);

        try {
          const file = new File([audioBlob], "voicenote.webm", { type: "audio/webm" });
          const media = await apiClient.media.upload(token, file, "audio", "chat_upload");
          const queued = await apiClient.stt.transcribe(token, media.id);
          appendBotMessage("Pesan suara diterima, sedang memproses menggunakan AI...");
          
          await waitForJob(token, queued.job.id);
          
          await onTransactionAdded(token);
          appendBotMessage("Pesan suara berhasil diproses! Transaksi telah diperbarui/ditambahkan jika valid.");
        } catch (error) {
          appendBotMessage(error instanceof Error ? error.message : "Gagal memproses pesan suara.");
        } finally {
          setIsSending(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (err) {
      alert("Tidak dapat mengakses mikrofon. Pastikan izin telah diberikan.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };
  
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="flex-1 flex flex-col h-[100dvh] lg:h-[calc(100vh-32px)] bg-[#f9f9f7] relative pb-20">
      <style>{`
        .chat-scroll {
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .chat-scroll::-webkit-scrollbar {
          display: none;
        }
        .ambient-shadow {
          box-shadow: 0 10px 30px rgba(0,0,0,0.06);
        }
      `}</style>
      
      {/* Hidden file inputs */}
      <input 
        type="file" 
        className="absolute w-0 h-0 opacity-0 overflow-hidden"
        accept="image/*" 
        ref={galleryInputRef} 
        onChange={handleFileChange} 
      />
      <input 
        type="file" 
        className="absolute w-0 h-0 opacity-0 overflow-hidden"
        accept="image/*" 
        capture="environment" 
        ref={cameraInputRef} 
        onChange={handleFileChange} 
      />

      {/* Top AppBar */}
      <header className="flex-none bg-[#f9f9f7]/90 backdrop-blur-md z-20 px-4 py-4 flex items-center justify-between border-b border-[#E8E8E8]/50 sticky top-0 md:rounded-t-3xl">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push("/?tab=overview")}
            className="md:hidden flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm border border-[#E8E8E8] text-[#1a1c1b] mr-1 active:scale-95 transition-transform"
          >
            <span className="material-symbols-outlined">arrow_back</span>
          </button>
          <div className="w-10 h-10 rounded-full bg-[#F1F2F0] flex items-center justify-center relative">
            <span className="material-symbols-outlined text-[#4e6700] text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
            <div className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-[#c7ff00] animate-pulse border-2 border-[#f9f9f7]"></div>
          </div>
          <div>
            <h1 className="font-bold text-[20px] text-[#1a1c1b] tracking-tight leading-tight">Sakoo AI</h1>
            <p className="text-[12px] text-[#5FCF6A] flex items-center gap-1 mt-0.5 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#5FCF6A] inline-block"></span> Online
            </p>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto chat-scroll p-4 flex flex-col relative gap-4">
        <div className="text-center text-[12px] text-[#6F6F6F] mt-2 font-semibold">Hari ini</div>
        
        {chatMessages.length === 0 && (
          <div className="text-center text-[#6F6F6F] mt-10 text-xs font-medium opacity-70">
            Ketik pesanan atau transaksi di sini. <br/> Contoh: &quot;Beli bensin 25rb&quot;
          </div>
        )}

        {chatMessages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            {msg.sender === "bot" ? (
              <div className="flex gap-3 max-w-[85%]">
                <div className="w-8 h-8 rounded-full bg-[#F1F2F0] flex-shrink-0 flex items-center justify-center mt-auto shadow-sm">
                  <span className="material-symbols-outlined text-[18px] text-[#4e6700]" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                </div>
                <div className="bg-white border border-[#E8E8E8] rounded-[24px] rounded-bl-sm px-5 py-4 ambient-shadow relative overflow-hidden">
                  <p className="text-[14px] text-[#1a1c1b] mb-1 mt-1 whitespace-pre-wrap">{msg.text}</p>
                  <span className="text-[10px] text-[#6F6F6F] mt-1 inline-block font-semibold">{msg.time}</span>
                </div>
              </div>
            ) : (
              <div className="bg-[#2f3130] text-white rounded-[24px] rounded-tr-sm px-5 py-4 max-w-[85%] ambient-shadow">
                <p className="text-[14px] whitespace-pre-wrap">{msg.text}</p>
                <span className="text-[10px] text-gray-400 mt-1 inline-block text-right w-full font-semibold">{msg.time}</span>
              </div>
            )}
          </div>
        ))}
        
        {isSending && (
          <div className="flex gap-3 max-w-[85%]">
            <div className="w-8 h-8 rounded-full bg-[#F1F2F0] flex-shrink-0 flex items-center justify-center mt-auto shadow-sm">
              <span className="material-symbols-outlined text-[18px] text-[#4e6700]" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
            </div>
            <div className="bg-white border border-[#E8E8E8] rounded-[24px] rounded-bl-sm px-5 py-4 ambient-shadow relative flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#1a1c1b] animate-bounce"></span>
              <span className="h-2 w-2 rounded-full bg-[#1a1c1b] animate-bounce" style={{ animationDelay: '0.1s' }}></span>
              <span className="h-2 w-2 rounded-full bg-[#1a1c1b] animate-bounce" style={{ animationDelay: '0.2s' }}></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Floating Input Bar */}
      <div className="absolute bottom-0 left-0 right-0 px-2 md:px-4 z-30 pb-1 md:pb-4 bg-gradient-to-t from-[#f9f9f7] via-[#f9f9f7]/90 to-transparent pt-12">
        <div className="bg-white/70 backdrop-blur-md rounded-full p-2 flex items-center gap-2 shadow-[0_12px_40px_rgba(0,0,0,0.12)] border border-white/50 relative mx-1 md:mx-0">
          
          {/* Menu Plus Button */}
          {isMenuOpen && (
            <div className="absolute bottom-16 left-2 bg-white rounded-2xl shadow-xl border border-[#E8E8E8] p-2 flex flex-col gap-1 w-48 animate-in zoom-in-95 duration-100 z-50">
              <button 
                onClick={() => {
                  cameraInputRef.current?.click();
                  setIsMenuOpen(false);
                }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-[#F1F2F0] rounded-xl text-sm font-semibold text-[#1a1c1b] transition-colors border-none bg-transparent cursor-pointer text-left"
              >
                <span className="material-symbols-outlined text-[#4e6700]">photo_camera</span>
                Ambil Foto
              </button>
              <button 
                onClick={() => {
                  galleryInputRef.current?.click();
                  setIsMenuOpen(false);
                }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-[#F1F2F0] rounded-xl text-sm font-semibold text-[#1a1c1b] transition-colors border-none bg-transparent cursor-pointer text-left"
              >
                <span className="material-symbols-outlined text-[#4e6700]">image</span>
                Unggah Galeri
              </button>
            </div>
          )}

          <button 
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="w-10 h-10 rounded-full bg-white flex items-center justify-center text-[#6F6F6F] hover:text-[#1a1c1b] transition-colors flex-shrink-0 border-none cursor-pointer"
          >
            <span className="material-symbols-outlined">add</span>
          </button>
          
          {isRecording ? (
            <div className="flex-1 flex items-center justify-between px-4 py-2 bg-red-50 rounded-full animate-pulse border border-red-100">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                <span className="text-sm font-bold text-red-600">{formatTime(recordingTime)}</span>
              </div>
              <span className="text-xs text-red-500 font-semibold">Merekam...</span>
            </div>
          ) : (
            <textarea 
              className="flex-1 bg-transparent border-none focus:ring-0 text-[14px] placeholder-[#6F6F6F] px-2 py-2.5 outline-none font-semibold resize-none h-10 max-h-24 scrollbar-hide" 
              placeholder="Ketik pesan atau transaksi..." 
              value={chatInput}
              rows={1}
              onChange={(e) => {
                setChatInput(e.target.value);
                e.target.style.height = '40px';
                e.target.style.height = `${Math.min(e.target.scrollHeight, 96)}px`;
              }}
              onFocus={() => {
                setTimeout(() => {
                  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
                }, 300);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  // Only auto-send on Enter if it's a desktop (no touch screen)
                  if (typeof window !== 'undefined' && !('ontouchstart' in window)) {
                    e.preventDefault();
                    handleSendText();
                  }
                }
              }}
            />
          )}
          
          {chatInput.trim() ? (
            <button 
              onClick={handleSendText}
              className="w-10 h-10 rounded-full bg-[#1a1c1b] flex items-center justify-center text-white hover:bg-black transition-colors flex-shrink-0 border-none cursor-pointer"
            >
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>arrow_upward</span>
            </button>
          ) : isRecording ? (
            <button 
              onClick={stopRecording}
              className="w-10 h-10 rounded-full bg-red-500 flex items-center justify-center text-white hover:bg-red-600 transition-colors flex-shrink-0 border-none cursor-pointer shadow-md"
            >
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>stop</span>
            </button>
          ) : (
            <button 
              onClick={startRecording}
              className="w-10 h-10 rounded-full bg-[#4e6700] flex items-center justify-center text-white hover:bg-[#3d5200] transition-colors flex-shrink-0 border-none cursor-pointer"
            >
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>mic</span>
            </button>
          )}
        </div>
        
        {/* Click-away backdrop for menu */}
        {isMenuOpen && (
          <div className="fixed inset-0 z-40" onClick={() => setIsMenuOpen(false)}></div>
        )}
      </div>
    </div>
  );
}
