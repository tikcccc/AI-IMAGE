import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";
import { getCookieDomain, getRequestProtocol } from "@/lib/hosts";

export async function POST(request: NextRequest) {
  const protocol = getRequestProtocol(request.headers, request.nextUrl.protocol);
  const response = NextResponse.json({
    status: "success",
    data: {
      redirect_url: new URL("/login", request.nextUrl.origin).toString(),
    },
  });

  response.cookies.set({
    name: SESSION_COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: protocol === "https",
    path: "/",
    expires: new Date(0),
    domain: getCookieDomain(),
  });

  return response;
}
