export type UserRole = "admin" | "guest";

export type SessionUser = {
  username: string;
  role: UserRole;
  expiresAt: number;
};
const DEFAULT_AUTH_SECRET = "dev-auth-secret-change-me";
const encoder = new TextEncoder();
const decoder = new TextDecoder();

export const SESSION_COOKIE_NAME = "ai_image_session";

function getAuthSecret(): string {
  return process.env.AUTH_SECRET?.trim() || DEFAULT_AUTH_SECRET;
}

function encodeBase64Url(input: string | Uint8Array): string {
  const binary =
    typeof input === "string"
      ? input
      : Array.from(input, (value) => String.fromCharCode(value)).join("");

  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);

  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function signValue(value: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));

  return encodeBase64Url(new Uint8Array(signature));
}

function isValidRole(value: unknown): value is UserRole {
  return value === "admin" || value === "guest";
}

export async function readSessionFromToken(token: string | undefined | null): Promise<SessionUser | null> {
  if (!token) {
    return null;
  }

  const [payloadSegment, signatureSegment] = token.split(".");
  if (!payloadSegment || !signatureSegment) {
    return null;
  }

  const expectedSignature = await signValue(payloadSegment, getAuthSecret());
  if (expectedSignature !== signatureSegment) {
    return null;
  }

  try {
    const payload = JSON.parse(decoder.decode(decodeBase64Url(payloadSegment))) as {
      u?: unknown;
      r?: unknown;
      exp?: unknown;
    };

    if (typeof payload.u !== "string" || !isValidRole(payload.r) || typeof payload.exp !== "number") {
      return null;
    }

    if (!payload.u.trim()) {
      return null;
    }

    if (payload.exp <= Math.floor(Date.now() / 1000)) {
      return null;
    }

    return {
      username: payload.u,
      role: payload.r,
      expiresAt: payload.exp,
    };
  } catch {
    return null;
  }
}
