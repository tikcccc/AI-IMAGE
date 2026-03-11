export function getRequestProtocol(headers: Headers, fallbackProtocol?: string): string {
  const forwardedProtocol = headers.get("x-forwarded-proto")?.split(",")[0]?.trim();

  if (forwardedProtocol) {
    return forwardedProtocol;
  }

  return fallbackProtocol?.replace(/:$/u, "") || "http";
}

export function getCookieDomain(): string | undefined {
  const explicitDomain = process.env.SESSION_COOKIE_DOMAIN?.trim();
  return explicitDomain || undefined;
}
