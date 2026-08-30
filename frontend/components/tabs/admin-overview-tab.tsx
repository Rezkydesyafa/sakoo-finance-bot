"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { getStoredAuthToken } from "@/lib/auth-storage";

type AdminStats = {
  total_users: number;
  active_users: number;
  total_transactions: number;
  total_llm_requests: number;
};

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
  created_at: string;
};

type UserItem = {
  id: number;
  name: string;
  email: string;
  phone_number: string | null;
  created_at: string;
  transaction_count: number;
  last_active: string | null;
};

export function AdminOverviewTab() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<LlmLogItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadAdminData() {
      const token = getStoredAuthToken();
      if (!token) return;
      try {
        const [statsData, logsData, usersData] = await Promise.all([
          apiClient.getAdminStats(token),
          apiClient.getAdminLlmLogs(token),
          apiClient.getAdminUsers(token),
        ]);
        setStats(statsData);
        setLogs(logsData.items);
        setUsers(usersData.items);
      } catch (err) {
        console.error("Failed to load admin stats", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadAdminData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-[#c7ff00]/30 border-t-[#c7ff00] animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6F6F6F]">Sakoo Admin</p>
        <h1 className="text-3xl font-semibold text-[#1a1c1b] mt-2">Admin Dashboard</h1>
        <p className="text-sm text-[#6F6F6F] mt-2">
          Pantau aktivitas pengguna, log transaksi AI, dan kelola konfigurasi sistem.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E8E8E8]">
          <p className="text-sm text-[#6F6F6F] font-medium">Total Users</p>
          <p className="text-3xl font-semibold text-[#1a1c1b] mt-2">{stats?.total_users || 0}</p>
        </div>
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E8E8E8]">
          <p className="text-sm text-[#6F6F6F] font-medium">Active Users (30d)</p>
          <p className="text-3xl font-semibold text-[#1a1c1b] mt-2">{stats?.active_users || 0}</p>
        </div>
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E8E8E8]">
          <p className="text-sm text-[#6F6F6F] font-medium">Total LLM Requests</p>
          <p className="text-3xl font-semibold text-[#1a1c1b] mt-2">{stats?.total_llm_requests || 0}</p>
        </div>
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E8E8E8]">
          <p className="text-sm text-[#6F6F6F] font-medium">Total Transactions</p>
          <p className="text-3xl font-semibold text-[#1a1c1b] mt-2">{stats?.total_transactions || 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        {/* Recent AI Logs */}
        <div className="bg-white rounded-[28px] p-6 shadow-sm border border-[#E8E8E8] flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-[#1a1c1b] flex items-center gap-2">
              <span className="material-symbols-outlined text-[#c7ff00] text-xl">neurology</span>
              Recent LLM Activity
            </h2>
          </div>
          <div className="flex-1 overflow-auto rounded-xl border border-gray-100 bg-gray-50/50">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-gray-100/50 text-[#6F6F6F] text-xs uppercase sticky top-0">
                <tr>
                  <th className="px-4 py-3 font-semibold">User</th>
                  <th className="px-4 py-3 font-semibold">Intent</th>
                  <th className="px-4 py-3 font-semibold">Provider</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.slice(0, 10).map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-[#1a1c1b] font-medium">
                      {log.user_name || "Unknown"}
                    </td>
                    <td className="px-4 py-3 text-[#6F6F6F]">
                      {log.intent || log.message_type}
                    </td>
                    <td className="px-4 py-3 text-[#6F6F6F]">
                      {log.provider || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        log.status === 'success' || log.status === 'transaction_finance_chat' || log.status === 'llm_usage' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[#6F6F6F]">No recent LLM logs.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* User Directory */}
        <div className="bg-white rounded-[28px] p-6 shadow-sm border border-[#E8E8E8] flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-[#1a1c1b] flex items-center gap-2">
              <span className="material-symbols-outlined text-[#c7ff00] text-xl">group</span>
              Registered Users
            </h2>
          </div>
          <div className="flex-1 overflow-auto rounded-xl border border-gray-100 bg-gray-50/50">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-gray-100/50 text-[#6F6F6F] text-xs uppercase sticky top-0">
                <tr>
                  <th className="px-4 py-3 font-semibold">Name</th>
                  <th className="px-4 py-3 font-semibold">Email</th>
                  <th className="px-4 py-3 font-semibold text-right">Transactions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.slice(0, 10).map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-[#1a1c1b] font-medium">{user.name}</td>
                    <td className="px-4 py-3 text-[#6F6F6F]">{user.email}</td>
                    <td className="px-4 py-3 text-[#1a1c1b] text-right font-medium">{user.transaction_count}</td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-[#6F6F6F]">No users found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
