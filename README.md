# Personal Portfolio Desk

Personal portfolio tracking application built around manual Zerodha statement uploads, delayed public market data, SQLite, a Streamlit UI, and an optional LangGraph assistant.

This project follows the attached architecture documents. It does not use a broker API, WebSockets, Redis, Celery, or an LLM to calculate portfolio numbers.

## Current Status

### Implemented

- Phase 1: Holdings upload, validation, confirmation gate, SQLite schema, snapshot diffs, and Dashboard.
- Phase 2: `yfinance` quote/history provider, SQLite price cache, Chart page, public Gainers/Losers page, stock details, recommendations, and IPO scanner.
- Phase 4 initial slice: Chroma persistence, local Hugging Face embeddings, LangGraph tools/agent, chat page, optional LangSmith tracing, and knowledge-note indexing.

### Not Yet Implemented

- Tradebook ingestion.
- Tax P&L ingestion.
- PDF/native table extraction and OCR fallback.
- Phase 3 alerts, APScheduler refresh jobs, Telegram delivery, and document generation.
- Full Phase 4 knowledge-base ingestion scripts for tax rules and glossary documents.
- Phase 5 authentication, deployment, and production hardening.

## Architecture

```text
Zerodha CSV/XLSX
        |
        v
Streamlit upload -> pandas normalization -> Pydantic validation
        |
        v
Human confirmation gate -> SQLAlchemy -> SQLite
                                  |
                                  +--> holdings snapshots and diffs
                                  +--> cached public prices

yfinance -> PriceProvider -> price_cache -> charts and ranking pages

Knowledge notes -> Hugging Face embeddings -> Chroma

User question -> LangGraph agent
                 |                |
                 v                v
          SQLite tools       Chroma retrieval
          exact numbers      explanations and notes
                 \                /
                  v              v
                    OpenAI chat model
                         |
                         v
                    Streamlit response
                         |
                         +--> optional LangSmith trace
```

The relational database and vector store are intentionally separate. Holdings, prices, and P&L are never answered from embedding similarity.

## Technology Map

| Component | Technology | Purpose |
|---|---|---|
| UI | Streamlit | Multipage dashboard, upload review, charts, and chat |
| Relational storage | SQLite + SQLAlchemy 2.0 | Source of truth for holdings and exact numeric data |
| Tabular parsing | pandas | CSV/XLSX ingestion |
| Validation | Pydantic v2 | Typed row validation and upload rejection |
| Public prices | yfinance | Delayed NSE/BSE quotes and OHLC history |
| Charts | Plotly | Candlestick market-trend visualization |
| Vector store | Chroma | Persistent explanatory knowledge retrieval |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` via LangChain HuggingFace | Local, free text embeddings |
| Agent orchestration | LangGraph | Tool-calling assistant workflow |
| LLM | OpenAI `gpt-4o-mini` | Natural-language routing, tool selection, and response synthesis |
| Agent tools | LangChain tools | Exact holdings, cached price, and P&L access |
| Observability | LangSmith, optional | Traces graph runs, tool calls, and model behavior |
| Tests | pytest | Parser and market-data service tests |

## Project Layout

```text
app.py                         Streamlit entry point and navigation
pages/
  1_Dashboard.py              Current holdings dashboard
  2_Upload_Statements.py      Holdings upload and confirmation workflow
        3_Market_Trends.py          Held-symbol line, bar, or candlestick chart
        4_Gainers_Losers.py         Ranked public quote view
        6_Stock_Details.py          Quote, fundamentals, and trend screen
        7_IPO_Scanner.py             Public IPO snapshot and research table
        8_Recommendations.py        Portfolio-wide sector and trend screen
  5_Chat_Assistant.py         LangGraph chat UI
core/config.py                Session credential policy
core/ingestion/               Pydantic schemas and Holdings parser
core/market_data/             PriceProvider, yfinance, cache service, universe loader
core/storage/                 SQLAlchemy models, SQLite setup, repositories
core/rag/                     Chroma and Hugging Face retrieval
core/agent/                   LangGraph graph and relational tools
tests/                        Automated tests
data/                          Runtime SQLite and Chroma files; keep out of Git
requirements.txt              pip dependencies
pyproject.toml                Project metadata and pytest configuration
```

## Installation

Use Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The current environment has been validated with Python 3.14. Chroma and sentence-transformers download additional packages and the embedding model is downloaded on first Chroma use.

## Run the Application

```powershell
streamlit run app.py
```

The sidebar requires an OpenAI API key before the application pages are unlocked. The key is held in the Streamlit session and is not written to SQLite.

### Optional LangSmith Tracing

LangSmith is disabled by default. Enable **Enable LangSmith tracing** in the sidebar only when you want graph traces. When enabled, provide a LangSmith API key. The application sets `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, and the default project name `portfolio-assistant` for the current process.

