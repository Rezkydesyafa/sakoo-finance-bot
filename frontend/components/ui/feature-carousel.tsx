"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AiChat01Icon,
  AiScanIcon,
  AiMicIcon,
  File01Icon,
  Wallet01Icon,
  Notification01Icon,
} from "@hugeicons/core-free-icons";
import { cn } from "@/lib/utils";
import { HugeiconsIcon } from "@hugeicons/react";

// Feature list Sakoo Finance Bot
const FEATURES = [
  {
    id: "chat-transaction",
    label: "Chat Transaction AI",
    icon: AiChat01Icon,
    image: "/brand/chat-web-demo.jpg",
    description: "Catat pengeluaran & pemasukan secepat chatting di WhatsApp / Telegram.",
  },
  {
    id: "receipt-ocr",
    label: "OCR Receipt Scanner",
    icon: AiScanIcon,
    image:
      "https://images.unsplash.com/photo-1554224154-26032ffc0d07?q=80&w=1200",
    description: "Foto struk belanja Anda, AI langsung mengekstrak item & nominal otomatis.",
  },
  {
    id: "voice-input",
    label: "Voice Note Logging",
    icon: AiMicIcon,
    image:
      "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?q=80&w=1200",
    description: "Kirim rekaman suara singkat saat senggang untuk mencatat transaksi tanpa ketik.",
  },
  {
    id: "pdf-reports",
    label: "Automatic PDF Reports",
    icon: File01Icon,
    image:
      "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1200",
    description: "Ekspor laporan keuangan mingguan & bulanan rapi berformat PDF siap cetak.",
  },
  {
    id: "smart-budgeting",
    label: "Smart Budgeting",
    icon: Wallet01Icon,
    image: "/brand/dashboard-demo.jpg",
    description: "Atur limit anggaran per kategori pengeluaran agar finansial tetap terjaga.",
  },
  {
    id: "wa-notifications",
    label: "Daily WhatsApp Alerts",
    icon: Notification01Icon,
    image:
      "https://images.unsplash.com/photo-1611746872915-64382b5c76da?q=80&w=1200",
    description: "Notifikasi & pengingat pencatatan otomatis yang dikirim langsung ke WhatsApp.",
  },
];

const AUTO_PLAY_INTERVAL = 3500;
const ITEM_HEIGHT = 65;

const wrap = (min: number, max: number, v: number) => {
  const rangeSize = max - min;
  return ((((v - min) % rangeSize) + rangeSize) % rangeSize) + min;
};

