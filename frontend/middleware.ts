import { NextRequest, NextResponse } from "next/server";
import { readSessionFromToken, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function middleware(request: NextRequest) {
  const session = await readSessionFromToken(request.cookies.get(SESSION_COOKIE_NAME)?.value);
  const { pathname, search } = request.nextUrl;
  const loginUrl = new URL(`/login${search}`, request.url);
  const appUrl = new URL(`/ai-image${search}`, request.url);

  if (pathname === "/") {
    return NextResponse.redirect(session ? appUrl : loginUrl);
  }

  if (pathname.startsWith("/ai-image")) {
    if (!session) {
      return NextResponse.redirect(loginUrl);
    }

    return NextResponse.next();
  }

  if (pathname === "/login" && session) {
    return NextResponse.redirect(appUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
