import { NextRequest } from "next/server";
import { AUTH_TOKEN_COOKIE } from "@/lib/auth-constants";
import { SERVER_API_BASE_URL, SERVER_SERVICE_BASE_URL } from "@/lib/api";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const servicePaths = new Set(["health"]);

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, context);
}

async function proxyBackendRequest(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { path } = await context.params;
  const targetUrl = buildTargetUrl(path, request.nextUrl.searchParams);
  const response = await fetch(targetUrl, {
    method: request.method,
    headers: buildForwardHeaders(request),
    body: hasRequestBody(request.method) ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: buildResponseHeaders(response),
  });
}

function buildTargetUrl(path: string[], searchParams: URLSearchParams): string {
  const targetBaseUrl = servicePaths.has(path[0] ?? "")
    ? SERVER_SERVICE_BASE_URL
    : SERVER_API_BASE_URL;
  const url = new URL(`${targetBaseUrl}/${path.map(encodeURIComponent).join("/")}`);

  searchParams.forEach((value, key) => {
    url.searchParams.append(key, value);
  });

  return url.toString();
}

function buildForwardHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  const cookieToken = request.cookies.get(AUTH_TOKEN_COOKIE)?.value;

  headers.delete("connection");
  headers.delete("content-length");
  headers.delete("expect");
  headers.delete("host");
  headers.delete("cookie");

  if (!headers.has("authorization") && cookieToken) {
    headers.set("Authorization", `Bearer ${cookieToken}`);
  }

  return headers;
}

function buildResponseHeaders(response: Response): Headers {
  const headers = new Headers(response.headers);

  headers.delete("content-encoding");
  headers.delete("content-length");
  headers.delete("transfer-encoding");

  return headers;
}

function hasRequestBody(method: string): boolean {
  return !["GET", "HEAD"].includes(method.toUpperCase());
}
