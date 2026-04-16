"""
Streamlit application — GovScheme Assistant.

Step-by-step user intake → scheme discovery → chatbot deep-dive.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure rag_pipeline is importable when running from project root
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from rag_pipeline.config import (
    UI_AREA_OPTIONS,
    UI_CASTE_OPTIONS,
    UI_DISABILITY_OPTIONS,
    UI_GENDER_OPTIONS,
    UI_PROFESSION_OPTIONS,
    UI_STATE_OPTIONS,
)

# ── Page config ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="GovScheme Assistant",
    page_icon="🏛️",
    layout="centered",
)

# ── Custom CSS ───────────────────────────────────────────────────────

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Header */
.header-box {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%);
    padding: 1.8rem 2rem;
    border-radius: 1rem;
    margin-bottom: 1.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(79, 70, 229, 0.25);
}
.header-box h1 {
    color: #fff;
    margin: 0;
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}
.header-box p {
    color: rgba(255,255,255,0.85);
    margin: 0.3rem 0 0 0;
    font-size: 0.95rem;
}

/* Scheme card */
.scheme-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 0.75rem;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
    transition: border-color 0.2s;
}
.scheme-card:hover {
    border-color: rgba(168, 85, 247, 0.4);
}
.scheme-card h4 {
    margin: 0 0 0.4rem 0;
    color: #c084fc;
    font-size: 1.05rem;
}
.scheme-card p {
    margin: 0.15rem 0;
    font-size: 0.88rem;
    color: rgba(255,255,255,0.7);
}

/* Profile pill */
.profile-pill {
    display: inline-block;
    background: rgba(168,85,247,0.12);
    color: #c084fc;
    padding: 0.2rem 0.65rem;
    border-radius: 1rem;
    font-size: 0.78rem;
    margin: 0.15rem 0.2rem;
    border: 1px solid rgba(168,85,247,0.2);
}

/* Divider */
.soft-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 1rem 0;
}

/* Intake step animations */
.step-question {
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state init ───────────────────────────────────────────────

INTAKE_STEPS = [
    {
        "key": "gender",
        "question": "What is your **gender**?",
        "widget": "radio",
        "options": UI_GENDER_OPTIONS,
    },
    {
        "key": "age",
        "question": "How **old** are you?",
        "widget": "selectbox",
        "options": list(range(1, 101)),
    },
    {
        "key": "state",
        "question": "Which **State / Union Territory** do you belong to?",
        "widget": "selectbox",
        "options": UI_STATE_OPTIONS,
    },
    {
        "key": "area",
        "question": "Do you live in an **urban** or **rural** area?",
        "widget": "radio",
        "options": UI_AREA_OPTIONS,
    },
    {
        "key": "caste",
        "question": "What is your **caste category**?",
        "widget": "selectbox",
        "options": UI_CASTE_OPTIONS,
    },
    {
        "key": "disability",
        "question": "Do you have any **disability**?",
        "widget": "radio",
        "options": UI_DISABILITY_OPTIONS,
    },
    {
        "key": "profession",
        "question": "What is your **profession**?",
        "widget": "selectbox",
        "options": UI_PROFESSION_OPTIONS,
    },
]

if "step" not in st.session_state:
    st.session_state.step = 0
    st.session_state.profile = {}
    st.session_state.messages = []        # chat display messages
    st.session_state.chat_history = []    # LLM history (role, content)
    st.session_state.schemes = []         # SchemeResult list
    st.session_state.active_scheme = None # scheme_id for deep-dive
    st.session_state.discovery_done = False
    st.session_state.is_relaxed = False

# ── Header ───────────────────────────────────────────────────────────

st.markdown(
    '<div class="header-box">'
    "<h1>🏛️ GovScheme Assistant</h1>"
    "<p>Find government schemes you're eligible for</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Sidebar: profile summary ────────────────────────────────────────


def _render_sidebar():
    profile = st.session_state.profile
    if not profile:
        return
    with st.sidebar:
        st.markdown("### 📋 Your Profile")
        for k, v in profile.items():
            st.markdown(
                f'<span class="profile-pill"><b>{k.title()}</b>: {v}</span>',
                unsafe_allow_html=True,
            )
        st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
        if st.button("🔄 Start Over", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


_render_sidebar()

# ── Intake phase ─────────────────────────────────────────────────────


def _run_intake():
    """Render step-by-step user intake."""
    step_idx = st.session_state.step

    # Show completed answers
    for i in range(step_idx):
        s = INTAKE_STEPS[i]
        with st.chat_message("assistant"):
            st.markdown(s["question"])
        with st.chat_message("user"):
            st.markdown(f"**{st.session_state.profile[s['key']]}**")

    # Current step
    if step_idx < len(INTAKE_STEPS):
        s = INTAKE_STEPS[step_idx]
        with st.chat_message("assistant"):
            st.markdown(
                f'<div class="step-question">{s["question"]}</div>',
                unsafe_allow_html=True,
            )

        with st.form(key=f"intake_step_{step_idx}"):
            if s["widget"] == "radio":
                value = st.radio(
                    s["key"].title(),
                    s["options"],
                    horizontal=True,
                    label_visibility="collapsed",
                )
            elif s["widget"] == "selectbox":
                value = st.selectbox(
                    s["key"].title(),
                    s["options"],
                    label_visibility="collapsed",
                )
            else:
                value = st.text_input(s["key"].title(), label_visibility="collapsed")

            submitted = st.form_submit_button("Next →", use_container_width=True)
            if submitted:
                st.session_state.profile[s["key"]] = value
                st.session_state.step = step_idx + 1
                st.rerun()
    else:
        # All info collected → trigger discovery
        if not st.session_state.discovery_done:
            _run_discovery()


# ── Discovery phase ──────────────────────────────────────────────────


def _run_discovery():
    """Run the retrieval + reranking pipeline and show results."""
    from rag_pipeline.inference.generator import prepare_discovery_candidates, run_discovery_page_stream

    profile = st.session_state.profile

    # Show completed profile summary
    for i, s in enumerate(INTAKE_STEPS):
        with st.chat_message("assistant"):
            st.markdown(s["question"])
        with st.chat_message("user"):
            st.markdown(f"**{profile[s['key']]}**")

    with st.chat_message("assistant"):
        st.markdown("🔍 **Searching for schemes matching your profile…**")
        with st.spinner("Retrieving and ranking schemes…"):
            try:
                if "all_discovered_schemes" not in st.session_state:
                    top_schemes, is_relaxed = prepare_discovery_candidates(profile)
                    st.session_state.all_discovered_schemes = top_schemes
                    st.session_state.discovery_page = 0
                    st.session_state.is_relaxed = is_relaxed
                else:
                    top_schemes = st.session_state.all_discovered_schemes
                    is_relaxed = st.session_state.is_relaxed

                if not top_schemes:
                    st.warning(
                        "No schemes found matching your profile. "
                        "Try adjusting your details or check back later."
                    )
                    st.session_state.discovery_done = True
                    return

                page = st.session_state.discovery_page
                start = page * 5
                top_schemes_page = top_schemes[start : start + 5]

                stream = run_discovery_page_stream(
                    profile, top_schemes_page, is_relaxed, start_idx=start
                )
            except Exception as exc:
                st.error(f"Error during discovery: {exc}")
                return

        st.session_state.schemes = top_schemes_page
        
        if is_relaxed:
            st.info(
                "ℹ️ No exact matches found. Showing closest matching schemes "
                "with relaxed filters."
            )

        # Stream the LLM response
        response_text = st.write_stream(stream)

    # Store in state
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )
    st.session_state.discovery_done = True
    st.rerun()


# ── Chat phase ───────────────────────────────────────────────────────


def _run_chat():
    """Render the chatbot for follow-up questions."""
    from rag_pipeline.inference.generator import chat_response_stream, general_chat_stream

    profile = st.session_state.profile
    schemes = st.session_state.schemes

    # Show scheme selection in sidebar
    if schemes:
        with st.sidebar:
            st.markdown("### 📑 Discovered Schemes")
            scheme_names = [s.scheme_name for s in schemes]
            for i, name in enumerate(scheme_names):
                truncated = name[:55] + "…" if len(name) > 55 else name
                if st.button(
                    f"{i+1}. {truncated}",
                    key=f"scheme_btn_{i}",
                    use_container_width=True,
                ):
                    st.session_state.active_scheme = schemes[i].scheme_id
                    st.session_state.trigger_query = f"Please provide full detailed information about {name}."
                    # Clear history so we don't carry the massive text of Scheme A into Scheme B
                    st.session_state.chat_history = []
                    st.rerun()

            st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
            active = st.session_state.active_scheme
            if active:
                active_name = next(
                    (s.scheme_name for s in schemes if s.scheme_id == active),
                    None,
                )
                if active_name:
                    st.markdown(f"**🔎 Deep-diving:** {active_name[:60]}")
                if st.button("↩ Back to all schemes", use_container_width=True):
                    st.session_state.active_scheme = None
                    st.rerun()
            else:
                total_loaded = len(st.session_state.schemes)
                total_available = len(st.session_state.get("all_discovered_schemes", []))
                if total_loaded < total_available:
                    if st.button("🔄 Load More Schemes", use_container_width=True):
                        st.session_state.trigger_load_more = True
                        st.rerun()

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask about a scheme…")
    
    # Handle auto-triggered load more
    trigger_load_more = st.session_state.pop("trigger_load_more", None)
    if trigger_load_more:
        from rag_pipeline.inference.generator import run_discovery_page_stream
        page = st.session_state.discovery_page + 1
        start = page * 5
        next_schemes = st.session_state.all_discovered_schemes[start : start + 5]
        
        if next_schemes:
            st.session_state.discovery_page = page
            st.session_state.schemes.extend(next_schemes)
            
            with st.chat_message("assistant"):
                st.markdown("🔄 **Loading more schemes…**")
                stream = run_discovery_page_stream(
                    profile, next_schemes, st.session_state.is_relaxed, start_idx=start
                )
                response_text = st.write_stream(stream)
            
            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )
            st.rerun()
        else:
            st.warning("No more schemes available.")

    # Handle auto-triggered query from buttons
    trigger_query = st.session_state.pop("trigger_query", None)
    if trigger_query:
        user_input = trigger_query

    if user_input:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Detect if user is referring to a scheme by number
        _detect_scheme_reference(user_input, schemes)

        # Generate response
        with st.chat_message("assistant"):
            active = st.session_state.active_scheme
            if active:
                stream = chat_response_stream(
                    user_message=user_input,
                    profile=profile,
                    scheme_id=active,
                    history=st.session_state.chat_history,
                )
            else:
                stream = general_chat_stream(
                    user_message=user_input,
                    profile=profile,
                    schemes=schemes,
                    history=st.session_state.chat_history,
                )

            response_text = st.write_stream(stream)

        # Update history
        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )
        st.session_state.chat_history.append(
            {"role": "assistant", "content": response_text}
        )


def _detect_scheme_reference(user_input: str, schemes):
    """Auto-set active_scheme if user references a scheme by number (e.g. 'scheme 2')."""
    if not schemes:
        return
    text = user_input.lower()
    for i in range(len(schemes)):
        markers = [
            f"scheme {i+1}",
            f"scheme no {i+1}",
            f"#{i+1}",
            f"number {i+1}",
            f"option {i+1}",
        ]
        if any(m in text for m in markers):
            st.session_state.active_scheme = schemes[i].scheme_id
            return

    # Check by name substring
    for s in schemes:
        if s.scheme_name.lower()[:30] in text:
            st.session_state.active_scheme = s.scheme_id
            return


# ── Main router ──────────────────────────────────────────────────────

if st.session_state.discovery_done:
    _run_chat()
else:
    _run_intake()
