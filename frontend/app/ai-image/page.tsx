"use client";

import { ChangeEvent, DragEvent, FormEvent, useEffect, useRef, useState } from "react";

const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"];
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;

type AccountSummary = {
  username: string;
  role: "admin" | "guest";
  usage_count: number;
  usage_limit: number | null;
  remaining_generations: number | null;
  is_limited: boolean;
};

type ApiSuccessResponse = {
  status: "success";
  data: {
    account: AccountSummary;
    result_image: string;
  };
};

type ApiErrorResponse = {
  status: "error";
  message: string;
  code: string;
};

type AccountSuccessResponse = {
  status: "success";
  data: AccountSummary;
};

function validateImageFile(file: File | null): string | null {
  if (!file) {
    return "Select an image before submitting.";
  }

  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return "Only JPG, PNG, and WEBP images are supported.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "The selected image must be smaller than 5 MB.";
  }

  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function getFileTypeLabel(file: File): string {
  const normalizedType = file.type.replace("image/", "").toUpperCase();

  if (normalizedType === "JPEG") {
    return "JPG";
  }

  return normalizedType;
}

function getServerErrorMessage(errorPayload: ApiErrorResponse | null): string {
  if (!errorPayload?.message.trim()) {
    return "Could not generate the result. Please try again.";
  }

  return errorPayload.message;
}

function getDisplayErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message === "Failed to fetch"
      ? "The service is temporarily unavailable. Please try again later."
      : error.message;
  }

  return "Could not generate the result. Please try again.";
}

