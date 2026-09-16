"""LangGraph runtime for the portfolio assistant."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

OPENAI_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    "You are NiveshIQ, an Indian stock-market research assistant. Route every question to the appropriate approved tool. "
    "Use SQLite tools for exact uploaded holdings, invested value, P&L, and cached prices. "
    "Use stock tools for live delayed stock details and trend screens. Use IPO and index tools for public market research. "
    "Use knowledge search only for concepts and indexed notes. Never invent numbers, dates, prices, IPO facts, or buy advice. "
    "Explain the tool results clearly, include data limitations and timestamps when available, and call a tool before answering factual market questions."
)


def build_agent(
    openai_api_key: str,
    database_path: Path,
    chroma_path: Path,
    langsmith_api_key: str = "",
    langsmith_enabled: bool = False,
) -> Any:
    """Build a tool-calling LangGraph agent for one application session."""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    from core.agent.tools import make_tools
    from core.rag.store import search_knowledge_base

    @tool
    def search_knowledge(query: str) -> list[str]:
        """Search tax rules, glossary, and user notes; do not use for portfolio numbers."""
        return search_knowledge_base(query, chroma_path)

    if langsmith_enabled and langsmith_api_key.strip():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
        os.environ.setdefault("LANGCHAIN_PROJECT", "portfolio-assistant")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
    model = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=openai_api_key,
        temperature=0,
        timeout=30,
        max_retries=2,
    )
    tools = [*make_tools(database_path), search_knowledge]
    return create_react_agent(
        model,
        tools,
        prompt=SYSTEM_PROMPT,
    )


def ask_agent(agent: Any, question: str) -> str:
    """Run the graph for one user question and return the final text response."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    message = result["messages"][-1]
    return str(message.content)


def fallback_answer(question: str, database_path: Path) -> str:
    """Answer common questions from approved tools when the LLM is unavailable."""
    from core.agent.tools import get_current_holdings

    holdings = get_current_holdings(database_path)
    lowered = question.lower()
    if "ipo" in lowered:
        from core.market_data.ipo import load_ipo_snapshot

        try:
            table = load_ipo_snapshot().head(5)
            rows = "\n".join(f"- {row['Company']}: {row['Issue price']} | subscription {row['Subscription']}" for _, row in table.iterrows())
            return "Top public IPO research rows:\n\n" + rows + "\n\nThis is public research data, not a buy recommendation."
        except Exception as error:
            return f"IPO data is currently unavailable: {error}"
    if any(term in lowered for term in ("nifty", "index", "gainer", "recommendation")):
        from core.market_data.universe import MONEYCONTROL_INDEXES, load_index_recommendations

        index_name = next((name for name in MONEYCONTROL_INDEXES if name.lower() in lowered), "NIFTY 50")
        try:
            table, _ = load_index_recommendations(index_name)
            rows = "\n".join(f"- {row['Stock']}: {row['Price']} ({row['Change %']:+.2f}%)" for _, row in table.head(5).iterrows())
            return f"Top {index_name} momentum research rows:\n\n{rows}\n\nThis is a momentum screen, not personalized investment advice."
        except Exception as error:
            return f"Index data is currently unavailable: {error}"
    if not holdings:
        return "No confirmed holdings are available yet. Upload and confirm a holdings statement first."
    if any(term in lowered for term in ("how many", "count", "number of", "positions")):
        return f"Your current uploaded portfolio contains {len(holdings)} positions."
    if any(term in lowered for term in ("invested", "cost value", "total cost")):
        invested = sum(float(item["cost_value"]) for item in holdings)
        return f"The total invested value in the current uploaded portfolio is ₹{invested:,.2f}."
    matches = [item for item in holdings if str(item["symbol"]).lower() in lowered]
    rows = matches or holdings
    response = "Here are the current uploaded holdings:\n\n" + "\n".join(
        f"- {item['symbol']} ({item['exchange']}): {item['quantity']:g} shares at ₹{item['average_cost']:,.2f} average cost"
        for item in rows
    )
    return response + "\n\nLLM access is unavailable, so this is a tool-only response."


def check_openai_connection(openai_api_key: str) -> str:
    """Make a minimal model request for the UI connection test."""
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=OPENAI_MODEL, api_key=openai_api_key, temperature=0, timeout=15, max_retries=0)
    response = model.invoke("Reply with exactly: NiveshIQ connection OK")
    return str(response.content)