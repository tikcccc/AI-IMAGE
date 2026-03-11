import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";
import { getCookieDomain, getRequestProtocol } from "@/lib/hosts";

const API_BASE_URL =
  (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001").replace(
    /\/$/,
    "",
  );

type UpstreamLoginSuccessResponse = {
  status: "success";
  data: {
    token: string;
  };
};

type UpstreamLoginErrorResponse = {
  status: "error";
  message: string;
  code: string;
};

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      password?: unknown;
      username?: unknown;
    };
    const upstreamResponse = await fetch(`${API_BASE_URL}/api/login`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        username: typeof body.username === "string" ? body.username : "",
        password: typeof body.password === "string" ? body.password : "",
      }),
    });
    const payload = (await upstreamResponse.json().catch(() => null)) as
      | UpstreamLoginSuccessResponse
      | UpstreamLoginErrorResponse
      | null;

    if (!upstreamResponse.ok || payload?.status !== "success") {
      const errorPayload = payload as UpstreamLoginErrorResponse | null;
      return NextResponse.json(
        {
          status: "error",
          message: errorPayload?.message || "Sign-in failed. Please try again.",
          code: errorPayload?.code || "LOGIN_FAILED",
        },
        { status: upstreamResponse.status || 502 },
      );
    }

    const protocol = getRequestProtocol(request.headers, request.nextUrl.protocol);
    const response = NextResponse.json({
      status: "success",
      data: {
        redirect_url: new URL("/ai-image", request.nextUrl.origin).toString(),
      },
    });

    response.cookies.set({
      name: SESSION_COOKIE_NAME,
      value: payload.data.token,
      httpOnly: true,
      sameSite: "lax",
      secure: protocol === "https",
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
      domain: getCookieDomain(),
    });

    return response;
  } catch {
    return NextResponse.json(
      {
        status: "error",
        message: "The sign-in service is temporarily unavailable.",
        code: "BACKEND_UNAVAILABLE",
      },
      { status: 502 },
    );
  }
}
