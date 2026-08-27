import assert from "node:assert/strict";
import test from "node:test";
import {
  buildLlmProviderUpdatePayload,
  clearAuthSession,
  findCategoryId,
  mergeById,
  REPORT_PERIOD_OPTIONS,
  resolveBrowserApiBaseUrl,
  toCsv,
} from "../lib/frontend-utils.ts";

test("logout clears local token and expires the auth cookie", () => {
  let removed = "";
  const storage = { removeItem: (key: string) => { removed = key; } };
  const cookies = { cookie: "" };

  clearAuthSession(storage, cookies, "sakoo_auth_token", "sakoo_auth");

  assert.equal(removed, "sakoo_auth_token");
  assert.match(cookies.cookie, /^sakoo_auth=;.*Max-Age=0/);
});

test("pagination appends new transactions without duplicating ids", () => {
  const merged = mergeById(
    [{ id: 2, amount: 20 }, { id: 1, amount: 10 }],
    [{ id: 1, amount: 15 }, { id: 3, amount: 30 }],
  );

  assert.deepEqual(merged, [
    { id: 2, amount: 20 },
    { id: 1, amount: 15 },
    { id: 3, amount: 30 },
  ]);
});

test("report period choices map to backend period values", () => {
  assert.deepEqual(
    REPORT_PERIOD_OPTIONS.map(({ value }) => value),
    ["day", "week", "month"],
  );
});

test("receipt category resolves an expense category id", () => {
  const categories = [
    { id: 1, name: "Lainnya", type: "income" },
    { id: 2, name: "Lainnya", type: "expense" },
  ];

  assert.equal(findCategoryId(categories, "lainnya", "expense"), 2);
  assert.equal(findCategoryId(categories, "Tidak Ada", "expense"), null);
});

test("browser API URL prefers env configuration and CSV escapes values", () => {
  const location = { hostname: "localhost", origin: "http://localhost:3000", port: "3000" };
  assert.equal(
    resolveBrowserApiBaseUrl("https://api.example/v1", location),
    "https://api.example/v1",
  );
  assert.equal(
    resolveBrowserApiBaseUrl(undefined, location),
    "http://localhost:8000/api",
  );
  assert.equal(toCsv(["Nama"], [['Warung "Enak", Jakarta']]), 'Nama\r\n"Warung ""Enak"", Jakarta"');
});

test("LLM provider updates omit a blank API key", () => {
  assert.deepEqual(
    buildLlmProviderUpdatePayload({ name: "Primary", api_key: "" }),
    { name: "Primary" },
  );
  assert.deepEqual(
    buildLlmProviderUpdatePayload({ api_key: "new-secret" }),
    { api_key: "new-secret" },
  );
});
