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
  return (
    <div className="bg-white rounded-[28px] p-6 card-shadow flex flex-col h-[320px]">
      <div className="border-b border-[#E8E8E8] pb-3 mb-4 flex items-center justify-between">
        <div>
          <h4 className="text-[15px] font-semibold text-[#1a1c1b]">AI Assistant Chat</h4>
          <p className="text-[10px] text-[#6F6F6F] font-medium">Test bot parsing here</p>
        </div>
        <span className="h-2 w-2 rounded-full bg-[#5FCF6A] animate-pulse" />
      </div>
      <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 mb-4 pr-1 text-xs font-semibold leading-relaxed">
        {chatMessages.slice(-3).map((msg) => (
          <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}>
            <div className={`p-2.5 rounded-2xl ${
              msg.sender === "user" ? "bg-[#4e6700] text-white rounded-tr-none" : "bg-[#F1F2F0] text-[#191919] rounded-tl-none border border-[#E8E8E8]"
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 border-t border-[#E8E8E8] pt-3">
        <input
          type="text"
          placeholder="e.g. 'beli bensin 25rb'..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSendChatMessage()}
          className="flex-1 bg-[#F1F2F0] border-none rounded-xl px-3 py-2 text-xs text-[#191919] placeholder-[#6F6F6F] focus:ring-1 focus:ring-[#c7ff00]"
        />
        <button onClick={handleSendChatMessage} className="bg-[#c7ff00] hover:bg-[#bff500] text-[#151f00] text-[13px] font-semibold px-3 py-2 rounded-xl text-xs transition" type="button">
          Send
        </button>
      </div>
    </div>
  );
}
