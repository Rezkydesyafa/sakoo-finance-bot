export type LocationLike = {
  hostname: string;
  origin: string;
  port: string;
};

export const REPORT_PERIOD_OPTIONS = [
  { label: "Hari Ini", value: "day" },
  { label: "Minggu Ini", value: "week" },
  { label: "Bulan Ini", value: "month" },
] as const;

export function clearAuthSession(
  storage: { removeItem: (key: string) => void },
  cookieTarget: { cookie: string },
  storageKey: string,
  cookieName: string,
): void {
  storage.removeItem(storageKey);
  cookieTarget.cookie = `${cookieName}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function resolveBrowserApiBaseUrl(
  configuredBaseUrl: string | undefined,
  location: LocationLike,
): string {
  if (configuredBaseUrl?.trim()) return configuredBaseUrl;
  if (location.port === "3000" || location.port === "3001") {
    return `http://${location.hostname}:8000/api`;
  }
  return `${location.origin}/api`;
}

export function resolvePostLoginPath(isAdmin: boolean, requestedPath: string): string {
  return isAdmin && requestedPath === "/" ? "/?tab=admin" : requestedPath;
}

export function chooseFetchedModel(currentModel: string, models: string[]): string {
  if (models.length === 0 || models.includes(currentModel)) return currentModel;
  return models[0];
}

export function mergeById<T extends { id: number }>(
  current: T[],
  next: T[],
): T[] {
  const merged = new Map(current.map((item) => [item.id, item]));
  next.forEach((item) => merged.set(item.id, item));
  return [...merged.values()];
}

export function findCategoryId(
  categories: { id: number; name: string; type: string }[],
  name: string,
  type: string,
): number | null {
  const normalized = name.trim().toLocaleLowerCase("id-ID");
  return categories.find(
    (category) =>
      category.type === type &&
      category.name.trim().toLocaleLowerCase("id-ID") === normalized,
  )?.id ?? null;
}

export type CsvCell = string | number | null | undefined;

export function buildLlmProviderUpdatePayload<T extends { api_key?: string }>(
  payload: T,
): Omit<T, "api_key"> & { api_key?: string } {
  const { api_key, ...updates } = payload;
  return api_key?.trim() ? { ...updates, api_key: api_key.trim() } : updates;
}

export function toCsv(headers: string[], rows: CsvCell[][]): string {
  return [headers, ...rows]
    .map((row) => row.map(escapeCsvCell).join(","))
    .join("\r\n");
}

export function downloadCsv(
  filename: string,
  headers: string[],
  rows: CsvCell[][],
): void {
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", toCsv(headers, rows)], {
      type: "text/csv;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function escapeCsvCell(value: CsvCell): string {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}
