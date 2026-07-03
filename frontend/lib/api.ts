import { SERVER_API_BASE_URL } from "@/middleware";
import { Capacitor } from "@capacitor/core";

const getBrowserApiBaseUrl = () => {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  if (typeof window !== "undefined") {
    if (Capacitor.isNativePlatform()) {
      return "http://192.168.1.102:8000/api";
    }

    // If running Next.js dev server (port 3000) locally or via LAN (Live Reload)
    if (window.location.port === "3000" || window.location.port === "3001") {
      return `http://${window.location.hostname}:8000/api`;
    }
  }

  // Fallback for online deployment (behind Nginx proxy on port 80/443)
  return "/api";
};

const BROWSER_API_BASE_URL = normalizeBaseUrl(getBrowserApiBaseUrl());
const BROWSER_SERVICE_BASE_URL = BROWSER_API_BASE_URL.replace(/\/api\/?$/, "");

export const SERVER_SERVICE_BASE_URL = SERVER_API_BASE_URL.replace(/\/api\/?$/, "");

export const API_BASE_URL =
  typeof window === "undefined" ? SERVER_API_BASE_URL : BROWSER_API_BASE_URL;
export const SERVICE_BASE_URL =
  typeof window === "undefined" ? SERVER_SERVICE_BASE_URL : BROWSER_SERVICE_BASE_URL;

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
  category_name?: string | null;
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

export type TransactionCreateRequest = {
  type: TransactionType;
  amount: number;
  category_id?: number | null;
  description?: string | null;
  transaction_date?: string;
};

export type TransactionUpdateRequest = {
  type?: TransactionType;
  amount?: number;
  category_id?: number | null;
  description?: string | null;
  transaction_date?: string;
};

export type TransactionTextParseRequest = {
  text: string;
};

export type TransactionTextParseResponse = {
  status: string;
  reply_text: string;
  transaction_id: number | null;
};

// Report types
export type ReportTransactionItem = {
  id: number;
  type: string;
  amount: string;
  category_id: number | null;
  category_name: string | null;
  description: string | null;
  transaction_date: string;
  source: string;
};

export type ReportSummaryResponse = {
  report_type: string;
  period_start: string;
  period_end: string;
  total_income: string;
  total_expense: string;
  net_balance: string;
  transaction_count: number;
  income_count: number;
  expense_count: number;
  transactions: ReportTransactionItem[];
  total_transactions: number;
  limit: number;
  offset: number;
  has_next: boolean;
};

export type ReportSummaryParams = {
  period?: "day" | "week" | "month" | "custom";
  date?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
};

export type ReportCategoryItem = {
  category_id: number | null;
  category_name: string;
  type: string;
  total_amount: string;
  transaction_count: number;
  percentage: string;
};

export type ReportCategoryResponse = {
  report_type: string;
  period_start: string;
  period_end: string;
  type: string | null;
  total_amount: string;
  items: ReportCategoryItem[];
};

export type ReportCategoryParams = {
  period?: "day" | "week" | "month" | "custom";
  date?: string;
  start_date?: string;
  end_date?: string;
  type?: TransactionType;
};

export type ReportPdfGenerateResponse = {
  report: {
    id: number;
    user_id: number;
    period_start: string;
    period_end: string;
    report_type: string;
    file_id: number | null;
    generated_from: string;
    status: string;
    created_at: string;
  };
  file: {
    id: number;
    filename: string;
    mime_type: string;
    size: number;
  };
  download_url: string;
};

export type AccountLinkingCodeResponse = {
  id: number;
  code: string;
  command: string;
  expired_at: string;
  created_at: string;
};

export type MediaFileResponse = {
  id: number;
  user_id: number;
  file_type: string;
  original_filename: string | null;
  stored_path: string;
  mime_type: string | null;
  size: number | null;
  source: string;
  created_at: string;
};

export type JobResponse = {
  id: number;
  user_id: number;
  job_type: string;
  status: string;
  result_id: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ReceiptOcrJobResponse = {
  job: JobResponse;
  message: string;
};

export type ReceiptOcrResponse = {
  id: number;
  user_id: number;
  media_file_id: number;
  ocr_text: string | null;
  merchant_name: string | null;
  receipt_date: string | null;
  total_amount: string | null;
  confidence: string | null;
  status: string;
  created_at: string;
};

export type PlatformAccountResponse = {
  platform: "telegram" | "whatsapp";
  platform_user_id: string | null;
  phone_number: string | null;
  chat_id: string | null;
  linked_at: string;
  is_active: boolean;
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

  auth: {
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
      apiRequest<UserResponse>("/auth/me", { token }),
    linkingCode: (token: string) =>
      apiRequest<AccountLinkingCodeResponse>("/auth/linking-codes", {
        method: "POST",
        token,
      }),
    platformAccounts: (token: string) =>
      apiRequest<PlatformAccountResponse[]>("/auth/platform-accounts", { token }),
  },

  // Legacy flat aliases
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
    apiRequest<UserResponse>("/auth/me", { token }),

  transactions: {
    list: (token: string, query?: TransactionListParams) =>
      apiRequest<TransactionListResponse>("/transactions", { token, query }),
    create: (token: string, payload: TransactionCreateRequest) =>
      apiRequest<Transaction>("/transactions", {
        method: "POST",
        token,
        body: JSON.stringify(payload),
      }),
    update: (token: string, id: number, payload: TransactionUpdateRequest) =>
      apiRequest<Transaction>(`/transactions/${id}`, {
        method: "PUT",
        token,
        body: JSON.stringify(payload),
      }),
    delete: (token: string, id: number) =>
      apiRequest<void>(`/transactions/${id}`, {
        method: "DELETE",
        token,
      }),
    parseText: (token: string, payload: TransactionTextParseRequest) =>
      apiRequest<TransactionTextParseResponse>("/transactions/parse", {
        method: "POST",
        token,
        body: JSON.stringify(payload),
      }),
  },

  reports: {
    summary: (token: string, params?: ReportSummaryParams) =>
      apiRequest<ReportSummaryResponse>("/reports/summary", { token, query: params }),
    category: (token: string, params?: ReportCategoryParams) =>
      apiRequest<ReportCategoryResponse>("/reports/category", { token, query: params }),
    pdfGenerate: (token: string, payload: { period?: string; generated_from?: string }) =>
      apiRequest<ReportPdfGenerateResponse>("/reports/pdf/generate", {
        method: "POST",
        token,
        body: JSON.stringify({ generated_from: "dashboard", ...payload }),
      }),
  },

  ocr: {
    runReceipt: (token: string, mediaId: number) =>
      apiRequest<ReceiptOcrJobResponse>(`/ocr/receipts/${mediaId}`, {
        method: "POST",
        token,
      }),
    receiptResult: (token: string, receiptId: number) =>
      apiRequest<ReceiptOcrResponse>(`/ocr/receipts/results/${receiptId}`, { token }),
  },

  jobs: {
    get: (token: string, jobId: number) =>
      apiRequest<JobResponse>(`/jobs/${jobId}`, { token }),
  },

  media: {
    upload: (token: string, file: File, fileType: string, source = "dashboard_upload") => {
      const formData = new FormData();
      formData.set("file", file);
      formData.set("file_type", fileType);
      formData.set("source", source);
      return apiRequest<MediaFileResponse>("/media", {
        method: "POST",
        token,
        body: formData,
      });
    },
    downloadUrl: (id: number) => `${API_BASE_URL}/media/${id}/download`,
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

export function normalizeBaseUrl(value: string): string {
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

  if (body && !(body instanceof FormData)) {
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

  if (response.status === 204) {
    return undefined as T;
  }

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
