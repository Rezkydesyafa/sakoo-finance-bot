import { NextResponse, type NextRequest } from "next/server";
import { AUTH_TOKEN_COOKIE } from "@/lib/auth-constants";
import { normalizeBaseUrl } from "./lib/api";

const authRoutes = new Set(["/login", "/register"]);

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasToken = Boolean(request.cookies.get(AUTH_TOKEN_COOKIE)?.value);
  const isAuthRoute = authRoutes.has(pathname);
  const isFrontendApiRoute = pathname.startsWith("/api/");

  if (isFrontendApiRoute) {
    return NextResponse.next();
  }

  if (!hasToken && !isAuthRoute) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (hasToken && isAuthRoute) {
    const nextPath = request.nextUrl.searchParams.get("next") ?? "/";
    const dashboardUrl = request.nextUrl.clone();
    dashboardUrl.pathname = nextPath.startsWith("/") ? nextPath : "/";
    dashboardUrl.search = "";
    return NextResponse.redirect(dashboardUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
export const SERVER_API_BASE_URL = normalizeBaseUrl(
  process.env.NEXT_INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"
);