export function FeatureCarousel() {
  const [step, setStep] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const currentIndex =
    ((step % FEATURES.length) + FEATURES.length) % FEATURES.length;

  const nextStep = useCallback(() => {
    setStep((prev) => prev + 1);
  }, []);

  const handleChipClick = (index: number) => {
    const diff = (index - currentIndex + FEATURES.length) % FEATURES.length;
    if (diff > 0) setStep((s) => s + diff);
  };

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(nextStep, AUTO_PLAY_INTERVAL);
    return () => clearInterval(interval);
  }, [nextStep, isPaused]);

  const getCardStatus = (index: number) => {
    const diff = index - currentIndex;
    const len = FEATURES.length;

    let normalizedDiff = diff;
    if (diff > len / 2) normalizedDiff -= len;
    if (diff < -len / 2) normalizedDiff += len;

    if (normalizedDiff === 0) return "active";
    if (normalizedDiff === -1) return "prev";
    if (normalizedDiff === 1) return "next";
    return "hidden";
  };

  return (
    <div className="w-full max-w-7xl mx-auto md:p-8">
      <div className="relative overflow-hidden rounded-[2.5rem] lg:rounded-[3.5rem] flex flex-col lg:flex-row min-h-[580px] lg:aspect-video border border-[#E8E8E8] shadow-sm bg-white">
        {/* Left Feature Selection Column */}
        <div className="w-full lg:w-[42%] min-h-[350px] md:min-h-[420px] lg:h-full relative z-30 flex flex-col items-start justify-center overflow-hidden px-6 md:px-12 lg:pl-12 bg-[#202020]">
          
          {/* Static Title Header above the active scrolling list */}
          <div className="absolute top-8 left-6 md:left-12 z-50 pointer-events-none">
            <span className="text-[#c7ff00] text-[10px] font-semibold uppercase tracking-[0.25em]">Fitur Unggulan</span>
            <h3 className="text-white text-base font-semibold mt-1">Jelajahi Sakoo AI</h3>
          </div>

          <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-[#202020] via-[#202020]/80 to-transparent z-40" />
          <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[#202020] via-[#202020]/80 to-transparent z-40" />
          
          <div className="relative w-full h-full flex items-center justify-center lg:justify-start z-20">
            {FEATURES.map((feature, index) => {
              const isActive = index === currentIndex;
              const distance = index - currentIndex;
              const wrappedDistance = wrap(
                -(FEATURES.length / 2),
                FEATURES.length / 2,
                distance
              );

              return (
                <motion.div
                  key={feature.id}
                  style={{
                    height: ITEM_HEIGHT,
                    width: "fit-content",
                  }}
                  animate={{
                    y: (wrappedDistance * ITEM_HEIGHT) + 20, // offset down slightly to avoid overlapping header
                    opacity: 1 - Math.abs(wrappedDistance) * 0.28,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 90,
                    damping: 22,
                    mass: 1,
                  }}
                  className="absolute flex items-center justify-start"
                >
                  <button
                    onClick={() => handleChipClick(index)}
                    onMouseEnter={() => setIsPaused(true)}
                    onMouseLeave={() => setIsPaused(false)}
                    className={cn(
                      "relative flex items-center gap-3.5 px-6 md:px-8 py-3.5 rounded-full transition-all duration-500 text-left group border text-xs md:text-sm font-semibold tracking-tight",
                      isActive
                        ? "bg-[#c7ff00] text-[#151f00] border-[#c7ff00] z-10 shadow-md scale-105"
                        : "bg-transparent text-white/60 border-white/10 hover:border-white/30 hover:text-white"
                    )}
                  >
                    <div
                      className={cn(
                        "flex items-center justify-center transition-colors duration-300",
                        isActive ? "text-[#151f00]" : "text-white/40"
                      )}
                    >
                      <HugeiconsIcon
                        icon={feature.icon}
                        size={18}
                        strokeWidth={2}
                      />
                    </div>

                    <span className="whitespace-nowrap uppercase tracking-wider">
                      {feature.label}
                    </span>
                  </button>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Right Preview Card Stack */}
        <div className="flex-1 min-h-[480px] md:min-h-[550px] lg:h-full relative bg-[#f9f9f7] flex items-center justify-center py-12 md:py-20 lg:py-12 px-6 md:px-12 lg:px-10 overflow-hidden border-t lg:border-t-0 lg:border-l border-[#E8E8E8]">
          <div className="relative w-full max-w-[380px] aspect-[4/5] flex items-center justify-center">
            {FEATURES.map((feature, index) => {
              const status = getCardStatus(index);
              const isActive = status === "active";
              const isPrev = status === "prev";
              const isNext = status === "next";

              return (
                <motion.div
                  key={feature.id}
                  initial={false}
                  animate={{
                    x: isActive ? 0 : isPrev ? -90 : isNext ? 90 : 0,
                    scale: isActive ? 1 : isPrev || isNext ? 0.86 : 0.7,
                    opacity: isActive ? 1 : isPrev || isNext ? 0.45 : 0,
                    rotate: isPrev ? -3 : isNext ? 3 : 0,
                    zIndex: isActive ? 20 : isPrev || isNext ? 10 : 0,
                    pointerEvents: isActive ? "auto" : "none",
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 260,
                    damping: 25,
                    mass: 0.8,
                  }}
                  className="absolute inset-0 rounded-[2.2rem] overflow-hidden border-4 border-white bg-white shadow-xl origin-center"
                >
                  <img
                    src={feature.image}
                    alt={feature.label}
                    className={cn(
                      "w-full h-full object-cover transition-all duration-700",
                      isActive
                        ? "grayscale-0 blur-0"
                        : "grayscale blur-[2px] brightness-75"
                    )}
                  />

                  <AnimatePresence>
                    {isActive && (
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="absolute inset-x-0 bottom-0 p-8 pt-24 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex flex-col justify-end pointer-events-none"
                      >
                        <div className="bg-[#c7ff00] text-[#151f00] px-3.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-[0.16em] w-fit shadow-md mb-2.5">
                          0{index + 1} • {feature.label}
                        </div>
                        <p className="text-white font-semibold text-lg md:text-xl leading-snug drop-shadow-md tracking-tight">
                          {feature.description}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div
                    className={cn(
                      "absolute top-6 left-6 flex items-center gap-2.5 transition-opacity duration-300 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full border border-white/20",
                      isActive ? "opacity-100" : "opacity-0"
                    )}
                  >
                    {/* Dot has been removed as requested */}
                    <span className="text-white/90 text-[10px] font-semibold uppercase tracking-[0.2em]">
                      Sakoo AI Feature
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default FeatureCarousel;
