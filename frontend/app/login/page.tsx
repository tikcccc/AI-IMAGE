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

const authHighlights = [
  {
    title: "Protected workspace",
    description: "Access the image-processing console from a dedicated authenticated session.",
  },
  {
    title: "Preset credentials",
    description: "This project uses managed usernames and passwords without a separate sign-up flow.",
  },
  {
    title: "Direct handoff",
    description: "After sign-in you are redirected straight to the main AI image workspace.",
  },
] as const;

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
        <div className="auth-copy">
          <div className="brand-block auth-brand">
            <span className="brand-mark">IS</span>
            <div>
              <p className="brand-name">ISBIM AI</p>
              <p className="brand-caption">Image processing workspace</p>
            </div>
          </div>

          <div className="auth-copy-main">
            <p className="auth-kicker">Secure Access</p>
            <h1>Sign in to the AI image workspace</h1>
            <p>
              Enter the protected workflow for uploading source images, writing transformation
              prompts, and reviewing generated output from the same controlled session.
            </p>
          </div>

          <div className="auth-badge-row">
            <span className="status-pill status-working">Private environment</span>
            <span className="auth-chip">Single account flow</span>
          </div>

          <div className="auth-highlight-grid">
            {authHighlights.map((item) => (
              <article className="auth-highlight-card" key={item.title}>
                <p className="auth-highlight-title">{item.title}</p>
                <p className="auth-highlight-copy">{item.description}</p>
              </article>
            ))}
          </div>

          <div className="auth-side-note">
            <p className="auth-side-note-title">Session handoff</p>
            <p className="auth-side-note-copy">
              The sign-in page and the main workspace run on separate subdomains under the same
              root domain, then exchange access through the project session token.
            </p>
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-form-head">
            <p className="auth-form-kicker">Workspace Login</p>
            <h2 className="auth-form-title">Use your assigned credentials</h2>
            <p className="auth-form-copy">
              Sign in with the preset username and password configured for this environment.
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
            <p className="auth-submit-copy">
              You will be redirected to the main workspace immediately after authentication.
            </p>
          </div>
        </form>
      </section>
    </main>
  );
}
