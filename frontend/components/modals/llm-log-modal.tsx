import { format } from "date-fns";

type LlmLogItem = {
  id: number;
  user_id: number | null;
  user_name: string | null;
  user_email: string | null;
  platform: string;
  message_type: string;
  provider: string | null;
  intent: string | null;
  status: string;
  raw_message: string | null;
  parsed_result: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
};

export function LlmLogModal({ log, onClose }: { log: LlmLogItem, onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div 
        className="bg-[#202020] rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl border border-white/10 overflow-hidden transform transition-all"
      >
        <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-[#1a1a1a]">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-[#c7ff00] text-xl">terminal</span>
            LLM Console Log
          </h2>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto space-y-6 custom-scrollbar text-sm font-mono text-gray-300">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Timestamp</p>
              <p className="text-white">{format(new Date(log.created_at), "dd MMM yyyy, HH:mm:ss")}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Status</p>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                log.status === 'success' || log.status === 'transaction_finance_chat' || log.status === 'llm_usage' 
                  ? 'bg-green-500/20 text-[#c7ff00] border border-[#c7ff00]/30' 
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                {log.status.toUpperCase()}
              </span>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Provider & Model</p>
              <p className="text-[#c7ff00]">{log.provider || "N/A"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Intent / Action</p>
              <p className="text-blue-300">{log.intent || log.message_type}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">User Information</p>
              <div className="bg-[#111] border border-white/5 p-3 rounded-lg text-gray-400 break-all">
                Name: <span className="text-white">{log.user_name || "Unknown"}</span><br/>
                Email: <span className="text-white">{log.user_email || "N/A"}</span><br/>
                Platform: <span className="text-purple-300">{log.platform}</span>
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Raw Message / Request</p>
              <div className="bg-[#111] border border-white/5 p-3 rounded-lg text-green-300 whitespace-pre-wrap">
                {log.raw_message || "<No message content>"}
              </div>
            </div>

            {log.parsed_result && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Parsed Result / Response</p>
                <div className="bg-[#111] border border-white/5 p-3 rounded-lg text-yellow-200 overflow-x-auto">
                  <pre>{JSON.stringify(log.parsed_result, null, 2)}</pre>
                </div>
              </div>
            )}

            {log.error_message && (
              <div>
                <p className="text-xs text-red-500 uppercase tracking-wider mb-2">Error Message</p>
                <div className="bg-red-950/30 border border-red-900 p-3 rounded-lg text-red-400 whitespace-pre-wrap">
                  {log.error_message}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}