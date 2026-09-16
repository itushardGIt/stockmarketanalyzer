# Personal Portfolio App — Combined Design & Architecture (v3)

**Approach:** Manual statement upload (no broker API) + public market data + explicit vector DB for RAG, covering the full original feature set. This document supersedes the two earlier drafts and merges them into one reference.

---

## 1. Feature scope

| # | Feature | Data source in this design |
|---|---|---|
| 1 | Holdings dashboard/listing | Uploaded statement, stored relationally |
| 2 | Market trend charts | Public market data (`yfinance`) |
| 3 | Top gainers/losers | Public market data + NSE index constituent lists |
| 4 | Market tracking (near-real-time) | Public market data, polled on a schedule — **~15–20 min delayed**, not tick-level |
| 5 | Chat assistant (holdings + general) | LangGraph agent: tool-calls into relational store, RAG into vector store |
| 6 | Personal alerts (price/accumulation/watch triggers) | Deterministic rule engine over cached prices |
| 7 | Document downloads (P&L, tax) | Uploaded tax statement +/or own FIFO computation |

**Core design principle, unchanged from the original doc:** deterministic features (1–4, 6–7) are plain Python/SQL and never touch an LLM. Only feature 5 is agentic, and even there the agent's job is to call tools and narrate results, never to compute or recall numbers itself.

---

## 2. Architecture overview

Five layers (see diagram above):

1. **Ingestion** — manual holdings upload + scheduled public market data fetch
2. **Storage** — a relational store (source of truth for numbers) and a **separate vector store** (source of truth for retrievable knowledge)
3. **AI agent layer** — LangGraph orchestration, tool-calling, RAG, LangSmith tracing
4. **Streamlit app** — the UI across all seven features
5. **Alerts** — a branch off the app for outbound notifications

The two storage stores are drawn and treated separately on purpose: the relational store must never be approximated by embedding similarity, and the vector store should never be asked to hold anything that must be numerically exact. Section 5 covers each in technical detail.

---

## 3. Ingestion

### 3.1 Manual holdings upload

| Statement | Format to request | Contains |
|---|---|---|
| Holdings | XLSX/CSV (Zerodha Console export) | Quantity, avg. cost, current snapshot |
| Tradebook | XLSX/CSV | Every executed trade |
| Tax P&L | XLSX | Zerodha's own FIFO-computed STCG/LTCG |

