import { NextResponse } from "next/server";

const API_BASE_URL =
  (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001").replace(
    /\/$/,
    "",
  );
const USAGE_LIMIT_ERROR_PATTERN = /\b(insufficient|quota|credit|balance|exhausted)\b/i;

export const runtime = "nodejs";

type UpstreamErrorPayload = {
  code?: unknown;
  detail?: unknown;
  error?: unknown;
  message?: unknown;
};

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseErrorPayload(rawBody: string): UpstreamErrorPayload | null {
  if (!rawBody.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawBody);
    return parsed && typeof parsed === "object" ? (parsed as UpstreamErrorPayload) : null;
  } catch {
    return null;
  }
}

function getNestedErrorMessage(error: unknown): string {
  if (!error || typeof error !== "object") {
    return "";
  }

  const nestedMessage = (error as { message?: unknown }).message;
  return isNonEmptyString(nestedMessage) ? nestedMessage : "";
}

function getUserFacingErrorMessage(
  payload: UpstreamErrorPayload | null,
  rawBody: string,
  status: number,
): string {
  const code = isNonEmptyString(payload?.code) ? payload.code : "";
  const message = isNonEmptyString(payload?.message) ? payload.message : "";
  const detail = isNonEmptyString(payload?.detail) ? payload.detail : "";
  const nestedMessage = getNestedErrorMessage(payload?.error);
  const normalizedErrorText = [code, message, detail, nestedMessage, rawBody].join(" ").toLowerCase();

  if (USAGE_LIMIT_ERROR_PATTERN.test(normalizedErrorText)) {
    return "Usage limit reached. Please try again later.";
  }

  switch (code) {
    case "INVALID_PROMPT":
      return "Enter editing instructions before submitting.";
    case "UNSUPPORTED_IMAGE_TYPE":
      return "Only JPG, PNG, and WEBP images are supported.";
    case "EMPTY_IMAGE":
      return "Upload a valid image before submitting.";
    case "IMAGE_TOO_LARGE":
      return "The selected image must be smaller than 5 MB.";
    case "INVALID_INPUT":
      return "Check the image and instructions, then try again.";
    case "PROVIDER_TIMEOUT":
      return "The request is taking longer than expected. Please try again.";
    case "BACKEND_UNAVAILABLE":
      return "The service is temporarily unavailable. Please try again later.";
    default:
      break;
  }

  if (status === 504) {
    return "The request is taking longer than expected. Please try again.";
  }

  return "Could not generate the result. Please try again.";
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const upstreamResponse = await fetch(`${API_BASE_URL}/api/process-image`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
    const rawBody = await upstreamResponse.text();

    if (upstreamResponse.ok) {
      return new Response(rawBody, {
        status: upstreamResponse.status,
        headers: {
          "content-type": upstreamResponse.headers.get("content-type") || "application/json",
        },
      });
    }

    const errorPayload = parseErrorPayload(rawBody);

    return NextResponse.json(
      {
        status: "error",
        message: getUserFacingErrorMessage(errorPayload, rawBody, upstreamResponse.status),
        code: isNonEmptyString(errorPayload?.code) ? errorPayload.code : "PROCESS_IMAGE_FAILED",
      },
      { status: upstreamResponse.status },
    );
  } catch {
    return NextResponse.json(
      {
        status: "error",
        message: "The service is temporarily unavailable. Please try again later.",
        code: "BACKEND_UNAVAILABLE",
      },
      { status: 502 },
    );
  }
}
