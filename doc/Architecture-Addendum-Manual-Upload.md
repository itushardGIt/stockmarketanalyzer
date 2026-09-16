# Architecture Addendum — Manual Upload + Public Market Data

**Supersedes:** the Kite Connect ingestion sections of `Personal-Portfolio-App-Architecture.md`. The AI agent layer decisions in that document (LangGraph, tool-calling vs RAG split, LangSmith, model choice) are unchanged and still apply — this addendum only replaces §1–§2 (data sourcing) and simplifies §5 (storage) as a consequence.

**What changes and why:** No broker API, no daily token refresh, no live WebSocket connection to manage. You trade true real-time ticks for a much simpler, zero-external-dependency stack. This is a reasonable trade for a personal tool, but be clear-eyed about what you're giving up (see §4).

---

## 1. Holdings ingestion — manual statement upload

### 1.1 What to ask the user to export

Zerodha's Console already provides clean, structured exports — use these instead of scraping the mobile/web app or parsing PDFs where avoidable:

| Statement | Format | Contains |
|---|---|---|
| Holdings | XLSX/CSV | Current quantity, avg. cost, current holdings snapshot |
| Tradebook | XLSX/CSV | Every executed trade (buy/sell, price, quantity, date) |
| Tax P&L statement | XLSX | Realized STCG/LTCG, already FIFO-computed by Zerodha |

**Strongly prefer XLSX/CSV over PDF.** These are already tabular with stable column headers — `pandas.read_excel`/`read_csv` handles them directly, no ML model needed. Reserve PDF parsing for cases where only a PDF is available (e.g., an individual contract note).

### 1.2 Upload & parsing flow

1. `st.file_uploader` accepts the export (XLSX/CSV/PDF).
2. **XLSX/CSV path:** `pandas` reads it directly; validate columns/dtypes with a `pydantic` schema before accepting.
3. **PDF path (fallback only):** 
   - If it's a native (non-scanned) PDF — the normal case for Zerodha — use `pdfplumber` or `camelot-py` for table extraction. No ML model required; these are layout/heuristic-based table extractors.
   - Only if the PDF is a scanned image (rare for broker statements) would you need OCR: Tesseract first (fast, free, good on typed text), or a HuggingFace document-understanding model like `naver-clova-ix/donut-base` or `microsoft/table-transformer-detection` if Tesseract's output is messy on complex table layouts. Treat this as a last resort, not the default path.
4. **Confirmation gate before writing to the database** — show the parsed table back to the user in Streamlit (`st.dataframe`) and require an explicit "confirm" click before it overwrites the stored portfolio. This mirrors good practice you're likely already familiar with from manual portfolio-tracking workflows: never silently trust a parse, always let the human eyeball it first.
5. On confirm, upsert into your holdings table, and diff against the previous snapshot so you can show "what changed since last upload" (new positions, exits, quantity changes) — useful context for the chat assistant later.

### 1.3 Refresh cadence

This is inherently a manual, periodic process (whenever you export a fresh statement — daily, weekly, whatever fits your habit). Design the UI to make re-upload frictionless (one page, drag-and-drop, immediate diff view) rather than trying to force it into a "live sync" mental model it isn't.

---

## 2. Market data — public sources instead of a broker feed

Since holdings composition now comes from your upload, live market data only needs to answer "what's the current price of the symbols I hold (or watch)" — a much narrower need than a full broker feed.

### 2.1 Provider comparison

| Source | Cost | NSE/BSE coverage | Latency | Caveats |
|---|---|---|---|---|
| `yfinance` (unofficial Yahoo Finance wrapper) | Free | Good — use `.NS` (NSE) / `.BO` (BSE) ticker suffixes | ~15–20 min delayed | Unofficial API wrapper, not a documented/supported product — Yahoo can rate-limit or change behavior without notice. Widely used for personal projects; fine at low request volume |
| NSE India public site endpoints | Free | Native, most complete | Near real-time on the site itself | Requires session cookies/header spoofing to access programmatically, actively anti-bot, breaks whenever NSE changes its site, and sits in a legal gray area relative to NSE's terms of use — treat as fragile, not a foundation to build reliability on |
| `nsepython`/`nsetools` (community wrappers around the above) | Free | Same as above | Same as above | Same fragility, plus dependent on community maintenance |
| Alpha Vantage | Free tier (rate-limited) | Weak/inconsistent for Indian equities — primarily US-focused | Delayed | Not a good primary source for NSE/BSE |
| Twelve Data | Free tier available | Some NSE/BSE coverage — check current limits before relying on it | Delayed on free tier | Worth evaluating as a secondary/backup source |

