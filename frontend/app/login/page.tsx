"use client";

import { FormEvent, useState } from "react";

type LoginSuccessResponse = {
  status: "success";
  data: {
    redirect_url: string;
  };
};

type LoginErrorResponse = {
  status: "error";
  message: string;
  code: string;
};

function getDisplayMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message === "Failed to fetch"
      ? "The sign-in request could not be completed. Please try again shortly."
      : error.message;
  }

  return "Sign-in failed. Please try again.";
}

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!username.trim() || !password) {
      setErrorMessage("Enter both username and password.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });
      const payload = (await response.json().catch(() => null)) as
        | LoginSuccessResponse
        | LoginErrorResponse
        | null;

      if (!response.ok || payload?.status !== "success") {
        const errorPayload = payload as LoginErrorResponse | null;
        throw new Error(errorPayload?.message || "Sign-in failed. Please try again.");
      }

      window.location.replace(payload.data.redirect_url);
    } catch (error) {
      setErrorMessage(getDisplayMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-block auth-brand">
          <span className="brand-mark">IS</span>
          <div>
            <p className="brand-name">ISBIM AI</p>
            <p className="brand-caption">Image processing workspace</p>
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-copy">
            <p className="auth-eyebrow">Login</p>
            <h1 className="auth-title">Sign in</h1>
            <p className="auth-copy-text">
              Use your assigned username and password to enter the AI image workspace.
            </p>
          </div>

          <label className="auth-field">
            <span>Username</span>
            <input
              autoComplete="username"
              name="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Enter your username"
            />
          </label>

          <label className="auth-field">
            <span>Password</span>
            <input
              autoComplete="current-password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
          </label>

          {errorMessage ? (
            <div className="message-box error-box" role="alert">
              {errorMessage}
            </div>
          ) : null}

          <div className="auth-submit-row">
            <button className="submit-button auth-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
            <p className="auth-submit-copy">You will be redirected to the main workspace after login.</p>
          </div>
        </form>
      </section>
    </main>
  );
}
