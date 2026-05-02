from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from api.whatsapp_state import WhatsAppSession, WhatsAppStateManager
from rag_pipeline.config import (
    CATEGORY_DISPLAY_MAP,
    CENTRAL_GOVT_LABEL,
    ENABLE_MULTILINGUAL,
    UI_CASTE_OPTIONS,
    UI_DISABILITY_OPTIONS,
    UI_GENDER_OPTIONS,
    UI_STATE_OPTIONS,
)
from rag_pipeline.inference.generator import (
    prepare_discovery_candidates,
    prepare_search_candidates,
)
from rag_pipeline.inference.retriever import KnowledgeBaseUnavailableError, SchemeResult
from rag_pipeline.inference.translator import (
    detect_and_translate_query,
    translate_response,
)

MENU = "menu"
AWAITING_SEARCH_QUERY = "awaiting_search_query"
AWAITING_GENDER = "awaiting_gender"
AWAITING_AGE = "awaiting_age"
AWAITING_STATE = "awaiting_state"
AWAITING_AREA = "awaiting_area"
AWAITING_CASTE = "awaiting_caste"
AWAITING_DISABILITY = "awaiting_disability"
AWAITING_PROFESSION = "awaiting_profession"

AREA_OPTIONS = ["Urban", "Rural"]
PROFESSION_OPTIONS = [
    "Student",
    "Farmer",
    "Entrepreneur / Self-Employed",
    "Corporate Employee",
    "Government Employee",
    "Unemployed",
    "Other",
]

COMMAND_KEYWORDS = {"menu", "reset", "restart", "start", "help"}
GREETING_KEYWORDS = {
    "hi",
    "hello",
    "hey",
    "namaste",
    "namaskar",
    "good morning",
    "good afternoon",
    "good evening",
}