When tracing is off, the application sets `LANGCHAIN_TRACING_V2=false` and does not require a LangSmith key.

## User Workflow

### 1. Upload Holdings

1. Export a structured Holdings CSV or XLSX from Zerodha Console.
2. Open **Upload statements**.
3. Upload the file.
4. Review normalized symbols, exchanges, quantities, average costs, invested value, and the previous-snapshot diff.
5. Select the review checkbox.
6. Confirm the replacement.

The parser supports the sample CSV format and Zerodha Holdings workbooks, including their preamble rows and `Equity` sheet. It accepts aliases such as `Trading Symbol`, `Symbol`, `Exchange`, `Quantity`, `Quantity Available`, `Qty`, `Average Price`, `Average Cost`, and `Avg. Cost`. Zerodha equity statements without an exchange column are normalized to `NSE`. Unsupported or missing required columns are rejected. Duplicate exchange/symbol positions are rejected.

### 2. View the Dashboard

The Dashboard reads only the latest confirmed snapshot. It shows invested value, position count, snapshot date, and the normalized holdings table.

### 3. Load Charts

Open **Chart**, select a held symbol, choose a period and `Candle`, `Line`, or `Bar`, and press **Load history**. The page requests delayed OHLC history from Yahoo Finance through the `PriceProvider` abstraction. Plotly provides the chart rendering; TradingView is used as a visual reference only.

### 4. Rank Gainers and Losers

Open **Gainers / losers**, choose **Gainers** or **Losers**, and press **Refresh rankings**. The page loads the top 50 NIFTY 500 rows from Moneycontrol's public market-statistics table. Yahoo Finance remains available for held-symbol quotes and chart history; public market data is delayed, rate-limited, and may fail. The UI reports provider failures rather than inventing values.

### 5. Use the Assistant

Open **Chat assistant** and ask about holdings, cached prices, invested value, or P&L. The agent is instructed to call relational tools for exact numbers.

Use **Add a knowledge note** for tax rules, glossary entries, or personal research. Notes are embedded locally and stored in Chroma. Do not use notes as a substitute for official numeric portfolio data.

### 6. Research Stocks and IPOs

**Stock details** shows public quote, sector, industry, valuation fields, moving averages, and momentum when the provider supplies them. **Recommendations** applies a transparent trend screen to current holdings and includes sector context. **IPO scanner** loads public IPO rows and subscription or listing statistics. These screens are research aids, not buy advice; verify official filings and the prospectus before acting.

## Agent and Tool Design

The assistant uses a LangGraph ReAct graph with an OpenAI chat model and four tools:

- `get_holdings`: returns current symbols, exchanges, quantities, average costs, and cost values from SQLite.
- `get_price`: returns a cached delayed quote for a symbol.
- `get_pnl_summary`: calculates invested value, available cached market value, and the difference from relational data.
- `search_knowledge`: searches the Chroma knowledge collection for explanations and notes.

The system prompt establishes the critical boundary: the model must not invent or calculate authoritative portfolio figures from memory, and Chroma must not be used for exact holdings or P&L.

The current LLM is `gpt-4o-mini` because the application needs reliable tool calling at modest cost. The model is replaceable inside `core/agent/graph.py`; the deterministic tools remain independent of that choice.

## Data and Security

- `data/portfolio.db` contains holdings, snapshots, diffs, and cached prices.
- `data/chroma_db/` contains locally persisted embeddings and note text.
- API keys are entered into the Streamlit session and are not stored in the database.
- Do not commit `data/`, `.streamlit/secrets.toml`, `.env`, or API keys.
- This is a personal tool, not a trading or tax-advice system.
- Public market prices are delayed and should not be used for intraday execution decisions.
- Verify Zerodha parses against the original export before confirming replacement.

## Testing and Checks

```powershell
python -m pytest -q
python -m compileall -q app.py core pages tests
```

Tests currently cover valid Holdings parsing, missing required columns, duplicate positions, and deterministic quote-cache persistence. Market and LLM tests should remain mocked so test runs do not depend on Yahoo Finance, OpenAI, or LangSmith availability.

## Development Notes

- Add new price vendors behind `PriceProvider`; do not couple pages directly to a vendor.
- Keep exact numeric features in SQLite-backed tools.
- Keep explanatory documents in Chroma collections.
- Add tradebook and tax parsers using the same confirmation-gate pattern before exposing them to the agent.
- Add APScheduler only when implementing Phase 3 refresh and alert jobs.