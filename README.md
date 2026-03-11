# AI 圖片處理 Demo Web App

以 `prd.md` 為需求來源，這個 repo 目前只包含本機可跑的最小 demo：

- `frontend/`: Next.js App Router + TypeScript 單頁表單
- `backend/`: FastAPI API gateway，代理呼叫 Vector Engine

## 本機啟動

### 一鍵啟動

先確認 `backend/.venv`、`frontend/node_modules`、`backend/.env` 已準備好，然後直接在 repo 根目錄執行：

```bash
./start-dev.sh
```

這會同時啟動：

- frontend: `http://localhost:3100`
- backend: `http://localhost:8001`

`frontend/.env.local` 若不存在，腳本會自動從 `frontend/.env.example` 建立；`backend/.env` 不會自動建立，因為你需要填入真實 provider 設定。

### 1. 啟動 backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

`backend/.env` 必填：

```bash
PROXY_API_KEY=...
PROXY_URL=https://api.vectorengine.ai/v1/chat/completions
MODEL_NAME=gemini-3.1-flash-image-preview
CORS_ORIGINS=http://localhost:3100
REQUEST_TIMEOUT_SECONDS=60
```

### 2. 啟動 frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

`frontend/.env.local`：

```bash
API_BASE_URL=http://localhost:8001
```

打開 `http://localhost:3100`，上傳一張圖片、輸入 prompt 後即可送出。

## API 流程

1. 前端檢查單檔、MIME 類型、5MB 上限、prompt 非空。
2. 前端用 `fetch` + `FormData` 呼叫 `POST /api/process-image`。
3. 後端再次驗證輸入，將圖片轉成 `data:<mime>;base64,...`。
4. 後端用 OpenAI-compatible `chat/completions` payload 呼叫 `PROXY_URL`。
5. 後端優先解析第一個可用圖片 URL；若只回 markdown 內容，也會擷取第一個圖片 URL。

注意：目前 backend 只支援同步的 OpenAI-compatible `chat/completions` 介面。已實測可用的組合是 `PROXY_URL=https://api.vectorengine.ai/v1/chat/completions` 搭配 `MODEL_NAME=gemini-3.1-flash-image-preview`。如果你要改接向量引擎文件中的 `fal-ai/nano-banana/edit` 這類非同步任務 API，還需要另外實作 `request_id` 輪詢，不能直接沿用現在這個 adapter。

## API Contract

請求：

- `POST /api/process-image`
- `Content-Type: multipart/form-data`
- fields: `image`, `prompt`

成功回應：

```json
{
  "status": "success",
  "data": {
    "result_image": "https://..."
  }
}
```

錯誤回應：

```json
{
  "status": "error",
  "message": "圖片處理失敗",
  "code": "PROVIDER_ERROR"
}
```

## 常見排查

- backend 啟動即失敗：檢查 `PROXY_API_KEY`、`PROXY_URL`、`MODEL_NAME` 是否存在。
- backend 啟動即失敗且提示 `PROXY_URL must include a concrete endpoint path`：表示你把 `PROXY_URL` 填成了根網域，需改成完整 API 端點，例如 `https://api.vectorengine.ai/v1/chat/completions`。
- 瀏覽器出現 CORS 錯誤：確認 `CORS_ORIGINS` 包含 `http://localhost:3100`。
- 前端送出後直接報錯：確認 `API_BASE_URL` 或 `NEXT_PUBLIC_API_BASE_URL` 指向實際 backend 位址，例如 `http://localhost:8001`。
- provider 成功但前端沒圖：檢查第三方回應是否真的有圖片 URL 或 markdown 圖片連結。
