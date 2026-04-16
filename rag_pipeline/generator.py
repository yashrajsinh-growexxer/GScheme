"""
Generator module — LangChain chain with Groq LLM.

Provides:
  - generate_discovery_response: format top schemes for the user
  - generate_chat_response: answer follow-up questions with scheme context
"""
from __future__ import annotations

import os
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv

try:
    from .config import (
        DISCOVERY_TOP_K,
        GROQ_MAX_TOKENS,
        GROQ_MODEL,
        GROQ_TEMPERATURE,
        MAX_CHAT_HISTORY_TURNS,
        USE_RERANKER,
    )
    from .prompts import build_few_shot_messages, build_system_prompt
    from .reranker import get_reranker
    from .retriever import (
        SchemeResult,
        build_scheme_context,
        build_search_query,
        discover_schemes,
        fetch_scheme_chunks,
    )
except ImportError:
    from config import (
        DISCOVERY_TOP_K,
        GROQ_MAX_TOKENS,
        GROQ_MODEL,
        GROQ_TEMPERATURE,
        MAX_CHAT_HISTORY_TURNS,
        USE_RERANKER,
    )
    from prompts import build_few_shot_messages, build_system_prompt
    from reranker import get_reranker
    from retriever import (
        SchemeResult,
        build_scheme_context,
        build_search_query,
        discover_schemes,
        fetch_scheme_chunks,
    )

load_dotenv()


# ── LLM helper ───────────────────────────────────────────────────────


def _get_llm(streaming: bool = False):
    """Return a ChatGroq LLM instance."""
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise ImportError(
            "langchain-groq not installed. Install with: pip install langchain-groq"
        ) from exc

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to your .env file."
        )

    return ChatGroq(
        model=GROQ_MODEL,
        api_key=api_key,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
        streaming=streaming,
    )


