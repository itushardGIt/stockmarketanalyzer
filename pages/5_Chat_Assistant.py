"""LangGraph portfolio chat interface."""

from pathlib import Path

import streamlit as st

from core.agent.graph import OPENAI_MODEL, ask_agent, build_agent, check_openai_connection, fallback_answer
from core.rag.store import add_knowledge_texts
from core.ui import market_progress

st.header("Chat assistant")
st.caption("One grounded assistant for holdings, stocks, markets, recommendations, IPOs, and knowledge notes.")

openai_api_key = st.session_state.get("openai_api_key", "")
langsmith_api_key = st.session_state.get("langsmith_api_key", "")
database_path = Path("data/portfolio.db")
chroma_path = Path("data/chroma_db")
langsmith_enabled = st.session_state.get("langsmith_enabled", False)
if openai_api_key:
    st.caption(f"Backend: LangGraph tool-calling agent + OpenAI {OPENAI_MODEL}.")
else:
    st.caption("Backend: deterministic portfolio and market-tool fallback. Add an OpenAI key to enable natural-language synthesis.")

if st.button("Test OpenAI connection", disabled=not openai_api_key):
    with market_progress(f"Testing {OPENAI_MODEL} access"):
        try:
            response = check_openai_connection(openai_api_key)
            st.success(response)
        except Exception as error:
            st.error(f"OpenAI connection failed: {error}")

with st.expander("Add a knowledge note"):
    note = st.text_area("Tax rule, glossary entry, or personal research note", height=120)
    if st.button("Index note", disabled=not note.strip()):
        add_knowledge_texts(chroma_path, [note.strip()])
        st.success("Note indexed in Chroma.")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

history_col, clear_col = st.columns([4, 1])
with history_col:
    with st.expander("Past 5 chat messages", expanded=False):
        recent_messages = st.session_state.chat_messages[-5:]
        if recent_messages:
            for message in recent_messages:
                label = "You" if message["role"] == "user" else "NiveshIQ"
                st.markdown(f"**{label}:** {message['content']}")
        else:
            st.caption("No chat history yet.")
with clear_col:
    if st.button("Clear chat", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()

for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about holdings, stocks, markets, recommendations, IPOs, or notes")
if question:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        progress_label = "Consulting NiveshIQ research assistant"
        with market_progress(progress_label):
            try:
                if openai_api_key:
                    agent = build_agent(
                        openai_api_key,
                        database_path,
                        chroma_path,
                        langsmith_api_key,
                        langsmith_enabled,
                    )
                    answer = ask_agent(agent, question)
                else:
                    answer = fallback_answer(question, database_path)
            except Exception as error:
                error_text = str(error)
                answer = fallback_answer(question, database_path)
                st.warning(f"LLM unavailable; returned a tool-grounded fallback. Details: {error_text}")
            st.markdown(answer)
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})