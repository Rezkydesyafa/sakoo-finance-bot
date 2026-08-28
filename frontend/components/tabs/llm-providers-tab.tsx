"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError, type LlmProvider } from "@/lib/api";
import { clearAuthToken, getStoredAuthToken } from "@/lib/auth-storage";
import { chooseFetchedModel } from "@/lib/frontend-utils";

type Form = {
  name: string;
  base_url: string;
  model: string;
  api_key: string;
  enabled: boolean;
  priority: number;
};

type ProviderStatus = {
  kind: "success" | "error" | "info";
  message: string;
};

const emptyForm: Form = {
  name: "",
  base_url: "",
  model: "",
  api_key: "",
  enabled: true,
  priority: 0,
};

export function LlmProvidersTab() {
  const router = useRouter();
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [form, setForm] = useState<Form>(emptyForm);
  const [editing, setEditing] = useState<number | null>(null);
  const editingRef = useRef<number | null>(null);
  const [message, setMessage] = useState("Memuat provider...");
  const [saving, setSaving] = useState(false);
  const [checkingIds, setCheckingIds] = useState<Set<number>>(new Set());
  const [fetchingIds, setFetchingIds] = useState<Set<number>>(new Set());
  const [providerModels, setProviderModels] = useState<Record<number, string[]>>({});
  const [providerStatuses, setProviderStatuses] = useState<Record<number, ProviderStatus>>({});

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    apiClient.llmProviders
      .list(token)
      .then((response) => {
        setProviders(response.items);
        setMessage("");
      })
      .catch((error) => handleError(error, router, setMessage));
  }, [router]);

  function edit(provider: LlmProvider) {
    editingRef.current = provider.id;
    setEditing(provider.id);
    setForm({
      name: provider.name,
      base_url: provider.base_url,
      model: chooseFetchedModel(provider.model, providerModels[provider.id] ?? []),
      api_key: "",
      enabled: provider.enabled,
      priority: provider.priority,
    });
    setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    setSaving(true);
    setMessage("");
    try {
      const provider =
        editing === null
          ? await apiClient.llmProviders.create(token, form)
          : await apiClient.llmProviders.update(token, editing, { ...form });
      setProviders((current) =>
        editing === null
          ? [...current, provider]
          : current.map((item) => (item.id === provider.id ? provider : item)),
      );
      if (editing !== null) {
        setProviderModels((current) => omitProviderState(current, editing));
        setProviderStatuses((current) => omitProviderState(current, editing));
      }
      setForm(emptyForm);
      editingRef.current = null;
      setEditing(null);
      setMessage("Provider berhasil disimpan.");
    } catch (error) {
      handleError(error, router, setMessage);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    const token = getStoredAuthToken();
    if (!token || !window.confirm("Hapus provider ini?")) return;
    try {
      await apiClient.llmProviders.delete(token, id);
      setProviders((current) => current.filter((item) => item.id !== id));
      if (editingRef.current === id) {
        editingRef.current = null;
        setEditing(null);
        setForm(emptyForm);
      }
      setProviderModels((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
      setProviderStatuses((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    } catch (error) {
      handleError(error, router, setMessage);
    }
  }

  async function checkConnection(provider: LlmProvider) {
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    setCheckingIds((current) => new Set(current).add(provider.id));
    setProviderStatuses((current) => ({
      ...current,
      [provider.id]: { kind: "info", message: "Mengecek koneksi..." },
    }));
    try {
      const result = await apiClient.llmProviders.check(token, provider.id);
      setProviderStatuses((current) => ({
        ...current,
        [provider.id]: {
          kind: "success",
          message: `Terhubung · ${result.latency_ms} ms · ${result.model_count} model`,
        },
      }));
    } catch (error) {
      if (handleAuthError(error, router)) return;
      setProviderStatuses((current) => ({
        ...current,
        [provider.id]: { kind: "error", message: providerErrorMessage(error) },
      }));
    } finally {
      setCheckingIds((current) => withoutId(current, provider.id));
    }
  }

  async function fetchModels(provider: LlmProvider) {
    const token = getStoredAuthToken();
    if (!token) return router.replace("/login");
    setFetchingIds((current) => new Set(current).add(provider.id));
    setProviderStatuses((current) => ({
      ...current,
      [provider.id]: { kind: "info", message: "Mengambil daftar model..." },
    }));
    try {
      const result = await apiClient.llmProviders.models(token, provider.id);
      setProviderModels((current) => ({ ...current, [provider.id]: result.models }));
      if (editingRef.current === provider.id) {
        setForm((current) => ({
          ...current,
          model: chooseFetchedModel(current.model, result.models),
        }));
      }
      setProviderStatuses((current) => ({
        ...current,
        [provider.id]: {
          kind: "success",
          message:
            result.total > 0
              ? `${result.total} model berhasil diambil. Pilih model saat Edit.`
              : "Koneksi berhasil, tetapi provider tidak mengembalikan model.",
        },
      }));
    } catch (error) {
      if (handleAuthError(error, router)) return;
      setProviderStatuses((current) => ({
        ...current,
        [provider.id]: { kind: "error", message: providerErrorMessage(error) },
      }));
    } finally {
      setFetchingIds((current) => withoutId(current, provider.id));
    }
  }

  const editingModels = editing === null ? [] : providerModels[editing] ?? [];

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      <div>
        <h1 className="text-2xl font-bold text-[#1a1c1b]">LLM Providers</h1>
        <p className="text-sm text-[#6F6F6F]">
          Kelola gateway, cek koneksi, dan ambil daftar model OpenAI-compatible.
        </p>
      </div>

      {message && (
        <p
          className={`text-sm font-semibold ${
            message === "Akses admin ditolak." ? "text-red-600" : "text-[#4e6700]"
          }`}
        >
          {message}
        </p>
      )}

      <form onSubmit={save} className="bg-white rounded-[28px] p-6 card-shadow space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-[#1a1c1b]">
              {editing === null ? "Tambah Provider" : "Edit Provider"}
            </h2>
            {editing !== null && editingModels.length > 0 && (
              <p className="text-xs text-[#4e6700] mt-1">
                {editingModels.length} model tersedia dari provider.
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <TextField
            label="NAME"
            required
            value={form.name}
            onChange={(value) => setForm({ ...form, name: value })}
          />
          <TextField
            label="BASE URL"
            required
            value={form.base_url}
            onChange={(value) => setForm({ ...form, base_url: value })}
          />
          <label className="text-xs font-semibold text-[#6F6F6F]">
            MODEL
            <input
              required
              list={editingModels.length > 0 ? "provider-model-options" : undefined}
              value={form.model}
              onChange={(event) => setForm({ ...form, model: event.target.value })}
              placeholder="Ketik manual atau Fetch Models"
              className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]"
            />
            {editingModels.length > 0 && (
              <datalist id="provider-model-options">
                {editingModels.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            )}
          </label>
          <label className="text-xs font-semibold text-[#6F6F6F]">
            API KEY
            <input
              type="password"
              value={form.api_key}
              onChange={(event) => setForm({ ...form, api_key: event.target.value })}
              placeholder={editing === null ? "Wajib saat membuat" : "Kosongkan jika tidak diubah"}
              className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]"
              required={editing === null}
            />
          </label>
          <label className="text-xs font-semibold text-[#6F6F6F]">
            PRIORITY
            <input
              type="number"
              min={0}
              value={form.priority}
              onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })}
              className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]"
            />
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold text-[#1a1c1b] mt-6">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
            />
            Aktif
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            disabled={saving}
            className="bg-[#c7ff00] text-[#151f00] px-5 py-2.5 rounded-full text-xs font-bold disabled:opacity-50"
          >
            {saving ? "Menyimpan..." : editing === null ? "Tambah Provider" : "Simpan Perubahan"}
          </button>
          {editing !== null && (
            <button
              type="button"
              onClick={() => {
                editingRef.current = null;
                setEditing(null);
                setForm(emptyForm);
              }}
              className="bg-[#F1F2F0] px-5 py-2.5 rounded-full text-xs font-bold"
            >
              Batal
            </button>
          )}
        </div>
      </form>

      <div className="space-y-3">
        {providers.map((provider) => {
          const status = providerStatuses[provider.id];
          const models = providerModels[provider.id] ?? [];
          return (
            <div key={provider.id} className="bg-white rounded-2xl p-5 card-shadow space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-bold text-[#1a1c1b]">{provider.name}</h2>
                    <span
                      className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full ${
                        provider.enabled
                          ? "bg-[#eaffb0] text-[#385000]"
                          : "bg-[#F1F2F0] text-[#6F6F6F]"
                      }`}
                    >
                      {provider.enabled ? "Aktif" : "Nonaktif"}
                    </span>
                  </div>
                  <p className="text-xs text-[#6F6F6F] break-all mt-1">{provider.base_url}</p>
                  <p className="text-xs text-[#6F6F6F] mt-1">
                    Model: {provider.model} · Key: {provider.api_key_masked} · Prioritas: {provider.priority}
                  </p>
                  {status && (
                    <p
                      className={`text-xs font-semibold mt-3 ${
                        status.kind === "error"
                          ? "text-red-600"
                          : status.kind === "success"
                            ? "text-[#4e6700]"
                            : "text-[#6F6F6F]"
                      }`}
                    >
                      {status.message}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 shrink-0">
                  <button
                    type="button"
                    disabled={checkingIds.has(provider.id)}
                    onClick={() => checkConnection(provider)}
                    className="bg-[#151f00] text-white px-4 py-2 rounded-full text-xs font-bold disabled:opacity-50"
                  >
                    {checkingIds.has(provider.id) ? "Checking..." : "Check Connection"}
                  </button>
                  <button
                    type="button"
                    disabled={fetchingIds.has(provider.id)}
                    onClick={() => fetchModels(provider)}
                    className="bg-[#eaffb0] text-[#385000] px-4 py-2 rounded-full text-xs font-bold disabled:opacity-50"
                  >
                    {fetchingIds.has(provider.id) ? "Fetching..." : "Fetch Models"}
                  </button>
                  <button
                    type="button"
                    onClick={() => edit(provider)}
                    className="bg-[#F1F2F0] px-4 py-2 rounded-full text-xs font-bold"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(provider.id)}
                    className="bg-red-50 text-red-600 px-4 py-2 rounded-full text-xs font-bold"
                  >
                    Hapus
                  </button>
                </div>
              </div>

              {models.length > 0 && (
                <div className="border-t border-[#E8E8E8] pt-3">
                  <p className="text-[11px] font-bold text-[#6F6F6F] mb-2">
                    MODEL TERDETEKSI ({models.length})
                  </p>
                  <div className="flex flex-wrap gap-2 max-h-28 overflow-y-auto">
                    {models.map((model) => (
                      <button
                        type="button"
                        key={model}
                        onClick={() => {
                          edit(provider);
                          setForm((current) => ({ ...current, model }));
                        }}
                        className={`text-[11px] px-3 py-1.5 rounded-full border ${
                          model === provider.model
                            ? "bg-[#c7ff00] border-[#c7ff00] text-[#151f00] font-bold"
                            : "bg-white border-[#E8E8E8] text-[#5f5e5e]"
                        }`}
                      >
                        {model}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  required,
  onChange,
}: {
  label: string;
  value: string;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-xs font-semibold text-[#6F6F6F]">
      {label}
      <input
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full bg-[#F1F2F0] rounded-xl border-none py-3 px-4 text-sm text-[#1a1c1b]"
      />
    </label>
  );
}

function withoutId(current: Set<number>, id: number): Set<number> {
  const next = new Set(current);
  next.delete(id);
  return next;
}

function omitProviderState<T>(current: Record<number, T>, id: number): Record<number, T> {
  const next = { ...current };
  delete next[id];
  return next;
}

function handleAuthError(error: unknown, router: ReturnType<typeof useRouter>): boolean {
  if (error instanceof ApiError && error.status === 401) {
    clearAuthToken();
    router.replace("/login");
    return true;
  }
  return false;
}

function providerErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) return "Akses admin ditolak.";
  if (error instanceof ApiError && error.status === 502) return "Provider tidak dapat dihubungi atau responsnya tidak valid.";
  return "Operasi provider gagal. Cek base URL, API key, dan koneksi jaringan.";
}

function handleError(
  error: unknown,
  router: ReturnType<typeof useRouter>,
  setMessage: (message: string) => void,
) {
  if (handleAuthError(error, router)) return;
  setMessage(error instanceof ApiError && error.status === 403 ? "Akses admin ditolak." : "Provider belum dapat dimuat atau disimpan.");
}
