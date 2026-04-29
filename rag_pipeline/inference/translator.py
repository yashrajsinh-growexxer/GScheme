"""
Multilingual translation layer using Sarvam Mayura.

Workflow:
  1. Detect the user's prompt language.
  2. Translate non-English prompts to English with Sarvam Mayura.
  3. Run the existing RAG pipeline in English.
  4. Translate the English answer back to the prompt language.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple

import httpx

from rag_pipeline.config import (
    SARVAM_TRANSLATION_CHUNK_CHARS,
    SARVAM_TRANSLATION_MODE,
    SARVAM_TRANSLATION_MODEL,
    SARVAM_TRANSLATION_TIMEOUT,
)

logger = logging.getLogger(__name__)

ENGLISH_CODE = "en-IN"
AUTO_CODE = "auto"

LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "or": "od-IN",
    "pa": "pa-IN",
    "ta": "ta-IN",
    "te": "te-IN",
}

MAYURA_SUPPORTED_LANGUAGES = set(LANG_MAP.values())

SCRIPT_RANGES = [
    ("hi-IN", r"[\u0900-\u097F]"),  # Devanagari; disambiguated below when possible.
    ("bn-IN", r"[\u0980-\u09FF]"),
    ("gu-IN", r"[\u0A80-\u0AFF]"),
    ("pa-IN", r"[\u0A00-\u0A7F]"),
    ("od-IN", r"[\u0B00-\u0B7F]"),
    ("ta-IN", r"[\u0B80-\u0BFF]"),
    ("te-IN", r"[\u0C00-\u0C7F]"),
    ("kn-IN", r"[\u0C80-\u0CFF]"),
    ("ml-IN", r"[\u0D00-\u0D7F]"),
]


class SarvamTranslator:
    """Small synchronous client for Sarvam Mayura translation."""

    _instance: Optional["SarvamTranslator"] = None

    def __init__(self):
        self.api_key = os.environ.get("SARVAM_API_KEY", "")
        self.endpoint = "https://api.sarvam.ai/translate"

    @classmethod
    def get_instance(cls) -> "SarvamTranslator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_english(self, text: str) -> bool:
        """Return True when text is primarily English/ASCII."""
        if not text or not text.strip():
            return True
        non_ascii = sum(1 for char in text if ord(char) > 127)
        return non_ascii / max(len(text.strip()), 1) < 0.15

    def detect_language(self, text: str) -> str:
        """Detect the prompt language and return a Sarvam BCP-47 code."""
        if not text or not text.strip() or self.is_english(text):
            return ENGLISH_CODE

        script_counts: dict[str, int] = {}
        for language_code, pattern in SCRIPT_RANGES:
            count = len(re.findall(pattern, text))
            if count:
                script_counts[language_code] = count

        if script_counts:
            detected = max(script_counts, key=lambda code: script_counts[code])
            if detected == "hi-IN":
                return self._disambiguate_devanagari(text)
            return detected

        try:
            from langdetect import detect

            detected = LANG_MAP.get(detect(text))
            if detected:
                return detected
        except Exception:
            logger.debug("langdetect could not classify the prompt", exc_info=True)

        return ENGLISH_CODE

    def _disambiguate_devanagari(self, text: str) -> str:
        """Distinguish Hindi and Marathi for Devanagari prompts when possible."""
        try:
            from langdetect import detect

            language = detect(text)
            if language == "mr":
                return "mr-IN"
        except Exception:
            logger.debug("Could not disambiguate Devanagari prompt", exc_info=True)
        return "hi-IN"

    def _split_text(self, text: str) -> list[str]:
        cleaned = text.strip()
        limit = max(100, SARVAM_TRANSLATION_CHUNK_CHARS)
        if len(cleaned) <= limit:
            return [cleaned]

        units = re.split(r"(\n\n+|(?<=[.!?।])\s+)", cleaned)
        chunks: list[str] = []
        current = ""

        for unit in units:
            if not unit:
                continue

            candidate = f"{current}{unit}" if current else unit
            if len(candidate) <= limit:
                current = candidate
                continue

            if current.strip():
                chunks.append(current.strip())
                current = ""

            if len(unit) <= limit:
                current = unit
                continue

            start = 0
            while start < len(unit):
                piece = unit[start : start + limit].strip()
                if piece:
                    chunks.append(piece)
                start += limit

        if current.strip():
            chunks.append(current.strip())

        return chunks or [cleaned[:limit]]

    def _translate_chunk(self, text: str, source_lang: str, target_lang: str) -> tuple[str, str]:
        if not self.api_key:
            logger.warning("SARVAM_API_KEY not configured; skipping translation")
            return text, source_lang

        payload = {
            "input": text,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": SARVAM_TRANSLATION_MODEL,
            "mode": SARVAM_TRANSLATION_MODE,
            "output_script": None,
            "numerals_format": "international",
        }

        try:
            with httpx.Client(timeout=SARVAM_TRANSLATION_TIMEOUT) as client:
                response = client.post(
                    self.endpoint,
                    headers={
                        "api-subscription-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or "Sarvam translation request failed"
            logger.warning("Sarvam translation failed: %s", detail)
            return text, source_lang
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Could not reach Sarvam translation service: %s", exc)
            return text, source_lang

        translated_text = data.get("translated_text") or text
        detected_source = data.get("source_language_code") or source_lang
        return translated_text, detected_source

    def translate(self, text: str, source_lang: str, target_lang: str) -> tuple[str, str]:
        if not text.strip() or source_lang == target_lang:
            return text, source_lang

        if target_lang not in MAYURA_SUPPORTED_LANGUAGES:
            logger.warning("Target language %s is not supported by Mayura", target_lang)
            return text, source_lang

        if source_lang != AUTO_CODE and source_lang not in MAYURA_SUPPORTED_LANGUAGES:
            logger.warning("Source language %s is not supported by Mayura", source_lang)
            return text, source_lang

        translated_parts: list[str] = []
        detected_source = source_lang
        for chunk in self._split_text(text):
            translated_chunk, chunk_source = self._translate_chunk(
                chunk,
                source_lang,
                target_lang,
            )
            translated_parts.append(translated_chunk)
            if chunk_source and chunk_source != AUTO_CODE:
                detected_source = chunk_source

        translated = "\n".join(part.strip() for part in translated_parts if part.strip())
        return translated or text, detected_source

    def translate_to_english(self, text: str, source_lang: str) -> tuple[str, str]:
        """Translate a non-English prompt to English."""
        if source_lang == ENGLISH_CODE or not text.strip():
            return text, ENGLISH_CODE
        return self.translate(text, source_lang, ENGLISH_CODE)

    def translate_from_english(self, text: str, target_lang: str) -> str:
        """Translate an English answer back to the prompt language."""
        if target_lang == ENGLISH_CODE or not text.strip():
            return text
        translated, _ = self.translate(text, ENGLISH_CODE, target_lang)
        return translated


def get_translator() -> SarvamTranslator:
    """Get the shared Sarvam translator instance."""
    return SarvamTranslator.get_instance()


def detect_and_translate_query(text: str) -> Tuple[str, str]:
    """
    Detect the prompt language and translate it to English if needed.

    Returns:
        (english_text, detected_language_code)
    """
    translator = get_translator()
    detected = translator.detect_language(text)

    if detected == ENGLISH_CODE:
        return text, detected

    english_text, detected_source = translator.translate_to_english(text, detected)
    target_lang = detected_source if detected_source in MAYURA_SUPPORTED_LANGUAGES else detected
    logger.info(
        "Translated query [%s] -> [%s]: %s chars -> %s chars",
        target_lang,
        ENGLISH_CODE,
        len(text),
        len(english_text),
    )
    return english_text, target_lang


def translate_response(text: str, target_lang: str) -> str:
    """Translate an English response to the prompt language."""
    if target_lang == ENGLISH_CODE:
        return text

    translator = get_translator()
    translated = translator.translate_from_english(text, target_lang)
    logger.info(
        "Translated response [%s] -> [%s]: %s chars -> %s chars",
        ENGLISH_CODE,
        target_lang,
        len(text),
        len(translated),
    )
    return translated