**Flow:**
1. `st.file_uploader` accepts the file.
2. XLSX/CSV → `pandas.read_excel`/`read_csv` directly, validated against a `pydantic` model (column names, dtypes, no nulls in required fields) before acceptance.
3. PDF (fallback only, when XLSX/CSV isn't available) → `pdfplumber`/`camelot-py` for native PDFs; Tesseract OCR, or a HuggingFace layout model (`microsoft/table-transformer-detection`, `naver-clova-ix/donut-base`) only if the PDF is a scanned image — this should be rare for a Zerodha export.
4. **Confirmation gate**: render the parsed table with `st.dataframe`, diff it against the last stored snapshot (new positions, exits, quantity/avg-cost changes), and require explicit user confirmation before writing to the database. This is the same discipline as a portfolio-review confirmation step — never let a parse silently overwrite state.
5. On confirm: upsert into `holdings`, append to `portfolio_snapshots` for historical tracking (Zerodha's own holdings view doesn't retain your history — this table is what gives you a value-over-time chart).

**Pydantic schema sketch:**
```python
class HoldingRow(BaseModel):
    symbol: str
    exchange: Literal["NSE", "BSE"]
    quantity: float
    avg_cost: float
    sector: str | None = None

class UploadBatch(BaseModel):
    uploaded_at: datetime
    source_file: str
    rows: list[HoldingRow]
```

### 3.2 Public market data fetch

| Source | Role | Notes |
|---|---|---|
| `yfinance` (`.NS`/`.BO` suffixes) | Primary price/history provider | Free, unofficial wrapper, ~15–20 min delay, rate-limit gracefully |
| NSE index constituent CSVs (nseindia.com published lists) | Static reference data for gainers/losers universe | Downloaded occasionally, not scraped live — much less fragile than scraping the live site |
| NSE/BSE live site scraping | Explicitly **not** the foundation | Anti-bot, ToS gray area, breaks on site changes — a "maybe later," not a dependency |

**Provider abstraction** (so the price source is swappable later without touching the rest of the app):
```python
class PriceProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...
    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame: ...

class YFinanceProvider:
    def get_quote(self, symbol: str) -> Quote: ...
    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame: ...
```

**Scheduling:** APScheduler job every N minutes (market hours only) refreshes `price_cache` for held symbols + watchlist; a separate daily job refreshes the index-constituent list for gainers/losers.

**Gainers/losers computation:** fetch quotes for the constituent list, compute `day_change_pct` in pandas, `ORDER BY` — no dedicated third-party gainers/losers endpoint needed.

---

## 4. Storage layer — technical detail

### 4.1 Relational schema (SQLite for a single user; swap to Postgres only if you outgrow it)

| Table | Key columns | Purpose |
|---|---|---|
| `holdings` | symbol, exchange, quantity, avg_cost, sector, snapshot_date | Current + historical holdings snapshots |
| `trades` | symbol, side, quantity, price, trade_date, order_id | Full trade history from tradebook uploads |
| `tax_statements` | financial_year, stcg, ltcg, source_file, uploaded_at | Zerodha's own computed tax P&L per FY |
| `price_cache` | symbol, ltp, day_change_pct, fetched_at | Latest polled price per symbol |
| `portfolio_snapshots` | snapshot_date, total_invested, total_value, total_pnl | Value-over-time series, since brokers don't retain this for you |
| `alert_rules` | symbol, condition_type, threshold, status, created_at | User-defined trigger conditions |
| `alert_events` | rule_id, triggered_at, price_at_trigger, delivered | Fired-alert log |
| `chat_history` | session_id, role, content, created_at | Conversation log for the assistant |

### 4.2 Vector store — first-class component

**Choice:** Chroma (local, persistent directory, zero external service) — FAISS is a fine alternative if you want a lighter dependency; `pgvector` only makes sense if you've already moved the relational store to Postgres.

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (fast) or `BAAI/bge-base-en-v1.5` (higher quality) — both run locally via HuggingFace, no per-call cost.

**Collections (keep them separate, not one blended index):**

| Collection | Content | Populated by |
|---|---|---|
| `tax_rules` | Indian capital-gains tax rules, STCG/LTCG thresholds, STT treatment | One-time ingestion script, refreshed when rules change |
| `glossary` | Broker/market terminology (margin, T1 settlement, circuit limits, etc.) | One-time ingestion script |
| `notes` | Your own saved research notes/analysis | Ongoing, as you add notes through the UI |
| `news_digest` (optional, later) | Ingested news headlines, tagged with `ProsusAI/finbert` sentiment as metadata | Scheduled ingestion job, if you add this feature |

**Critical boundary, restated:** never index holdings, trades, or P&L numbers into the vector store. If a chat question needs an exact number, the agent must call a relational-store tool — retrieval is for concepts and explanations, not figures.

**Retrieval tool signature:**
```python
def search_knowledge_base(query: str, collection: str, k: int = 4) -> list[RetrievedChunk]:
    ...
```

---

## 5. AI agent layer — technical detail

### 5.1 LangGraph state and graph

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]
    intent: Literal["portfolio_data", "general_knowledge", "mixed", "chitchat"] | None
    tool_results: dict
