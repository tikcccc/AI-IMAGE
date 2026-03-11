太棒了！選擇 Next.js 搭配 FastAPI 是一個非常現代且高效的架構。FastAPI 原生支援非同步 (Asynchronous) 處理，對於這種需要等待外部 API (中轉站) 回應的 I/O 密集型任務來說，效能表現極佳。

既然我們已經確定了方向，接下來為你整理一份完整的 **產品需求文件 (PRD, Product Requirements Document)**。這份文件可以作為你後續開發的藍圖，確保系統架構與功能邏輯清晰明確。

---

# 產品需求文件 (PRD)：AI 圖片處理 Web 應用

## 1. 產品概述 (Product Overview)

本專案旨在開發一個輕量級的單頁式網頁應用程式 (SPA)。使用者可以上傳單張圖片並輸入文字指令 (Prompt)，系統將透過 API 中轉站 (Vector Engine) 呼叫 `nano-banana-2` 模型處理圖片，並將處理後的結果即時顯示給使用者。本應用無須對話記憶功能，採用「單輪請求、單次處理」的模式。

## 2. 系統架構設計 (System Architecture)

系統採用前後端分離架構，以確保 API 金鑰的安全性與系統的可擴展性。

* **前端 (Client-side)：** Next.js (React) - 負責使用者介面、表單驗證與狀態管理。
* **後端 (Server-side)：** Python (FastAPI) - 作為安全閘道器，負責接收前端資料、圖片轉碼、以及與中轉站進行通訊。
* **AI 服務 (Third-party)：** Vector Engine API 中轉站 - 提供統一的介面呼叫 Nano Banana 2 (Gemini 3 Flash Image) 模型。

## 3. 核心功能需求 (Functional Requirements)

### 3.1 前端功能 (Next.js)

* **圖片上傳區塊：**
* 支援點擊選擇或拖曳上傳單張圖片。
* 支援常見圖片格式（如 `.jpg`, `.jpeg`, `.png`, `.webp`）。
* 上傳後需在畫面上顯示圖片預覽縮圖。
* 限制檔案大小（例如最大 5MB），超過時給予前端錯誤提示。


* **文字輸入區塊：**
* 提供一個必填的單行或多行文字輸入框，讓使用者輸入 Prompt。


* **提交與狀態管理：**
* 點擊「送出」按鈕後，按鈕需進入鎖定狀態 (Disabled)，防止重複點擊。
* 畫面上需有明顯的「處理中 (Loading)」視覺回饋（例如轉圈動畫或進度條），讓使用者知道系統正在等待 AI 運算。


* **結果展示區塊：**
* 成功接收後端回傳的資料後，在特定區域顯示 AI 處理完成的新圖片。
* 若發生錯誤，需將系統或後端傳來的錯誤訊息以友善的方式顯示給使用者。



### 3.2 後端功能 (FastAPI)

* **接收請求：** 提供一個 API 端點（如 `POST /api/process-image`）接收前端傳遞的 `multipart/form-data`（包含圖片與 Prompt）。
* **資料轉碼：** 將接收到的圖片二進位檔案 (Bytes) 即時轉換為 Base64 字串，並組合成 OpenAI Vision 支援的 Data URL 格式（如 `data:image/jpeg;base64,...`）。
* **封裝並轉發請求：** * 讀取環境變數 (`.env`) 中的中轉站 API Key 與 Base URL。
* 依照 Vector Engine 的 `chat/completions` 格式，將 Base64 圖片與 Prompt 封裝成 JSON payload。
* 使用非同步 HTTP 客戶端（如 `httpx`）發送請求給中轉站。


* **回應處理：** * 接收中轉站的 JSON 回應，提取出生成的圖片結果（URL 或 Markdown）。
* 將結果標準化後，回傳給 Next.js 前端。



## 4. 系統介面與資料定義 (API Contract)

為了讓前後端能順利對接，我們需要先定義好兩者溝通的橋樑（API 規格）。

### 前端呼叫後端的 API 端點

| 項目 | 說明 |
| --- | --- |
| **Endpoint** | `POST /api/process-image` |
| **Content-Type** | `multipart/form-data` |
| **Request Parameters** | `image`: 檔案 (File Object)<br>

<br>`prompt`: 字串 (String) |

### 後端回傳給前端的資料格式 (JSON)

**成功回應 (HTTP 200 OK):**

```json
{
  "status": "success",
  "data": {
    "result_image": "https://... 或 data:image/png;base64,..." 
  }
}

```

**失敗回應 (HTTP 400 / 500):**

```json
{
  "status": "error",
  "message": "中轉站處理失敗：餘額不足",
  "code": "INSUFFICIENT_QUOTA"
}

```

## 5. 非功能性需求 (Non-Functional Requirements)

* **安全性 (Security)：** * Vector Engine 的 API Key **絕對禁止**出現在 Next.js 的客戶端程式碼中。
* 必須配置跨來源資源共用 (CORS) 策略，FastAPI 僅允許來自 Next.js 網域的請求。


* **環境變數管理：** FastAPI 啟動時需驗證 `.env` 檔案中是否已確實配置 `PROXY_API_KEY`、`PROXY_URL` 與 `MODEL_NAME`，若缺失應阻止伺服器啟動並報錯。
* **例外處理 (Error Handling)：** FastAPI 需能妥善處理中轉站超時 (Timeout)、連線失敗或中轉站本身回傳的錯誤碼，並轉化為前端可理解的錯誤訊息。

## 6. 不在範圍內 (Out of Scope)

* 使用者登入與註冊系統 (Authentication)。
* 對話歷史紀錄儲存 (Database/Chat History)。
* 多張圖片同時上傳處理。
* 複雜的圖片裁切或編輯工具（如畫筆塗抹局部修改）。

