"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError, type LlmProvider } from "@/lib/api";
import { clearAuthToken, getStoredAuthToken } from "@/lib/auth-storage";

type Form = { name: string; base_url: string; model: string; api_key: string; enabled: boolean; priority: number };
const emptyForm: Form = { name: "", base_url: "", model: "", api_key: "", enabled: true, priority: 0 };

export function LlmProvidersTab() {
  const router = useRouter();
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [form, setForm] = useState<Form>(emptyForm);
  const [editing, setEditing] = useState<number | null>(null);
  const [message, setMessage] = useState("Memuat provider...");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    apiClient.llmProviders.list(token).then((response) => {
      setProviders(response.items);
      setMessage("");
    }).catch((error) => handleError(error, router, setMessage));
  }, [router]);

  function edit(provider: LlmProvider) {
    setEditing(provider.id);
    setForm({ name: provider.name, base_url: provider.base_url, model: provider.model, api_key: "", enabled: provider.enabled, priority: provider.priority });
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    setSaving(true); setMessage("");
    try {
      const provider = editing === null
        ? await apiClient.llmProviders.create(token, form)
        : await apiClient.llmProviders.update(token, editing, { ...form });
      setProviders((current) => editing === null ? [...current, provider] : current.map((item) => item.id === provider.id ? provider : item));
      setForm(emptyForm); setEditing(null); setMessage("Provider berhasil disimpan.");
    } catch (error) { handleError(error, router, setMessage); }
    finally { setSaving(false); }
  }

  async function remove(id: number) {
    const token = getStoredAuthToken();
    if (!token || !window.confirm("Hapus provider ini?")) return;
    try { await apiClient.llmProviders.delete(token, id); setProviders((current) => current.filter((item) => item.id !== id)); }
    catch (error) { handleError(error, router, setMessage); }
  }

  return <div className="space-y-6 max-w-5xl mx-auto pb-10">
    <div><h1 className="text-2xl font-bold text-[#1a1c1b]">LLM Providers</h1><p className="text-sm text-[#6F6F6F]">Kelola gateway dan model AI untuk aplikasi.</p></div>
    {message && <p className={`text-sm font-semibold ${message === "Akses admin ditolak." ? "text-red-600" : "text-[#4e6700]"}`}>{message}</p>}
    <form onSubmit={save} className="bg-white rounded-[28px] p-6 card-shadow space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {(["name", "base_url", "model"] as const).map((field) => <label key={field} className="text-xs font-semibold text-[#6F6F6F]">{field.replace("_", " ").toUpperCase()}<input required value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]" /></label>)}
        <label className="text-xs font-semibold text-[#6F6F6F]">API KEY<input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder={editing === null ? "Wajib saat membuat" : "Kosongkan jika tidak diubah"} className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]" required={editing === null} /></label>
        <label className="text-xs font-semibold text-[#6F6F6F]">PRIORITY<input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]" /></label>
        <label className="flex items-center gap-2 text-sm font-semibold text-[#1a1c1b] mt-6"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> Aktif</label>
      </div>
      <div className="flex gap-2"><button disabled={saving} className="bg-[#c7ff00] text-[#151f00] px-5 py-2.5 rounded-full text-xs font-bold">{saving ? "Menyimpan..." : editing === null ? "Tambah Provider" : "Simpan Perubahan"}</button>{editing !== null && <button type="button" onClick={() => { setEditing(null); setForm(emptyForm); }} className="bg-[#F1F2F0] px-5 py-2.5 rounded-full text-xs font-bold">Batal</button>}</div>
    </form>
    <div className="space-y-3">{providers.map((provider) => <div key={provider.id} className="bg-white rounded-2xl p-5 card-shadow flex flex-col sm:flex-row sm:items-center justify-between gap-4"><div><h2 className="font-bold text-[#1a1c1b]">{provider.name}</h2><p className="text-xs text-[#6F6F6F]">{provider.base_url} · {provider.model}</p><p className="text-xs text-[#6F6F6F] mt-1">Key: {provider.api_key_masked} · Prioritas: {provider.priority} · {provider.enabled ? "Aktif" : "Nonaktif"}</p></div><div className="flex gap-2"><button onClick={() => edit(provider)} className="bg-[#F1F2F0] px-4 py-2 rounded-full text-xs font-bold">Edit</button><button onClick={() => remove(provider.id)} className="bg-red-50 text-red-600 px-4 py-2 rounded-full text-xs font-bold">Hapus</button></div></div>)}</div>
  </div>;
}

function handleError(error: unknown, router: ReturnType<typeof useRouter>, setMessage: (message: string) => void) {
  if (error instanceof ApiError && error.status === 401) { clearAuthToken(); router.replace("/login"); return; }
  setMessage(error instanceof ApiError && error.status === 403 ? "Akses admin ditolak." : "Provider belum dapat dimuat atau disimpan.");
}
