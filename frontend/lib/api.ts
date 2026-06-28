const DEFAULT_API_BASE_URL = "http://localhost:8000/api";
const BROWSER_API_BASE_URL = "/api/backend";

export const SERVER_API_BASE_URL = normalizeBaseUrl(
  process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
);
export const SERVER_SERVICE_BASE_URL = SERVER_API_BASE_URL.replace(/\/api\/?$/, "");

export const API_BASE_URL =
  typeof window === "undefined" ? SERVER_API_BASE_URL : BROWSER_API_BASE_URL;
export const SERVICE_BASE_URL =
  typeof window === "undefined" ? SERVER_SERVICE_BASE_URL : BROWSER_API_BASE_URL;

export type HealthResponse = {
  status: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
};

export type RegisterRequest = {
  name: string;
  email: string;
  password: string;
  phone_number?: string | null;
};

export type UserResponse = {
  id: number;
  name: string;
  email: string;
  phone_number: string | null;
  created_at: string;
  updated_at: string;
};

export type TransactionType = "income" | "expense";

export type Transaction = {
  id: number;
  type: TransactionType;
  amount: string;
  category_id: number | null;
  description: string | null;
  transaction_date: string;
  source: string;
  created_at: string;
  updated_at: string;
};

export type TransactionListResponse = {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
};

export type TransactionListParams = {
  start_date?: string;
  end_date?: string;
  category_id?: number;
  type?: TransactionType;
  limit?: number;
  offset?: number;
};

type ApiRequestOptions = RequestInit & {
  token?: string;
  query?: Record<string, string | number | boolean | undefined | null>;
};

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export const apiClient = {
  health: () => serviceRequest<HealthResponse>("/health"),
  databaseHealth: () => serviceRequest<HealthResponse>("/health/db"),
  wahaHealth: () => serviceRequest<HealthResponse>("/health/waha"),
  register: (payload: RegisterRequest) =>
    apiRequest<UserResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (payload: { email: string; password: string }) =>
    apiRequest<AuthTokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: (token: string) =>
    apiRequest<UserResponse>("/auth/me", {
      token,
    }),
  transactions: {
    list: (token: string, query?: TransactionListParams) =>
      apiRequest<TransactionListResponse>("/transactions", { token, query }),
  },
};

export function buildApiUrl(
  path: string,
  query?: ApiRequestOptions["query"],
): string {
  return buildUrl(API_BASE_URL, path, query);
}

export function buildServiceUrl(
  path: string,
  query?: ApiRequestOptions["query"],
): string {
  return buildUrl(SERVICE_BASE_URL, path, query);
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>(buildApiUrl(path, options.query), options);
}

export async function serviceRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return request<T>(buildServiceUrl(path, options.query), options);
}

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

function buildUrl(
  baseUrl: string,
  path: string,
  query?: ApiRequestOptions["query"],
): string {
  const resolvedPath = path.startsWith("/") ? path : `/${path}`;
  const isAbsoluteUrl = /^https?:\/\//.test(baseUrl);
  const url = new URL(
    `${baseUrl}${resolvedPath}`,
    isAbsoluteUrl ? undefined : "http://frontend.local",
  );

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  });

  return isAbsoluteUrl ? url.toString() : `${url.pathname}${url.search}`;
}

async function request<T>(
  url: string,
  options: ApiRequestOptions,
): Promise<T> {
  const { token, headers, body } = options;
  const requestHeaders = new Headers(headers);

  requestHeaders.set("Accept", "application/json");

  if (body) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...toRequestInit(options),
    body,
    headers: requestHeaders,
  });

  const payload = await parsePayload(response);

  if (!response.ok) {
    throw new ApiError(response.statusText, response.status, payload);
  }

  return payload as T;
}

function toRequestInit(options: ApiRequestOptions): RequestInit {
  const init = { ...options };

  delete init.token;
  delete init.query;

  return init;
}

async function parsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type");

  if (contentType?.includes("application/json")) {
    return response.json();
  }

  return response.text();
}