**Recommendation:** `yfinance` as the primary price source — it's the most stable free option for NSE/BSE tickers in practice, good enough for a personal dashboard where 15–20 minute delay is an acceptable trade-off. Treat NSE's own site as a possible future enhancement, not a dependency, given how fragile scraping it tends to be.

### 2.2 Design it as a swappable "price provider" interface

Write one small abstraction — a `PriceProvider` class/interface with methods like `get_quote(symbol)`, `get_history(symbol, range)` — and implement it against `yfinance` now. This means if you ever do want a paid/broker-grade feed later (Kite Connect purely for read-only prices, or a different vendor), you swap the implementation behind that interface without touching the rest of the app. Good insurance for a decision you might revisit.

### 2.3 Top gainers / losers, without a dedicated "gainers/losers" API

NSE publishes index constituent lists (e.g., Nifty 50, Nifty Next 50, Nifty Midcap) as downloadable CSV files on its site — these are static reference data, not live scraping, and much less fragile to pull occasionally. Fetch quotes for the constituent list via `yfinance`, compute day-change % locally, and rank — no need for a dedicated third-party "gainers/losers" endpoint at all.

### 2.4 Market trend charts

Unchanged in approach from the original doc: `yfinance` historical OHLC → Plotly candlesticks/line charts via `st.plotly_chart`. Cache daily bars locally so you're not re-fetching the same history on every page load.

---

## 3. HuggingFace models worth knowing about for this app

| Use case | Model | Notes |
|---|---|---|
| RAG embeddings (tax rules, glossary, notes) | `sentence-transformers/all-MiniLM-L6-v2` (fast) or `BAAI/bge-base-en-v1.5` (higher quality) | Run locally, free, no API cost |
| Financial news/headline sentiment | `ProsusAI/finbert` | A BERT model fine-tuned specifically for financial-text sentiment (positive/negative/neutral) — could enrich a "market mood" widget if you later ingest news headlines |
| Scanned-document table extraction (PDF fallback only) | `microsoft/table-transformer-detection` + `-structure-recognition`, or `naver-clova-ix/donut-base` | Only needed if you hit a genuinely scanned (image) statement — see §1.2 |
| Optional local/open-weight LLM for the chat assistant | `meta-llama/Llama-3.1-8B-Instruct`, `Qwen/Qwen2.5-7B-Instruct`, `mistralai/Mistral-7B-Instruct`, `microsoft/Phi-3.5-mini-instruct` | Run via Ollama or vLLM for a fully local, zero-API-cost assistant. Among these, Qwen2.5-Instruct and Llama-3.1-Instruct currently tend to have the more reliable function/tool-calling support of the open-weight options — still meaningfully behind hosted frontier models on tool-call reliability, so validate carefully with real queries before trusting it with your numbers (see §4.3 of the main doc) |

None of these require fine-tuning — use them as-is (embeddings, sentiment scoring, or as the base chat model if you go the local-LLM route).

---

## 4. What you're trading away — be explicit about this with yourself

- **"Real-time" tracking becomes "~15–20 minute delayed."** Fine for portfolio monitoring and decision-making on a 12–18 month horizon (consistent with your own stated investment horizon elsewhere); not fine if you wanted intraday scalping-level freshness.
- **No live order/position sync** — if you place a trade on Zerodha, the app won't know until you next upload a statement. The upload-diff view (§1.2 step 5) is your substitute for "what changed."
- **Tax/P&L statements are more reliable, not less**, in this design — you're using Zerodha's own already-computed tax P&L export rather than reimplementing FIFO logic yourself, which removes a whole category of correctness risk from the original plan.

## 5. Storage — simplified

Because there's no live WebSocket ticker to buffer, you can drop Redis and Celery entirely for a first version:

| Store | Holds |
|---|---|
| SQLite (or Postgres if you prefer, but SQLite is genuinely enough at single-user scale) | Uploaded holdings snapshots, tradebook, tax statements, alert rules, chat history |
| Vector store (Chroma or FAISS, local) | Tax-rule text, glossary, notes — same narrow RAG scope as before |
| Streamlit's own `st.cache_data(ttl=...)` | In-memory cache for `yfinance` quote calls, instead of a separate Redis cache |

APScheduler (single-process, persisted job store) is still the right tool for periodic price refresh and alert-condition checks — no need for Celery's extra moving parts without a live ticker to justify it.

---

## 6. Everything else from the original document is unchanged

The AI agent layer design (§4 of the main architecture doc) — LangGraph orchestration, tool-calling for numbers vs. RAG for knowledge, LangSmith tracing, model choice, the phased build order — all still applies exactly as written. The only thing that moved is *where the numbers come from*: your own uploaded statement plus `yfinance`, instead of Kite Connect.