def _build_messages(
    system_prompt: str,
    few_shot: List[Dict[str, str]],
    history: List[Dict[str, str]],
    user_message: str,
    context: str = "",
) -> list:
    """Assemble the full message list for the LLM."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    msgs: list = [SystemMessage(content=system_prompt)]

    # Few-shot
    for m in few_shot:
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["content"]))
        else:
            msgs.append(AIMessage(content=m["content"]))

    # Conversation history (trimmed)
    trimmed = history[-(MAX_CHAT_HISTORY_TURNS * 2):]
    for m in trimmed:
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["content"]))
        else:
            msgs.append(AIMessage(content=m["content"]))

    # Current user message (with optional context)
    if context:
        content = (
            f"CONTEXT (retrieved from knowledge base):\n"
            f"---\n{context}\n---\n\n"
            f"USER QUESTION: {user_message}"
        )
    else:
        content = user_message
    msgs.append(HumanMessage(content=content))

    return msgs


# ── Discovery pipeline ──────────────────────────────────────────────


def run_discovery(
    profile: Dict[str, Any],
) -> tuple[List[SchemeResult], str, bool]:
    """
    End-to-end discovery: retrieve → rerank → generate summary.

    Returns:
        (top_schemes, llm_response_text, is_relaxed)
    """
    # 1. Retrieve candidate schemes
    candidates, is_relaxed = discover_schemes(profile)
    if not candidates:
        return [], "", True

    if USE_RERANKER:
        # 2. Rerank
        query_text = build_search_query(profile)
        reranker = get_reranker()
        passages = [s.combined_text[:2000] for s in candidates]
        ranked = reranker.rerank(query_text, passages, top_k=DISCOVERY_TOP_K)
        top_schemes = [candidates[idx] for idx, _score in ranked]

        # Update scores from reranker
        for scheme, (_, rerank_score) in zip(top_schemes, ranked):
            scheme.score = rerank_score
    else:
        top_schemes = candidates[:DISCOVERY_TOP_K]

    # 3. Build context for LLM
    context_parts = []
    for i, s in enumerate(top_schemes, 1):
        full_chunks = fetch_scheme_chunks(s.scheme_id)
        full_context = build_scheme_context(full_chunks, is_discovery=True)
        context_parts.append(f"--- Scheme {i} ---\n{full_context}\n")
    context = "\n".join(context_parts)

    # 4. Generate LLM response
    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    if is_relaxed:
        user_msg = (
            "No schemes matched my exact profile. Show me the closest "
            "matching schemes from the context and explain how they partially match."
        )
    else:
        user_msg = (
            "Based on my profile, show me the best government schemes "
            "I may be eligible for from the context provided."
        )

    llm = _get_llm(streaming=False)
    msgs = _build_messages(system_prompt, few_shot, [], user_msg, context)
    response = llm.invoke(msgs)
    return top_schemes, response.content, is_relaxed


def run_discovery_stream(
    profile: Dict[str, Any],
) -> tuple[List[SchemeResult], Generator, bool]:
    """Same as run_discovery but returns a streaming generator for the LLM output."""
    candidates, is_relaxed = discover_schemes(profile)
    if not candidates:
        return [], iter([]), True

    if USE_RERANKER:
        query_text = build_search_query(profile)
        reranker = get_reranker()
        passages = [s.combined_text[:2000] for s in candidates]
        ranked = reranker.rerank(query_text, passages, top_k=DISCOVERY_TOP_K)
        top_schemes = [candidates[idx] for idx, _score in ranked]

        for scheme, (_, rerank_score) in zip(top_schemes, ranked):
            scheme.score = rerank_score
    else:
        top_schemes = candidates[:DISCOVERY_TOP_K]

    context_parts = []
    for i, s in enumerate(top_schemes, 1):
        full_chunks = fetch_scheme_chunks(s.scheme_id)
        full_context = build_scheme_context(full_chunks, is_discovery=True)
        context_parts.append(f"--- Scheme {i} ---\n{full_context}\n")
    context = "\n".join(context_parts)

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    if is_relaxed:
        user_msg = (
            "No schemes matched my exact profile. Show me the closest "
            "matching schemes from the context and explain how they partially match."
        )
    else:
        user_msg = (
            "Based on my profile, show me the best government schemes "
            "I may be eligible for from the context provided."
        )

    llm = _get_llm(streaming=True)
    msgs = _build_messages(system_prompt, few_shot, [], user_msg, context)
    stream = llm.stream(msgs)
    return top_schemes, stream, is_relaxed


# ── Chat / deep-dive ────────────────────────────────────────────────


def chat_response(
    user_message: str,
    profile: Dict[str, Any],
    scheme_id: str,
    history: List[Dict[str, str]],
) -> str:
    """Answer a follow-up question about a specific scheme (non-streaming)."""
    chunks = fetch_scheme_chunks(scheme_id)
    context = build_scheme_context(chunks)

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=False)
    msgs = _build_messages(system_prompt, few_shot, history, user_message, context)
    response = llm.invoke(msgs)
    return response.content


def chat_response_stream(
    user_message: str,
    profile: Dict[str, Any],
    scheme_id: str,
    history: List[Dict[str, str]],
):
    """Streaming version of chat_response."""
    chunks = fetch_scheme_chunks(scheme_id)
    context = build_scheme_context(chunks)

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=True)
    msgs = _build_messages(system_prompt, few_shot, history, user_message, context)
    return llm.stream(msgs)


# ── General chat (no specific scheme) ────────────────────────────────


def general_chat_stream(
    user_message: str,
    profile: Dict[str, Any],
    schemes: List[SchemeResult],
    history: List[Dict[str, str]],
):
    """Chat about the discovered schemes generally (no single scheme selected)."""
    context_parts = []
    for i, s in enumerate(schemes, 1):
        full_chunks = fetch_scheme_chunks(s.scheme_id)
        full_context = build_scheme_context(full_chunks, is_discovery=True)
        context_parts.append(f"--- Scheme {i} ---\n{full_context}\n")
    context = "\n".join(context_parts)

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=True)
    msgs = _build_messages(system_prompt, few_shot, history, user_message, context)
    return llm.stream(msgs)
