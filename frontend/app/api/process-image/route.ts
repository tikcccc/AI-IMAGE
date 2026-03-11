import { NextResponse } from "next/server";

const API_BASE_URL =
  (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001").replace(
    /\/$/,
    "",
  );

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const upstreamResponse = await fetch(`${API_BASE_URL}/api/process-image`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });

    return new Response(await upstreamResponse.text(), {
      status: upstreamResponse.status,
      headers: {
        "content-type": upstreamResponse.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        status: "error",
        message: `Could not reach the image backend at ${API_BASE_URL}.`,
        code: "BACKEND_UNAVAILABLE",
      },
      { status: 502 },
    );
  }
}
