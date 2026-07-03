"use client";
import { useState } from "react";
import type { ChatMessage } from "@/app/(dashboard)/types";

type ChatSimulatorProps = {
  chatMessages: ChatMessage[];
  chatInput: string;
  setChatInput: (val: string) => void;
  handleSendChatMessage: () => void;
};

export function ChatSimulator({
  chatMessages,
  chatInput,
  setChatInput,
  handleSendChatMessage,
}: ChatSimulatorProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Floating Action Button */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-24 right-4 md:bottom-8 md:right-8 w-14 h-14 bg-[#c7ff00] rounded-full flex items-center justify-center shadow-lg hover:scale-105 transition-transform z-[150] cursor-pointer border-none"
      >
        <span className="material-symbols-outlined text-[#151f00] text-2xl">
          {isOpen ? "close" : "smart_toy"}
        </span>
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[140] pointer-events-auto transition-opacity duration-200"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Floating Chat Window */}
      {isOpen && (
        <div className="fixed bottom-40 right-4 md:bottom-28 md:right-8 w-[calc(100vw-2rem)] md:w-[360px] max-w-[360px] bg-white rounded-[28px] p-5 shadow-2xl flex flex-col h-[400px] z-[150] border border-[#E8E8E8] animate-in fade-in slide-in-from-bottom-4 duration-200">
          <div className="border-b border-[#E8E8E8] pb-3 mb-4 flex items-center justify-between">
            <div>
              <h4 className="text-[15px] font-bold text-[#1a1c1b] flex items-center gap-2">
                <span className="material-symbols-outlined text-[#c7ff00] text-[20px]">smart_toy</span>
                AI Assistant Chat
              </h4>
              <p className="text-[10px] text-[#6F6F6F] font-medium mt-0.5">Test bot parsing here</p>
            </div>
            <span className="h-2 w-2 rounded-full bg-[#5FCF6A] animate-pulse" />
          </div>
          <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 mb-4 pr-1 text-xs font-semibold leading-relaxed">
            {chatMessages.length === 0 ? (
              <div className="text-center text-[#6F6F6F] mt-10 text-xs font-medium opacity-70">Belum ada obrolan.<br/>Coba ketik &quot;beli bensin 25rb&quot;</div>
            ) : (
              chatMessages.map((msg) => (
                <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}>
                  <div className={`p-2.5 rounded-2xl ${
                    msg.sender === "user" ? "bg-[#4e6700] text-white rounded-tr-none" : "bg-[#F1F2F0] text-[#191919] rounded-tl-none border border-[#E8E8E8]"
                  }`}>
                    {msg.text}
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="flex gap-2 border-t border-[#E8E8E8] pt-3">
            <input
              type="text"
              placeholder="Ketik sesuatu..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSendChatMessage();
                }
              }}
              className="flex-1 bg-[#F1F2F0] border-none rounded-xl px-3 py-2 text-xs text-[#191919] placeholder-[#6F6F6F] focus:ring-1 focus:ring-[#c7ff00] outline-none"
            />
            <button onClick={handleSendChatMessage} className="bg-[#c7ff00] hover:bg-[#bff500] text-[#151f00] font-bold w-10 rounded-xl transition border-none cursor-pointer flex items-center justify-center" type="button">
              <span className="material-symbols-outlined text-[16px]">send</span>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
