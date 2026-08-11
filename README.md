# OpenRouter Chat

A browser-based chat tool for exploring and comparing OpenRouter models side by side, with support for file uploads (images, text documents, PDFs) and streaming responses.

Runs entirely client-side — no backend, no build step. Just open `index.html` in a browser.

## Features

- **Dual model comparison** — query two models in parallel and view responses side by side
- **Live model picker** — fetches the full OpenRouter model catalog (`/v1/models`, public endpoint) into a searchable dropdown with context length and pricing hints
- **Multi-turn conversations** — each model maintains its own independent conversation history
- **Streaming** — tokens stream in incrementally via SSE (toggleable, on by default)
- **File uploads** — attach images, text files, and PDFs:
  - Images (png/jpg/gif/webp) sent as `image_url` base64 parts (requires a vision-capable model)
  - Text files (.txt, .md, .json, .py, .js, etc.) read and injected as document text
  - PDFs extracted client-side via [pdf.js](https://mozilla.github.io/pdf.js/) (loaded from CDN on first use)
- **Markdown rendering** — code blocks, lists, tables, links, blockquotes, headings
- **Token usage & cost** — per-response usage stats with cost computed from each model's pricing
- **Copy buttons** — copy any assistant response
- **Raw JSON debug panel** — collapsible panel showing the last request/response payload
- **No persistence** — API key and conversations reset on page reload (nothing stored)

## Getting Started

### Prerequisites

- An [OpenRouter](https://openrouter.ai) account and API key (`sk-or-v1-...`)
- A modern browser (Chrome, Firefox, Safari, Edge)

### Run

Because the tool makes cross-origin requests to OpenRouter and custom endpoints from the browser, you need to serve it via the included proxy server:

```bash
cd dhi
python3 server.py
```

This starts a local server on port 8765 that:
- Serves `index.html` at http://localhost:8765/
- Provides a `/proxy?url=<target>` endpoint that forwards requests to any external API, bypassing CORS restrictions (needed for endpoints behind Cloudflare or without CORS headers)

Then open http://localhost:8765/index.html in your browser.

> Opening the file directly via `file://` will not work — browsers block cross-origin `fetch` from the `null` origin.

### Using Custom Endpoints

Each model (A and B) can be toggled between **OpenRouter** mode and **Custom** mode via the `OR / Custom` button next to each model selector.

In Custom mode, a config panel expands with three fields:
- **Endpoint URL** — full chat completions URL (e.g. `https://api.example.com/v1/chat/completions`)
- **Bearer Token** — sent as `Authorization: Bearer <token>`
- **Model Name** — the model ID for that endpoint

Custom endpoint requests are automatically routed through the local proxy (`/proxy?url=...`) to bypass CORS. The proxy uses `curl` under the hood, so it handles Cloudflare TLS fingerprinting correctly.

Click **Fetch Models** to try loading the endpoint's model list (derives `/models` from the chat completions URL). Falls back to manual typing if the endpoint doesn't support it.

### Usage

1. Paste your OpenRouter API key in the **API Key** field
2. Click **Load Models** to fetch the model catalog into the dropdowns
3. Select models in **Model A** and **Model B** (leave one blank to query a single model)
4. (Optional) Click **Settings** to adjust:
   - Temperature (0–2)
   - Top-p (0–1)
   - Max tokens
   - System prompt
   - Streaming toggle
5. Type a message and press **Enter** (or click **Send**). Use **Shift+Enter** for a newline.
6. Attach files via the **+** button, drag-and-drop, or paste from clipboard.

## Model Selection Tips

- Browse all models at https://openrouter.ai/models
- Models with a `:free` suffix (e.g. `meta-llama/llama-3.1-8b-instruct:free`) cost nothing — great for testing
- For image/file processing, use vision-capable models such as:
  - `openai/gpt-4o`
  - `openai/gpt-4o-mini`
  - `anthropic/claude-3.5-sonnet`
  - `google/gemini-flash-1.5`
  - `meta-llama/llama-3.2-90b-vision-instruct`

## File Upload Behavior

| Type | Formats | Handling |
|------|---------|----------|
| Images | png, jpg, gif, webp | Base64-encoded, sent as `image_url` content parts |
| Text | txt, md, json, csv, py, js, ts, html, css, sql, and more | Read as text, injected as `=== Document: name ===` text parts |
| PDF | .pdf | Text extracted via pdf.js, injected as document text |

Attachments are sent to both models for comparison. They are cleared after each send, but the processed content is preserved in conversation history for multi-turn context.

## Tech Stack

- Single HTML file (vanilla JS, no framework, no build step)
- `server.py` — local proxy server (Python stdlib + curl) for serving static files and bypassing CORS
- CSS custom properties for theming
- [pdf.js](https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/) loaded lazily from CDN for PDF text extraction

## API Headers

The tool sends these headers with each chat completion request:

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <your-key>` |
| `Content-Type` | `application/json` |
| `HTTP-Referer` | `https://opencode.ai` |
| `X-Title` | `OpenRouter Chat` |
| `Accept` | `text/event-stream` (when streaming) |

## Security Notes

- The API key is entered in the browser and held in memory only — it is never persisted to disk, localStorage, or a remote server.
- All requests go directly from your browser to `https://openrouter.ai/api/v1/chat/completions`.
- OpenRouter sets `Access-Control-Allow-Origin: *` and allows the required headers via CORS preflight, so browser-based requests work without a proxy.
- Do not commit your API key to version control.

## Project Structure

```
dhi/
├── index.html   # The entire application (HTML + CSS + JS)
├── server.py    # Local proxy server (static files + CORS bypass via curl)
└── README.md    # This file
```

## License

Personal project. No license granted.