class WhatsAppBotController:
    """Conversation controller for the Twilio WhatsApp bot."""

    def __init__(self, state_manager: Optional[WhatsAppStateManager] = None) -> None:
        self.state_manager = state_manager or WhatsAppStateManager()

    def handle_message(self, user_id: str, inbound_text: str) -> str:
        session = self.state_manager.get_session(user_id)
        raw_text = (inbound_text or "").strip()
        if not raw_text:
            return self._reply(session, self._menu_prompt())

        english_text, detected_lang = self._translate_inbound(raw_text)
        if detected_lang:
            session.language_code = detected_lang

        normalized = self._normalize_text(english_text)
        if normalized in COMMAND_KEYWORDS or normalized in GREETING_KEYWORDS:
            session.reset()
            return self._reply(session, self._menu_prompt())

        if session.state == MENU:
            return self._handle_menu_choice(session, normalized)
        if session.state == AWAITING_SEARCH_QUERY:
            return self._handle_search_query(session, english_text)
        if session.state == AWAITING_GENDER:
            return self._handle_gender(session, normalized)
        if session.state == AWAITING_AGE:
            return self._handle_age(session, normalized)
        if session.state == AWAITING_STATE:
            return self._handle_state(session, english_text)
        if session.state == AWAITING_AREA:
            return self._handle_area(session, normalized)
        if session.state == AWAITING_CASTE:
            return self._handle_caste(session, normalized)
        if session.state == AWAITING_DISABILITY:
            return self._handle_disability(session, normalized)
        if session.state == AWAITING_PROFESSION:
            return self._handle_profession(session, normalized)

        session.reset()
        return self._reply(session, self._menu_prompt())

    def _handle_menu_choice(self, session: WhatsAppSession, normalized_text: str) -> str:
        if normalized_text == "1" or "search" in normalized_text:
            session.state = AWAITING_SEARCH_QUERY
            session.profile.clear()
            return self._reply(
                session,
                (
                    "Search Schemes by Name selected.\n"
                    "Please send the scheme name or keywords.\n"
                    "Example: PM Kisan"
                ),
            )

        if (
            normalized_text == "2"
            or "find" in normalized_text
            or "eligibility" in normalized_text
            or "for you" in normalized_text
        ):
            session.state = AWAITING_GENDER
            session.profile.clear()
            return self._reply(session, self._prompt_for_gender())

        return self._reply(session, self._menu_prompt(prefix="Please reply with 1 or 2."))

    def _handle_search_query(self, session: WhatsAppSession, query_text: str) -> str:
        try:
            candidates = prepare_search_candidates(query_text)[:5]
        except KnowledgeBaseUnavailableError as exc:
            session.reset()
            return self._reply(session, str(exc))

        session.reset()
        if not candidates:
            return self._reply(
                session,
                (
                    "I could not find matching schemes.\n"
                    "Try another scheme name.\n\n"
                    + self._menu_prompt()
                ),
            )

        message = self._format_results(
            heading="Top 5 schemes",
            schemes=candidates,
        )
        return self._reply(session, message + "\n\n" + self._menu_prompt())

    def _handle_gender(self, session: WhatsAppSession, normalized_text: str) -> str:
        choice = self._parse_choice(
            normalized_text,
            {
                "1": "Male",
                "male": "Male",
                "man": "Male",
                "2": "Female",
                "female": "Female",
                "woman": "Female",
                "3": "Transgender",
                "transgender": "Transgender",
                "trans": "Transgender",
            },
        )
        if not choice:
            return self._reply(session, self._prompt_for_gender(error=True))

        session.profile["gender"] = choice
        session.state = AWAITING_AGE
        return self._reply(session, "Please enter your age in years.\nExample: 24")

    def _handle_age(self, session: WhatsAppSession, normalized_text: str) -> str:
        match = re.search(r"\d{1,3}", normalized_text)
        if not match:
            return self._reply(session, "Please enter a valid age in numbers.\nExample: 24")

        age = int(match.group(0))
        if age < 0 or age > 120:
            return self._reply(session, "Please enter an age between 0 and 120.")

        session.profile["age"] = str(age)
        session.state = AWAITING_STATE
        return self._reply(
            session,
            "Please enter your State or UT name.\nExample: Gujarat",
        )

    def _handle_state(self, session: WhatsAppSession, text: str) -> str:
        state = self._match_option(text, UI_STATE_OPTIONS)
        if not state:
            return self._reply(
                session,
                "Please enter a valid Indian State or UT name.\nExample: Tamil Nadu",
            )

        session.profile["state"] = state
        session.state = AWAITING_AREA
        return self._reply(
            session,
            "Select your area:\n1. Urban\n2. Rural",
        )

    def _handle_area(self, session: WhatsAppSession, normalized_text: str) -> str:
        choice = self._parse_choice(
            normalized_text,
            {
                "1": "Urban",
                "urban": "Urban",
                "city": "Urban",
                "2": "Rural",
                "rural": "Rural",
                "village": "Rural",
            },
        )
        if not choice:
            return self._reply(session, "Please reply with 1 for Urban or 2 for Rural.")

        session.profile["area"] = choice
        session.state = AWAITING_CASTE
        return self._reply(session, self._numbered_prompt("Select your caste category:", UI_CASTE_OPTIONS))

    def _handle_caste(self, session: WhatsAppSession, normalized_text: str) -> str:
        mapping = {str(index + 1): option for index, option in enumerate(UI_CASTE_OPTIONS)}
        mapping.update({self._normalize_text(option): option for option in UI_CASTE_OPTIONS})
        choice = self._parse_choice(normalized_text, mapping)
        if not choice:
            return self._reply(session, self._numbered_prompt("Please select a valid caste category:", UI_CASTE_OPTIONS))

        session.profile["caste"] = choice
        session.state = AWAITING_DISABILITY
        return self._reply(session, self._numbered_prompt("Do you have a disability?", UI_DISABILITY_OPTIONS))

    def _handle_disability(self, session: WhatsAppSession, normalized_text: str) -> str:
        mapping = {
            "1": "No",
            "no": "No",
            "2": "Yes",
            "yes": "Yes",
        }
        choice = self._parse_choice(normalized_text, mapping)
        if not choice:
            return self._reply(session, self._numbered_prompt("Please reply with 1 for No or 2 for Yes.", UI_DISABILITY_OPTIONS))

        session.profile["disability"] = choice
        session.state = AWAITING_PROFESSION
        return self._reply(session, self._numbered_prompt("Select your profession:", PROFESSION_OPTIONS))

    def _handle_profession(self, session: WhatsAppSession, normalized_text: str) -> str:
        mapping = {str(index + 1): option for index, option in enumerate(PROFESSION_OPTIONS)}
        mapping.update({self._normalize_text(option): option for option in PROFESSION_OPTIONS})
        mapping["entrepreneur"] = "Entrepreneur / Self-Employed"
        mapping["self employed"] = "Entrepreneur / Self-Employed"
        choice = self._parse_choice(normalized_text, mapping)
        if not choice:
            return self._reply(session, self._numbered_prompt("Please select a valid profession:", PROFESSION_OPTIONS))

        session.profile["profession"] = choice

        try:
            candidates, _is_relaxed = prepare_discovery_candidates(dict(session.profile))
        except KnowledgeBaseUnavailableError as exc:
            session.reset()
            return self._reply(session, str(exc))

        session.reset()
        if not candidates:
            return self._reply(
                session,
                "I could not find matching schemes for this profile.\n\n" + self._menu_prompt(),
            )

        message = self._format_results(
            heading="Top 5 schemes for you",
            schemes=candidates[:5],
        )
        return self._reply(session, message + "\n\n" + self._menu_prompt())

    def _format_results(self, heading: str, schemes: List[SchemeResult]) -> str:
        blocks = [heading]
        for index, scheme in enumerate(schemes[:5], start=1):
            state = (
                "Central"
                if scheme.location_name == CENTRAL_GOVT_LABEL
                else (scheme.location_name or "N/A")
            )
            category = CATEGORY_DISPLAY_MAP.get(
                scheme.category_name,
                (scheme.category_name or "N/A").replace("_", " ").title(),
            )
            blocks.append(
                "\n".join(
                    [
                        f"{index}. {scheme.scheme_name}",
                        f"URL: {scheme.scheme_url or 'N/A'}",
                        f"State: {state}",
                        f"Category: {category}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    def _menu_prompt(self, prefix: str = "") -> str:
        base = (
            "Welcome to GScheme WhatsApp Bot.\n"
            "Reply with:\n"
            "1. Search Schemes by Name\n"
            "2. Find Schemes for You\n\n"
            "You can also send menu or reset anytime."
        )
        return f"{prefix}\n\n{base}" if prefix else base

    def _prompt_for_gender(self, error: bool = False) -> str:
        prefix = "Please select a valid option.\n\n" if error else ""
        return prefix + self._numbered_prompt("Select your gender:", UI_GENDER_OPTIONS)

    def _numbered_prompt(self, title: str, options: List[str]) -> str:
        lines = [title]
        for index, option in enumerate(options, start=1):
            lines.append(f"{index}. {option}")
        return "\n".join(lines)

    def _translate_inbound(self, raw_text: str) -> tuple[str, str]:
        if not ENABLE_MULTILINGUAL:
            return raw_text, "en-IN"
        return detect_and_translate_query(raw_text)

    def _reply(self, session: WhatsAppSession, english_text: str) -> str:
        if not ENABLE_MULTILINGUAL or session.language_code == "en-IN":
            return english_text
        return translate_response(english_text, session.language_code)

    def _parse_choice(self, normalized_text: str, mapping: Dict[str, str]) -> Optional[str]:
        if normalized_text in mapping:
            return mapping[normalized_text]
        return mapping.get(normalized_text.replace("/", " ").strip())

    def _match_option(self, text: str, options: List[str]) -> Optional[str]:
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return None

        for option in options:
            if self._normalize_text(option) == normalized_text:
                return option

        for option in options:
            option_key = self._normalize_text(option)
            if normalized_text in option_key or option_key in normalized_text:
                return option

        best_option: Optional[str] = None
        best_score = 0.0
        for option in options:
            score = SequenceMatcher(
                None,
                normalized_text,
                self._normalize_text(option),
            ).ratio()
            if score > best_score:
                best_score = score
                best_option = option

        if best_option and best_score >= 0.78:
            return best_option
        return None

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[^a-z0-9\s]+", " ", (text or "").strip().lower()).strip()
