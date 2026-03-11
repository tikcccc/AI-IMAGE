import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";

const API_BASE_URL =
  (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001").replace(
    /\/$/,
    "",
  );

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const sessionToken = request.cookies.get(SESSION_COOKIE_NAME)?.value;

  if (!sessionToken) {
    return NextResponse.json(
      {
        status: "error",
        message: "Sign in first.",
        code: "AUTH_REQUIRED",
      },
      { status: 401 },
    );
  }

  try {
    const upstreamResponse = await fetch(`${API_BASE_URL}/api/account`, {
      method: "GET",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
      },
    });
    const rawBody = await upstreamResponse.text();

    return new Response(rawBody, {
      status: upstreamResponse.status,
      headers: {
        "content-type": upstreamResponse.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        status: "error",
        message: "The account details are temporarily unavailable.",
        code: "BACKEND_UNAVAILABLE",
      },
      { status: 502 },
    );
  }
}