```

**Nodes:**
- `route` — classifies the query into one of the intents above (a lightweight LLM call or a simple keyword/embedding classifier)
- `call_tools` — executes the relevant relational-store tool(s) based on intent
- `retrieve` — queries the vector store when general/tax/glossary knowledge is needed
- `generate` — synthesizes the final answer from `messages` + `tool_results` + retrieved chunks

**Edges:** `route` branches conditionally to `call_tools`, `retrieve`, both, or straight to `generate` for pure chit-chat — this conditional branching is exactly what LangGraph gives you over a linear chain.

### 5.2 Tool definitions (the deterministic layer the agent calls into)

```python
def get_holdings(as_of: date | None = None) -> list[Holding]: ...
def get_price(symbol: str) -> Quote: ...
def get_pnl_summary() -> PnLSummary: ...
def get_transaction_history(start: date, end: date, symbol: str | None = None) -> list[Trade]: ...
def get_concentration_report() -> ConcentrationReport: ...
def get_alerts(status: Literal["active", "triggered", "all"] = "active") -> list[AlertRule]: ...
def search_knowledge_base(query: str, collection: str, k: int = 4) -> list[RetrievedChunk]: ...
```

Every one of these has a single, testable, non-LLM implementation. The agent's only job is choosing which to call and phrasing the answer.

### 5.3 Model routing

| Role | Recommendation |
|---|---|
| Primary reasoning/orchestration | Hosted frontier model with strong function-calling (Claude or GPT-4o class) |
| Embeddings | Local HuggingFace `sentence-transformers` model — no API cost |
| Optional local/open-weight LLM | `Qwen2.5-7B-Instruct` or `Llama-3.1-8B-Instruct` via Ollama — the more reliable tool-callers among open-weight options, but validate carefully against real queries before trusting them with your numbers |

**LangSmith:** trace every graph run from day one. For this app specifically, watch for: wrong tool selected, tool called with wrong arguments, or the model answering a numeric question without calling a tool at all — that last one is the failure mode to actively hunt for.

---

## 6. Streamlit application

**Multipage structure**, one concern per page:

- `Home.py` — landing/summary
- `1_Dashboard.py` — holdings table, portfolio snapshot
- `2_Market_Trends.py` — Plotly charts (candlestick, moving averages)
- `3_Gainers_Losers.py` — ranked table
- `4_Chat_Assistant.py` — the LangGraph-backed chat interface
- `5_Alerts.py` — rule configuration + event log
- `6_Documents.py` — statement upload + P&L/tax export

**Caching:** `st.cache_data(ttl=...)` around price-fetch calls instead of a separate Redis layer — appropriate at single-user scale.

**UX notes (worth deliberate attention given your background):** Streamlit's defaults read as "internal tool," not "polished personal app." A few targeted choices go a long way without fighting the framework: a consistent color scale for P&L (not just red/green text — background tinting on rows reads faster), a persistent sidebar summary (invested/current/today's change) so it's visible from every page, and treating the upload-confirmation screen (§3.1 step 4) as a real UI moment rather than a raw dataframe dump — it's the one place a parsing mistake would otherwise go unnoticed.

---

## 7. Alerts engine

**Rule table** (`alert_rules`): symbol, condition_type (`price_above`, `price_below`, `pct_move_from_avg_cost`, `concentration_threshold`), threshold, status.

**Scheduler:** APScheduler job (every few minutes during market hours) reads active rules, checks against `price_cache`, writes to `alert_events` on trigger, and pushes a Telegram message via the Bot API. Email (SMTP) as a secondary channel.

**Hard rule:** no LLM anywhere in the trigger-evaluation path — this is pure `if condition met: fire` logic, auditable and testable.

---

## 8. Document generation

- Prefer Zerodha's own uploaded tax P&L export as the source of truth (§3.1) — cross-check against your own FIFO calculation only if you want a second opinion, don't replace the broker's figure with your own by default.
- PDF export via ReportLab/WeasyPrint (Jinja2 HTML template → PDF); Excel via `openpyxl`/`xlsxwriter`.
- `st.download_button` for delivery; a visible "not tax advice, verify with your CA" note in the UI itself, not just in this document.

---

## 9. Security & deployment

- Self-host (small VPS or home server) behind HTTPS (Caddy/Nginx) with `streamlit-authenticator` or basic auth in front — you're displaying real holdings and trade history, even without a broker API in the mix.
- Secrets via `.env`/environment variables, excluded from version control.
- Docker Compose: one container for the Streamlit app + scheduler process, no Redis/Celery needed at this scale (§5 of the earlier addendum still applies — SQLite + APScheduler covers it).

---

## 10. Project structure

```
portfolio_app/
├── app/
│   ├── Home.py
│   └── pages/
│       ├── 1_Dashboard.py
│       ├── 2_Market_Trends.py
│       ├── 3_Gainers_Losers.py
│       ├── 4_Chat_Assistant.py
│       ├── 5_Alerts.py
│       └── 6_Documents.py
├── core/
│   ├── ingestion/          # upload parsing + validation
│   ├── market_data/        # PriceProvider + yfinance implementation
│   ├── storage/            # SQLAlchemy models + session management
│   ├── agent/              # LangGraph graph, tool implementations, prompts
│   ├── rag/                # Chroma client, collection ingestion scripts
│   ├── alerts/             # rule engine + scheduler jobs
│   ├── documents/          # PDF/Excel generators
│   └── config.py
├── data/
│   ├── uploads/
│   ├── chroma_db/
│   └── portfolio.db
├── tests/
├── pyproject.toml
└── README.md
```

---

## 11. Phased build order

| Phase | Deliverable | AI involved? |
|---|---|---|
| 1 | Upload flow, relational schema, Dashboard page | No |
| 2 | Public price fetch, Market Trends + Gainers/Losers pages | No |
| 3 | Alerts engine + Telegram delivery, Document generation | No |
| 4 | Vector store ingestion (tax rules, glossary), LangGraph agent + tools, Chat Assistant page, LangSmith tracing | Yes |
| 5 | Hardening: auth, secrets, deployment, UX polish pass | No |

Same rationale as before: the deterministic tool layer (Phases 1–3) exists and is tested before the agent (Phase 4) is built on top of it.

---

## 12. Build prompt

Copy this into your coding assistant (e.g., Claude Code) to kick off implementation. It assumes you'll attach or paste this design document alongside it.

```
<role>
You are pair-programming with a senior engineer: 10+ years of Python, hands-on Streamlit
experience, and a UX design background. Do not explain basic Python, Streamlit, or web
concepts — assume fluency. Do explain architecture-specific tradeoffs, library-specific
gotchas (e.g., yfinance rate limiting, LangGraph state design, Chroma persistence), and
anything genuinely non-obvious about how the pieces fit together.
</role>