export default function HomePage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const dragDepthRef = useRef(0);
  const [account, setAccount] = useState<AccountSummary | null>(null);
  const [accountError, setAccountError] = useState<string>("");
  const [isLoadingAccount, setIsLoadingAccount] = useState<boolean>(true);
  const [isLoggingOut, setIsLoggingOut] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [prompt, setPrompt] = useState<string>("");
  const [resultImage, setResultImage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isDragActive, setIsDragActive] = useState<boolean>(false);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl("");
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  useEffect(() => {
    let isMounted = true;

    async function loadAccount() {
      try {
        const response = await fetch("/api/account", {
          cache: "no-store",
        });
        const payload = (await response.json().catch(() => null)) as
          | AccountSuccessResponse
          | ApiErrorResponse
          | null;

        if (!response.ok || payload?.status !== "success") {
          const errorPayload = payload as ApiErrorResponse | null;

          if (errorPayload?.code === "AUTH_REQUIRED" || errorPayload?.code === "INVALID_SESSION") {
            window.location.reload();
            return;
          }

          throw new Error(errorPayload?.message || "Could not load the account session.");
        }

        if (!isMounted) {
          return;
        }

        setAccount(payload.data);
        setAccountError("");
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setAccount(null);
        setAccountError(getDisplayErrorMessage(error));
      } finally {
        if (isMounted) {
          setIsLoadingAccount(false);
        }
      }
    }

    void loadAccount();

    return () => {
      isMounted = false;
    };
  }, []);

  function resetFileInput() {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function clearTransientState() {
    setResultImage("");
    setErrorMessage("");
  }

  function applySelectedFile(file: File | null) {
    const validationError = validateImageFile(file);

    if (validationError) {
      setSelectedFile(null);
      clearTransientState();
      setErrorMessage(validationError);
      resetFileInput();
      return;
    }

    setSelectedFile(file);
    clearTransientState();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    applySelectedFile(event.target.files?.[0] ?? null);
  }

  function handleDragEnter(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (isSubmitting) {
      return;
    }

    dragDepthRef.current += 1;
    setIsDragActive(true);
  }

  function handleDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (isSubmitting) {
      return;
    }

    event.dataTransfer.dropEffect = "copy";
    setIsDragActive(true);
  }

  function handleDragLeave(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (isSubmitting) {
      return;
    }

    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragActive(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();

    dragDepthRef.current = 0;
    setIsDragActive(false);

    if (isSubmitting) {
      return;
    }

    applySelectedFile(event.dataTransfer.files?.[0] ?? null);
  }

  function handlePromptChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setPrompt(event.target.value);

    if (errorMessage) {
      setErrorMessage("");
    }
  }

  function handleRemoveFile() {
    setSelectedFile(null);
    clearTransientState();
    setIsDragActive(false);
    resetFileInput();
  }

  function handleResetWorkspace() {
    setSelectedFile(null);
    setPrompt("");
    setPreviewUrl("");
    clearTransientState();
    setIsDragActive(false);
    dragDepthRef.current = 0;
    resetFileInput();
  }

  function getDownloadFilename() {
    if (!selectedFile) {
      return "processed-image.png";
    }

    const mimeType = resultImage.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,/)?.[1] ?? selectedFile.type;
    const extension = mimeType.split("/")[1]?.replace("jpeg", "jpg") || "png";
    const originalName = selectedFile.name.replace(/\.[^.]+$/, "");

    return `${originalName}-processed.${extension}`;
  }

  async function handleDownloadResult() {
    if (!resultImage) {
      return;
    }

    try {
      const link = document.createElement("a");
      link.href = resultImage;
      link.download = getDownloadFilename();
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setErrorMessage("Could not download the result image. Please try again.");
    }
  }

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      const response = await fetch("/api/logout", {
        method: "POST",
      });
      const payload = (await response.json().catch(() => null)) as
        | {
            status: "success";
            data: {
              redirect_url: string;
            };
          }
        | ApiErrorResponse
        | null;

      if (!response.ok || payload?.status !== "success") {
        const errorPayload = payload as ApiErrorResponse | null;
        throw new Error(errorPayload?.message || "Could not sign out.");
      }

      window.location.replace(payload.data.redirect_url);
    } catch (error) {
      setErrorMessage(getDisplayErrorMessage(error));
      setIsLoggingOut(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isLoadingAccount || !account) {
      setErrorMessage("Account session is not ready yet. Please try again.");
      return;
    }

    const normalizedPrompt = prompt.trim();
    const file = selectedFile;
    const fileError = validateImageFile(file);

    if (fileError || !file) {
      setErrorMessage(fileError ?? "Select an image before submitting.");
      return;
    }

    if (!normalizedPrompt) {
      setErrorMessage("Enter edit instructions before submitting.");
      return;
    }

    const formData = new FormData();
    formData.append("image", file);
    formData.append("prompt", normalizedPrompt);

    setIsSubmitting(true);
    setErrorMessage("");
    setResultImage("");

    try {
      const response = await fetch("/api/process-image", {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json().catch(() => null)) as
        | ApiSuccessResponse
        | ApiErrorResponse
        | null;

      if (!response.ok || payload?.status !== "success") {
        const errorPayload = payload as ApiErrorResponse | null;
        throw new Error(getServerErrorMessage(errorPayload));
      }

      setResultImage(payload.data.result_image);
      setAccount(payload.data.account);
    } catch (error) {
      setErrorMessage(getDisplayErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  const hasWorkspaceContent = Boolean(selectedFile || prompt || resultImage || errorMessage);

  const status = isSubmitting
    ? {
        tone: "working",
        label: "Processing",
      }
    : isLoadingAccount
      ? {
          tone: "working",
          label: "Checking session",
        }
    : errorMessage
      ? {
          tone: "critical",
          label: "Needs attention",
        }
      : resultImage
        ? {
            tone: "success",
            label: "Result ready",
          }
        : selectedFile
          ? {
              tone: "ready",
              label: "Ready to submit",
            }
          : {
              tone: "idle",
              label: "Waiting for input",
          };

  const accountSummary = isLoadingAccount
    ? "Checking account"
    : account
      ? account.role === "guest"
        ? `${account.username} · ${account.usage_count}/${account.usage_limit ?? 100} used`
        : `${account.username} · unlimited access`
      : accountError || "Account unavailable";

  const accountCaption = account
    ? account.role === "guest"
      ? `${account.remaining_generations ?? 0} image generations remaining`
      : "Admin account with no usage limit"
    : "Session information will appear here once loaded.";

  return (
    <main className="page-shell">
      <div className="page-inner">
        <header className="product-header">
          <div className="brand-block">
            <span className="brand-mark">IA</span>
            <div>
              <p className="brand-name">ISBIM AI</p>
              <p className="brand-caption">Image transformation workspace</p>
            </div>
          </div>

          <div className="header-controls">
            <div className="account-card">
              <p className="account-title">{accountSummary}</p>
              <p className="account-copy">{accountCaption}</p>
            </div>

            <div className={`status-pill status-${status.tone}`}>{status.label}</div>

            <button
              className="secondary-button compact-button"
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut || isSubmitting}
            >
              {isLoggingOut ? "Signing out..." : "Log out"}
            </button>
          </div>
        </header>

        <form className="workspace-stack" onSubmit={handleSubmit}>
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Prepare your request</h2>
                <p className="panel-copy">
                  Upload the source image on the left, then describe the intended output on the right.
                </p>
              </div>
              <span className="panel-meta">One image, up to 5 MB</span>
            </div>

            <div className="request-composer">
              <div className="request-media-stack">
                <label
                  className={`upload-field${selectedFile ? " has-file" : ""}${isDragActive ? " is-drag-active" : ""}`}
                  htmlFor="image-upload"
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <input
                    ref={fileInputRef}
                    id="image-upload"
                    name="image"
                    type="file"
                    accept={ALLOWED_IMAGE_TYPES.join(",")}
                    onChange={handleFileChange}
                  />
                  <div className="upload-copy">
                    <span className="upload-title">
                      {selectedFile ? "Replace source image" : "Drag an image here or click to upload"}
                    </span>
                    <span className="upload-caption">
                      Drop a JPG, PNG, or WEBP image here, or browse from your device.
                    </span>
                  </div>

                  <div className="upload-chip-row">
                    <span className="meta-chip">{selectedFile ? formatFileSize(selectedFile.size) : "Max 5 MB"}</span>
                    <span className="meta-chip">
                      {selectedFile ? getFileTypeLabel(selectedFile) : "JPG / PNG / WEBP"}
                    </span>
                  </div>
                </label>

                <div
                  className={`preview-frame source-frame${isDragActive ? " is-drag-active" : ""}`}
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {previewUrl ? (
                    <img className="preview-image" src={previewUrl} alt="Selected source preview" />
                  ) : (
                    <div className="empty-state">
                      <p className="empty-title">Source preview</p>
                      <p className="empty-copy">
                        Upload an image to inspect it before submitting the transformation request.
                      </p>
                    </div>
                  )}

                  {isDragActive ? (
                    <div className="drop-overlay" aria-hidden="true">
                      <p className="drop-overlay-title">Drop image here</p>
                      <p className="drop-overlay-copy">Release to upload and replace the current preview.</p>
                    </div>
                  ) : null}
                </div>

                <div className="file-summary">
                  <div>
                    <p className="summary-label">Selected file</p>
                    <p className="summary-value">
                      {selectedFile ? selectedFile.name : "No file chosen yet"}
                    </p>
                  </div>

                  {selectedFile ? (
                    <button
                      className="text-button"
                      type="button"
                      onClick={handleRemoveFile}
                      disabled={isSubmitting}
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="request-editor">
                <label className="prompt-field">
                  <span className="field-label">Prompt</span>
                  <textarea
                    name="prompt"
                    value={prompt}
                    onChange={handlePromptChange}
                    placeholder="Example: Preserve the main structure, refine the composition, and generate a cleaner modern version with clearer visual hierarchy."
                    rows={10}
                  />
                </label>

                <div className="action-row">
                  <button className="submit-button" type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Processing..." : "Generate result"}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={handleResetWorkspace}
                    disabled={!hasWorkspaceContent || isSubmitting}
                  >
                    Clear workspace
                  </button>
                </div>

                {errorMessage || resultImage ? (
                  <div
                    className={`message-box ${errorMessage ? "error-box" : "success-box"}`}
                    role={errorMessage ? "alert" : "status"}
                    aria-live="polite"
                  >
                    {errorMessage
                      ? errorMessage
                      : "Result ready. Review it below or download it directly."}
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="panel result-panel">
            <div className="panel-header">
              <div>
                <h2>Review the output</h2>
                <p className="panel-copy">
                  Review the generated image, then open or download the final output.
                </p>
              </div>
              <span className="panel-meta">
                {resultImage ? "Result available" : isSubmitting ? "In progress" : "Awaiting submission"}
              </span>
            </div>

            {isSubmitting ? (
              <div className="loading-card" aria-live="polite">
                <span className="spinner" />
                <div>
                  <p className="loading-title">Processing your image</p>
                  <p className="loading-copy">
                    The image and prompt are being submitted. The result will appear here as soon
                    as it is ready.
                  </p>
                </div>
              </div>
            ) : resultImage ? (
              <div className="result-stack">
                <div className="result-frame">
                  <img className="result-image" src={resultImage} alt="Processed image result" />
                </div>

                <div className="result-actions">
                  <button
                    className="submit-button"
                    type="button"
                    onClick={handleDownloadResult}
                  >
                    Download image
                  </button>
                </div>
              </div>
            ) : (
              <div className="result-placeholder">
                <p className="empty-title">
                  {previewUrl ? "Ready to process" : "Your result will appear here"}
                </p>
                <p className="empty-copy">
                  {previewUrl
                    ? "Your source image is loaded. Submit the request when the instructions are ready."
                    : "Upload an image and enter instructions to generate a processed version."}
                </p>
              </div>
            )}
          </section>
        </form>
      </div>
    </main>
  );
}
