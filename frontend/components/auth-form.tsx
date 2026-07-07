"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState, useEffect } from "react";
import { ApiError, apiClient, buildApiUrl } from "@/lib/api";
import { saveAuthToken, getStoredAuthToken } from "@/lib/auth-storage";

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
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegister = mode === "register";

  useEffect(() => {
    if (getStoredAuthToken()) {
      router.replace("/");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (isRegister && password !== confirmPassword) {
      setError("Konfirmasi password tidak cocok dengan password.");
      return;
    }

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
      window.location.href = getNextPath();
    } catch (submitError) {
      setError(getAuthErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleGoogleLogin() {
    window.location.href = buildApiUrl("/auth/google/start", {
      next: getNextPath(),
    });
  }

  return (
    <div className="bg-surface-white w-full max-w-[480px] p-card-padding sm:p-10 relative overflow-hidden transition-all duration-300 hover:-translate-y-1 group" style={{ borderRadius: '28px', boxShadow: '0 10px 30px rgba(0,0,0,0.06)' }}>
      <div className="relative z-10 flex flex-col items-center w-full">
        {/* Logo & Greeting */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-surface-muted rounded-full flex items-center justify-center text-primary group-hover:scale-105 transition-transform duration-300">
            <span className="material-symbols-outlined text-[32px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              robot_2
            </span>
          </div>
        </div>
        
        <h2 className="font-headline-hero text-headline-hero text-center text-inverse-surface mb-2">
          {isRegister ? "Create Account" : "Welcome Back"}
        </h2>
        <p className="font-body-main text-body-main text-text-muted text-center mb-8 px-4">
          {isRegister ? "Sign up to start using your smart financial assistant." : "Log in to manage your smart financial assistant."}
        </p>

        <form className="w-full flex flex-col gap-4" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="relative w-full">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <span className="material-symbols-outlined text-text-muted text-[20px]">person</span>
              </div>
              <input 
                className="w-full bg-surface-muted rounded-full py-4 pl-12 pr-6 font-body-main text-body-main text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary-container focus:bg-surface-white transition-all border-none shadow-none" 
                placeholder="Full Name" 
                required 
                type="text" 
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          <div className="relative w-full">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <span className="material-symbols-outlined text-text-muted text-[20px]">mail</span>
            </div>
            <input 
              className="w-full bg-surface-muted rounded-full py-4 pl-12 pr-6 font-body-main text-body-main text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary-container focus:bg-surface-white transition-all border-none shadow-none" 
              placeholder="Email address" 
              required 
              type="email" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {isRegister && (
            <div className="relative w-full">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <span className="material-symbols-outlined text-text-muted text-[20px]">phone</span>
              </div>
              <input 
                className="w-full bg-surface-muted rounded-full py-4 pl-12 pr-6 font-body-main text-body-main text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary-container focus:bg-surface-white transition-all border-none shadow-none" 
                placeholder="Phone Number (Optional)" 
                type="tel" 
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
              />
            </div>
          )}

          <div className="relative w-full">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <span className="material-symbols-outlined text-text-muted text-[20px]">lock</span>
            </div>
            <input 
              className="w-full bg-surface-muted rounded-full py-4 pl-12 pr-12 font-body-main text-body-main text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary-container focus:bg-surface-white transition-all border-none shadow-none" 
              placeholder="Password" 
              required 
              type={showPassword ? "text" : "password"} 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button 
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-text-muted hover:text-text-primary transition-colors"
            >
              <span className="material-symbols-outlined text-[20px]">{showPassword ? "visibility" : "visibility_off"}</span>
            </button>
          </div>

          {isRegister && (
            <div className="relative w-full">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <span className="material-symbols-outlined text-text-muted text-[20px]">lock_reset</span>
              </div>
              <input 
                className="w-full bg-surface-muted rounded-full py-4 pl-12 pr-12 font-body-main text-body-main text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary-container focus:bg-surface-white transition-all border-none shadow-none" 
                placeholder="Konfirmasi Password" 
                required 
                type={showConfirmPassword ? "text" : "password"} 
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
              <button 
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-text-muted hover:text-text-primary transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">{showConfirmPassword ? "visibility" : "visibility_off"}</span>
              </button>
            </div>
          )}

          {error && (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              {error}
            </p>
          )}

          {!isRegister && (
            <div className="flex justify-end w-full px-2 mt-1 mb-2">
              <a className="font-label-button text-label-button text-text-muted hover:text-primary transition-colors cursor-pointer">
                Forgot Password?
              </a>
            </div>
          )}

          <button 
            className="w-full bg-primary-container text-text-primary rounded-full py-4 font-label-button text-label-button flex items-center justify-center gap-2 hover:-translate-y-1 hover:shadow-[0_12px_24px_rgba(199,255,0,0.25)] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none mt-2" 
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Processing..." : (isRegister ? "Sign Up" : "Log In")}
            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
          </button>
        </form>

        <div className="w-full flex items-center gap-4 my-8">
          <div className="h-px bg-border-light flex-grow"></div>
          <span className="font-label-muted text-label-muted text-text-muted">Or continue with</span>
          <div className="h-px bg-border-light flex-grow"></div>
        </div>

        <div className="w-full">
          <button
            className="w-full bg-surface-muted text-text-primary rounded-full py-3 px-6 font-label-button text-label-button flex items-center justify-center gap-2 hover:bg-surface-variant transition-colors border border-transparent"
            type="button"
            onClick={handleGoogleLogin}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Google
          </button>
        </div>

        <div className="mt-8 text-center w-full">
          <span className="font-body-main text-body-main text-text-muted">
            {isRegister ? "Already have an account?" : "Don't have an account?"}
          </span>
          <Link className="font-label-button text-label-button text-primary hover:underline ml-1" href={isRegister ? "/login" : "/register"}>
            {isRegister ? "Log In" : "Sign Up"}
          </Link>
        </div>
      </div>
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

    if (error.status >= 500) {
      return "Internal server error. Pastikan server backend FastAPI berjalan (localhost:8000).";
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