<context>
Attached is my full architecture design document for a personal portfolio-tracking app
(manual statement upload, no broker API; public market data via yfinance; SQLite +
Chroma vector store; a LangGraph agent for chat; Streamlit multipage UI). Treat it as
the source of truth for architecture decisions — don't re-litigate choices it already
made (e.g., don't propose Kite Connect, don't propose Redis/Celery, don't propose RAG
for portfolio numbers). If you think a decision in the document is actually wrong,
say so explicitly and argue for the alternative — don't silently deviate.
</context>

<goal_for_this_session>
Build Phase 1 only (see the document's phased roadmap): the manual upload flow, the
relational schema, and the Dashboard page. Do not start on market data, alerts, or the
agent yet, even if it's tempting to scaffold everything at once.
</goal_for_this_session>

<working_style>
1. Before writing any code, propose the concrete file/folder layout for Phase 1 (a
   subset of the document's project structure) and the SQLAlchemy models with full
   field definitions. Wait for my confirmation before generating code.
2. Use type hints everywhere, Pydantic v2 for validation models, SQLAlchemy 2.0-style
   models, and docstrings on public functions — match idiomatic modern Python, not
   Python 2-era patterns.
3. Write the upload-confirmation UI (§3.1 step 4 in the doc) as a real UX moment, not
   a bare st.dataframe dump — I care about this screen specifically since it's the one
   place a bad parse would otherwise go unnoticed. Propose the layout before coding it.
4. Include a pytest test for the upload parser (valid file, missing-column file,
   duplicate-symbol file) before considering the ingestion piece done.
5. Flag any place where you're making an assumption the document didn't specify
   (e.g., exact column names in a Zerodha export) rather than guessing silently —
   ask me for a sample export if you need one to get column names right.
6. Keep changes scoped to Phase 1. If you notice something Phase 1 will need from a
   later phase (e.g., a field the agent will eventually need), note it as a comment
   or a short flag to me rather than building it now.
</working_style>

<deliverable>
End this session with: the confirmed folder structure, working SQLAlchemy models,
the upload parser with validation and the confirmation UI, and passing tests — in
that order, checkpointed with me between each.
</deliverable>
```
