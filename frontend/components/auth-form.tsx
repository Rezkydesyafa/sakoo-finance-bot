"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth-storage";

type AuthMode = "login" | "register";

type AuthFormProps = {
  mode: AuthMode;
};

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (isRegister) {
        await apiClient.register({
          name,
          email,
          password,
          phone_number: phoneNumber.trim() || null,
        });
      }

      const token = await apiClient.login({ email, password });
      saveAuthToken(token.access_token);
      router.replace(getNextPath());
      router.refresh();
    } catch (submitError) {
      setError(getAuthErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <p className="text-sm font-semibold uppercase text-emerald-700">
          Sakoo Finance Bot
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-950">
          {isRegister ? "Daftar akun" : "Masuk"}
        </h1>
      </div>

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        {isRegister ? (
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Nama</span>
            <input
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              minLength={1}
              maxLength={120}
              name="name"
              onChange={(event) => setName(event.target.value)}
              required
              type="text"
              value={name}
            />
          </label>
        ) : null}

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Email</span>
          <input
            autoComplete="email"
            className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            maxLength={255}
            minLength={3}
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>

        {isRegister ? (
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Nomor telepon
            </span>
            <input
              autoComplete="tel"
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              maxLength={32}
              name="phone_number"
              onChange={(event) => setPhoneNumber(event.target.value)}
              type="tel"
              value={phoneNumber}
            />
          </label>
        ) : null}

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Password</span>
          <input
            autoComplete={isRegister ? "new-password" : "current-password"}
            className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            maxLength={72}
            minLength={isRegister ? 8 : 1}
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>

        {error ? (
          <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">
            {error}
          </p>
        ) : null}

        <button
          className="w-full rounded-md bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? "Memproses..." : isRegister ? "Daftar" : "Masuk"}
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-slate-600">
        {isRegister ? "Sudah punya akun?" : "Belum punya akun?"}{" "}
        <Link
          className="font-semibold text-emerald-700 hover:text-emerald-800"
          href={isRegister ? "/login" : "/register"}
        >
          {isRegister ? "Masuk" : "Daftar"}
        </Link>
      </p>
    </div>
  );
}

function getNextPath(): string {
  const searchParams = new URLSearchParams(window.location.search);
  const nextPath = searchParams.get("next");

  return nextPath?.startsWith("/") ? nextPath : "/";
}

function getAuthErrorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    return "API belum bisa dihubungi. Pastikan backend aktif dan buka frontend lewat localhost.";
  }

  if (error instanceof ApiError) {
    const detail = getPayloadDetail(error.payload);

    if (detail) {
      return detail;
    }

    if (error.status === 409) {
      return "Email sudah terdaftar.";
    }

    if (error.status === 401) {
      return "Email atau password tidak sesuai.";
    }
  }

  return "Proses autentikasi gagal.";
}

function getPayloadDetail(payload: unknown): string | null {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    Array.isArray(payload.detail)
  ) {
    return payload.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg);
        }

        return null;
      })
      .filter(Boolean)
      .join(", ");
  }

  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return null;
}
