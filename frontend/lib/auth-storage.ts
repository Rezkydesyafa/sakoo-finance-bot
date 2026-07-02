import {
  AUTH_TOKEN_COOKIE,
  AUTH_TOKEN_MAX_AGE_SECONDS,
  AUTH_TOKEN_STORAGE_KEY,
} from "@/lib/auth-constants";

export function saveAuthToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  document.cookie = `${AUTH_TOKEN_COOKIE}=${encodeURIComponent(
    token,
  )}; Path=/; Max-Age=${AUTH_TOKEN_MAX_AGE_SECONDS}; SameSite=Lax`;
}

export function getStoredAuthToken(): string | null {
  return getCookieAuthToken() ?? localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function clearAuthToken(): void {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  document.cookie = `${AUTH_TOKEN_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function getCookieAuthToken(): string | null {
  const prefix = `${AUTH_TOKEN_COOKIE}=`;
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));

  if (!cookie) {
    return null;
  }

  return decodeURIComponent(cookie.slice(prefix.length));
}
