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

from rag_pipeline.config import (
    DISCOVERY_TOP_K,
    ENABLE_MULTILINGUAL,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    MAX_CHAT_HISTORY_TURNS,
    USE_RERANKER,
)
from rag_pipeline.inference.prompts import build_few_shot_messages, build_system_prompt
from rag_pipeline.inference.reranker import get_reranker
from rag_pipeline.inference.retriever import (
    SchemeResult,
    build_scheme_context,
    build_search_query,
    discover_schemes,
    fetch_scheme_chunks,
    search_schemes_by_name,
)
from rag_pipeline.inference.translator import detect_and_translate_query, translate_response

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


def _translate_history_to_english(
    history: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Translate prior chat turns into English for multilingual conversations."""
    translated_history: List[Dict[str, str]] = []
    for msg in history:
        content = msg.get("content", "")
        if not content.strip():
            translated_history.append(msg)
            continue

        english_content, _ = detect_and_translate_query(content)
        translated_history.append(
            {
                "role": msg.get("role", "user"),
                "content": english_content,
            }
        )

    return translated_history


def _prepare_multilingual_turn(
    user_message: str,
    history: List[Dict[str, str]],
) -> tuple[str, List[Dict[str, str]], str]:
    """Translate the current turn to English when multilingual support is enabled."""
    if not ENABLE_MULTILINGUAL:
        return user_message, history, "en-IN"

    english_message, detected_lang = detect_and_translate_query(user_message)
    english_history = _translate_history_to_english(history)
    return english_message, english_history, detected_lang


def _yield_text_chunks(text: str, chunk_size: int = 220) -> Generator[str, None, None]:
    """Yield plain text in frontend-friendly chunks."""
    for idx in range(0, len(text), chunk_size):
        yield text[idx : idx + chunk_size]


def _stream_response_with_translation(llm, msgs, target_lang: str):
    """
    Stream English directly, or buffer then translate back to the user's language.
    """
    if target_lang == "en-IN":
        yield from llm.stream(msgs)
        return

    english_parts: List[str] = []
    for chunk in llm.stream(msgs):
        if hasattr(chunk, "content"):
            english_parts.append(chunk.content)
        else:
            english_parts.append(str(chunk))

    translated_text = translate_response("".join(english_parts), target_lang)
    yield from _yield_text_chunks(translated_text)


# ── Discovery pipeline ──────────────────────────────────────────────


def prepare_discovery_candidates(
    profile: Dict[str, Any],
) -> tuple[List[SchemeResult], bool]:
    """Retrieve and rank all candidates for discovery, without generating a response."""
    candidates, is_relaxed = discover_schemes(profile)
    if not candidates:
        return [], True

    if USE_RERANKER:
        # Retrieve many, rank them all based on the reranker length
        query_text = build_search_query(profile)
        reranker = get_reranker()
        passages = [s.combined_text[:2000] for s in candidates]
        ranked = reranker.rerank(query_text, passages, top_k=len(candidates))
        top_schemes = [candidates[idx] for idx, _score in ranked]

        # Update scores from reranker
        for scheme, (_, rerank_score) in zip(top_schemes, ranked):
            scheme.score = rerank_score
    else:
        top_schemes = candidates

    return top_schemes, is_relaxed


def prepare_search_candidates(
    query_text: str,
) -> List[SchemeResult]:
    """Retrieve and rank direct search candidates using scheme titles only."""
    candidates = search_schemes_by_name(query_text)
    if not candidates:
        return []

    if USE_RERANKER:
        reranker = get_reranker()
        passages = [s.scheme_name for s in candidates]
        ranked = reranker.rerank(query_text, passages, top_k=len(candidates))
        top_schemes = [candidates[idx] for idx, _score in ranked]

        # Update scores from reranker
        for scheme, (_, rerank_score) in zip(top_schemes, ranked):
            scheme.score = rerank_score
    else:
        top_schemes = candidates

    return top_schemes


def run_discovery_page_stream(
    profile: Dict[str, Any],
    top_schemes: List[SchemeResult],
    is_relaxed: bool,
    start_idx: int = 0
) -> Generator:
    """Takes a specific page slice of schemes and streams the discovery LLM output."""
    if not top_schemes:
        return iter([])

    context_parts = []
    # Start idx is used just for display numbering (1-indexed)
    for i, s in enumerate(top_schemes, start_idx + 1):
        full_chunks = fetch_scheme_chunks(s.scheme_id)
        full_context = build_scheme_context(full_chunks, is_discovery=True)
        context_parts.append(f"--- Scheme {i} ---\n{full_context}\n")
    context = "\n".join(context_parts)

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    if is_relaxed:
        user_msg = (
            f"No schemes matched my exact profile. Show me ALL {len(top_schemes)} of the closest "
            f"matching schemes from the context and explain how they partially match. Do not skip any scheme, you must output exactly {len(top_schemes)} schemes."
        )
    else:
        user_msg = (
            f"Based on my profile, show me ALL {len(top_schemes)} government schemes "
            f"I may be eligible for from the context provided. Do not skip any scheme, you must output exactly {len(top_schemes)} schemes."
        )

    llm = _get_llm(streaming=True)
    msgs = _build_messages(system_prompt, few_shot, [], user_msg, context)
    return llm.stream(msgs)


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
    english_message, english_history, detected_lang = _prepare_multilingual_turn(
        user_message, history
    )

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=False)
    msgs = _build_messages(
        system_prompt,
        few_shot,
        english_history,
        english_message,
        context,
    )
    response = llm.invoke(msgs)
    response_text = response.content
    if detected_lang != "en-IN":
        return translate_response(response_text, detected_lang)
    return response_text


def chat_response_stream(
    user_message: str,
    profile: Dict[str, Any],
    scheme_id: str,
    history: List[Dict[str, str]],
):
    """Streaming version of chat_response."""
    chunks = fetch_scheme_chunks(scheme_id)
    context = build_scheme_context(chunks)
    english_message, english_history, detected_lang = _prepare_multilingual_turn(
        user_message, history
    )

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=True)
    msgs = _build_messages(
        system_prompt,
        few_shot,
        english_history,
        english_message,
        context,
    )
    return _stream_response_with_translation(llm, msgs, detected_lang)


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
    english_message, english_history, detected_lang = _prepare_multilingual_turn(
        user_message, history
    )

    system_prompt = build_system_prompt(profile)
    few_shot = build_few_shot_messages(profile)

    llm = _get_llm(streaming=True)
    msgs = _build_messages(
        system_prompt,
        few_shot,
        english_history,
        english_message,
        context,
    )
    return _stream_response_with_translation(llm, msgs, detected_lang)
